import datetime, pytz
import os
from pydantic_settings import BaseSettings
from pydantic import Field, AliasChoices, field_validator
from zipfile import ZipFile
from pathlib import Path
from typing import Any

from kaapanapy.helper import get_minio_client, load_workflow_config
from kaapanapy.settings import OperatorSettings, KaapanaSettings
from kaapanapy.logger import get_logger
from minio import Minio

logger = get_logger(__name__)

TIMEZONE = KaapanaSettings().timezone
WORKFLOW_CONFIG = load_workflow_config()
OPERATOR_SETTINGS = OperatorSettings()


def get_project_bucket_name():
    """
    Return the name of the project bucket.
    The project is received form the workflow config.
    """
    project = WORKFLOW_CONFIG.get("project_form")
    return project.get("s3_bucket")


class MinioOperatorArguments(BaseSettings):
    """
    This class parses the arguments given to the MinioOperator from environment variables.

    Comma separeted strings are parsed to list of strings.
    If the bucket_name is "None" or "" the project bucket is determined.
    The string zip_files is converted to a boolean.
    """

    action: str
    bucket_name: str = Field("", validation_alias="BUCKET_NAME")
    minio_prefix: str = Field("", validation_alias="MINIO_PREFIX")
    zip_files: bool = Field(True)
    whitelisted_file_extensions: str = Field("")
    source_files: str = Field(
        "",
        description="Explicit path to files on that action should be applied. The path is relative to minio_prefix and bucket_name",
        validation_alias=AliasChoices("SOURCE_FILES"),
    )

    batch_input_operators: str = Field(
        "", validation_alias=AliasChoices("BATCH_INPUT_OPERATORS")
    )
    none_batch_input_operators: str = Field(
        "", validation_alias=AliasChoices("NONE_BATCH_INPUT_OPERATORS")
    )

    @field_validator("bucket_name", mode="before")
    @classmethod
    def set_bucket_to_project_bucket_if_empty(cls, v: Any):
        if v is None:
            return get_project_bucket_name()
        elif type(v) is str and (v.lower() == "none" or v == ""):
            return get_project_bucket_name()
        else:
            return v

    @field_validator(
        "whitelisted_file_extensions",
        "source_files",
        "batch_input_operators",
        "none_batch_input_operators",
    )
    @classmethod
    def list_from_commaseparated_string(cls, v: Any):
        if type(v) == str and v == "":
            return []
        elif type(v) == str:
            return v.split(",")
        else:
            raise TypeError(f"{v=} must be of type str but is {type(v)}")

    @field_validator("zip_files", mode="before")
    @classmethod
    def str_to_bool(cls, v: Any):
        if v == "True":
            return True
        elif v == "False":
            return False
        else:
            raise ValueError(f"zip_files must be one of ['True','False'] not v")


def file_is_whitelisted(path: Path, whitelisted_file_extensions: list[str]):
    """
    Check if the file extension of the file at path are part of whitelisted_file_extensions.
    """
    if type(path) is str:
        path = Path(path)
    for extension in whitelisted_file_extensions:
        num_extensions = extension.count(".")
        ### Take whitelisted_file_extensions like .nii.gz into account
        if "".join(path.suffixes[-num_extensions:]) in whitelisted_file_extensions:
            logger.debug(f"File at {path=} whitelisted: {extension=}")
            return True
    logger.debug(f"File at {path=} not whitelisted!")
    return False


def download_objects(
    bucket_name: str,
    minio_prefix: str,
    source_files: list,
):
    """
    Download all files in source_files from bucket_name.
    Paths in source_files must be relative to bucket_name/minio_prefix.
    Files are downloaded into WORKFLOW_DIR/<operator_out_dir>/file_path for each file_path in source_files.

    - Initialize minio client
    - Create target_directory WORKFLOW_DIR/<operator_out_dir>/
    - Download all objects from minio into WORKFLOW_DIR/<operator_out_dir>/

    :params bucket_name:
    :params minio_prefix:
    :params source_files:

    **Raises:**
    * AssertionError: If source_files is empty
    """
    assert len(source_files) > 0, f"source_files must be non-empty list, if action=get"

    target_dir = os.path.join(
        OPERATOR_SETTINGS.workflow_dir,
        OPERATOR_SETTINGS.operator_out_dir,
    )
    os.makedirs(target_dir, exist_ok=True)
    minio_client: Minio = get_minio_client()

    for file_path in source_files:
        target_path = os.path.join(target_dir, file_path)
        object_path = os.path.join(minio_prefix, file_path)
        minio_client.fget_object(
            bucket_name, object_name=object_path, file_path=target_path
        )


def get_absolute_batch_operator_source_directories(
    batch_operator_source_directories: list,
):
    """
    Return a list of all absolute paths that match WORKFLOW_DIR/BATCH_NAME/<series-uid>/operator_out_dir
    for each operator_out_dir in <batch_operator_source_directories>.

    :param batch_operator_source_directories: List of directories that are operator_out_dir of an upstream operator.
    """
    workflow_batch_directory = Path(
        os.path.join(OPERATOR_SETTINGS.workflow_dir, OPERATOR_SETTINGS.batch_name)
    )
    if not workflow_batch_directory.is_dir():
        logger.warning(f"{workflow_batch_directory=} does not exist!")
        return []  # dir.iterdir() raises FileNotFoundError if dir doesn't exist
    absolute_batch_operator_source_directories = []
    for series_directory in workflow_batch_directory.iterdir():
        for operator_in_dir in batch_operator_source_directories:
            batch_operator_directory = series_directory.joinpath(operator_in_dir)
            if not batch_operator_directory.is_dir():
                logger.warning(f"{batch_operator_directory=} does not exist!")
            absolute_batch_operator_source_directories.append(batch_operator_directory)
    return absolute_batch_operator_source_directories


def get_absolute_none_batch_operator_source_directories(
    none_batch_operator_source_directories: list,
):
    """
    Return a list of all absolute paths that match WORKFLOW_DIR/operator_out_dir
    for each operator_out_dir in <none_batch_operator_source_directories>.

    :param none_batch_operator_source_directories: List of directories that are operator_out_dir of an upstream operator.
    """
    workflow_directory = Path(OPERATOR_SETTINGS.workflow_dir)
    if not workflow_directory.is_dir():
        logger.warning(f"{workflow_directory=} does not exist!")

    absolute_operator_source_directories = []
    for operator_directory in none_batch_operator_source_directories:
        operator_in_dir = workflow_directory.joinpath(operator_directory)
        if not operator_in_dir.is_dir():
            logger.warning(f"{operator_in_dir=} does not exist!")
        absolute_operator_source_directories.append(operator_in_dir)
    return absolute_operator_source_directories


def upload_objects(
    bucket_name: str,
    minio_prefix: str,
    whitelisted_file_extensions: list,
    zip_files: bool = True,
    source_files: list = [],
    source_directories: list = [],
):
    """
    Upload files to Minio.
    - Initialize minio client
    - Collect files from source_directories that match with whitelisted_file_extensions
    - Collect files from source_files that match whitelisted_file_extensions
    - If not zip_files: Upload all files to MinIO
    - If zip_files: Create archive from all collected files and upload archive to MinIo.

    :param source_directories: List of directories, from which files should be uploaded.
    :param bucket_name: The minio bucket, where the data will be uploaded.
    :param minio_prefix: A minio prefix relative to the bucket name, under which the data will be uploaded.
    :param zip_files: Whether the files should be zipped in a single archive before uploading them. Archive paths will be the paths relative to WORKFLOW_DIR.
    :param whitelisted_file_extensions: Exclusive list of file extensions, of files that will be uploaded.
    :param source_files: List of file paths relative to WORKFLOW_DIR, that should be uploaded

    - Collect all files that should be uploaded and match any extenstion in white_listed_file_extensions
    - If zip_files is true, create a archive of all collected files.
    - Upload either this archive or all collected files to minio_prefix relative to bucket_name

    Raises:
        * ValueError if no files were found to upload
    """
    logger.info("Start upload to MinIO!")
    logger.info(f"Search for files in {source_directories=}")
    minio_client: Minio = get_minio_client()

    zip_archive_file_path = Path("/tmp/zipped_files.zip")
    files_to_upload = []

    for source_directory in source_directories:
        files = [f for f in Path(source_directory).glob("**/*") if not f.is_dir()]
        for file_path in files:
            if not file_is_whitelisted(Path(file_path), whitelisted_file_extensions):
                continue
            files_to_upload.append(file_path)
            logger.info(f"Collect {file_path=} for upload!")

    for file_path in source_files:
        if not file_is_whitelisted(Path(file_path), whitelisted_file_extensions):
            continue
        absoulute_file_path = Path(OPERATOR_SETTINGS.workflow_dir, file_path)
        files_to_upload.append(absoulute_file_path)
        logger.info(f"Collect {absoulute_file_path=} for upload!")

    if len(files_to_upload) == 0:
        logger.error(
            f"No files were collected for upload. Maybe you have to adapt {whitelisted_file_extensions=}."
        )
        raise ValueError(
            f"No files were found for upload. Maybe you have to adapt {whitelisted_file_extensions=}."
        )

    for file_path in files_to_upload:
        relative_file_path = Path(file_path).relative_to(
            Path(
                OPERATOR_SETTINGS.workflow_dir,
            )
        )
        if zip_files:
            with ZipFile(zip_archive_file_path, "a") as zip_file:
                zip_file.write(filename=file_path, arcname=relative_file_path)
        else:
            minio_file_path = os.path.join(minio_prefix, relative_file_path)
            minio_client.fput_object(
                bucket_name=bucket_name,
                file_path=file_path,
                object_name=minio_file_path,
            )

    if zip_files and len(files_to_upload) > 0:
        logger.info("Compress files into zip archive before uploading")
        timestamp = datetime.datetime.now(pytz.timezone(TIMEZONE)).strftime(
            "%y-%m-%d-%H:%M:%S%f"
        )
        run_id = OPERATOR_SETTINGS.run_id
        archive_name = f"{run_id}_{timestamp}.zip"
        minio_path = os.path.join(minio_prefix, archive_name)
        logger.info(f"Upload archive to {minio_path=}.")
        minio_client.fput_object(
            bucket_name=bucket_name,
            file_path=zip_archive_file_path,
            object_name=minio_path,
        )


if __name__ == "__main__":
    operator_arguments = MinioOperatorArguments()

    # Arguments provided via workflow config are prioritized
    action = operator_arguments.action
    zip_files = WORKFLOW_CONFIG.get("zip_files") or operator_arguments.zip_files
    bucket_name = WORKFLOW_CONFIG.get("bucket_name") or operator_arguments.bucket_name
    minio_prefix = (
        WORKFLOW_CONFIG.get("minio_prefix") or operator_arguments.minio_prefix
    )
    whitelisted_file_extensions = (
        WORKFLOW_CONFIG.get("whitelisted_file_extensions")
        or operator_arguments.whitelisted_file_extensions
    )
    source_files = (
        WORKFLOW_CONFIG.get("action_files") or operator_arguments.source_files
    )
    batch_input_operator_directories = operator_arguments.batch_input_operators
    none_batch_input_operator_directories = (
        operator_arguments.none_batch_input_operators
    )

    source_directories = get_absolute_batch_operator_source_directories(
        batch_operator_source_directories=batch_input_operator_directories
    ) + get_absolute_none_batch_operator_source_directories(
        none_batch_operator_source_directories=none_batch_input_operator_directories
    )

    if action == "put":
        upload_objects(
            source_directories=source_directories,
            bucket_name=bucket_name,
            minio_prefix=minio_prefix,
            zip_files=zip_files,
            whitelisted_file_extensions=whitelisted_file_extensions,
            source_files=source_files,
        )
    elif action == "get":
        download_objects(
            bucket_name=bucket_name,
            minio_prefix=minio_prefix,
            source_files=source_files,
        )
