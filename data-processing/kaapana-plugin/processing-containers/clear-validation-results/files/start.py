import glob
import json
import os
import re
from os import getenv

from kaapanapy.helper import (
    get_minio_client,
    get_opensearch_client,
    load_workflow_config,
)
from kaapanapy.helper.HelperOpensearch import DicomTags
from kaapanapy.logger import get_logger
from kaapanapy.settings import OpensearchSettings, OperatorSettings
from minio import Minio

logger = get_logger(__name__, level="INFO")


class ClearValidationResultOperator:
    """ClearValidationResultOperator deletes validation results from MinIO and OpenSearch."""

    def __init__(
        self,
        static_results_dir: str = "staticwebsiteresults",
        validation_tag: str = "00111001",
        opensearch_index: str = None,
    ):
        # Operator attributes
        self.static_results_dir = static_results_dir
        self.validation_tag = validation_tag
        self.validation_field = f"{validation_tag} ValidationResults_object"
        self.opensearch_index = opensearch_index

        # Airflow variables
        operator_settings = OperatorSettings()
        workflow_config = load_workflow_config()

        self.operator_in_dir = operator_settings.operator_in_dir
        self.workflow_dir = operator_settings.workflow_dir
        self.batch_name = operator_settings.batch_name
        self.run_id = operator_settings.run_id
        self.project_bucket = workflow_config["project_form"]["s3_bucket"]

        # set the opensearch_index if not provided
        # Set the project index from workflow config or else default index from settings
        if not opensearch_index:
            project_opensearch_index = workflow_config["project_form"][
                "opensearch_index"
            ]
            self.opensearch_index = (
                project_opensearch_index
                if project_opensearch_index is not None
                else OpensearchSettings().default_index
            )

        self.minio_client: Minio = get_minio_client()
        self.os_client = get_opensearch_client()

    def get_all_files_from_result_bucket(self, prefix=""):
        """
        Recursively retrieves all files from the specified MinIO bucket `staticwebsiteresults`.

        Args:
            prefix (str): The prefix to filter the objects in the MinIO bucket. Defaults to an empty string.

        Returns:
            list: A list of file paths in the specified MinIO bucket.
        """
        if prefix == "":
            prefix = self.static_results_dir
        allresults = self.minio_client.list_objects(self.project_bucket, prefix)
        files = []
        for item in allresults:
            if item.is_dir:
                files.extend(
                    self.get_all_files_from_result_bucket(prefix=item.object_name)
                )
            else:
                files.append(item.object_name)
        return files

    def remove_field_in_opensearch(self, seriesuid: str, tagfield: str = ""):
        """
        Removes a specified field from a document in OpenSearch.

        Args:
            seriesuid (str): The unique identifier for the series in OpenSearch.
            tagfield (str): The field to be removed from the document. Defaults to the class attribute `validation_field`.

        Returns:
            None
        """
        if tagfield == "":
            tagfield = self.validation_field

        # Update the document to remove the field
        response = self.os_client.update(
            index=self.opensearch_index,
            id=seriesuid,
            body={
                "script": {
                    "source": "ctx._source.remove(params.field)",
                    "lang": "painless",
                    "params": {"field": tagfield},
                }
            },
        )

        if response["result"] == "updated":
            logger.info(f"{tagfield} is deleted from the {seriesuid} in OpenSearch")
        else:
            logger.info(
                f"Warning!! {tagfield} could not be deleted from the {seriesuid} document in OpenSearch"
            )

        return

    def remove_from_minio(self, seriesuid: str):
        """
        Deletes all validation results for a given series from MinIO bucket `staticwebsiteresults`.

        Args:
            seriesuid (str): The unique identifier for the series to be deleted from MinIO.

        Returns:
            None
        """
        allfiles = self.get_all_files_from_result_bucket(prefix=self.static_results_dir)

        # match only the files placed under the subdirectory of serisuid
        sereismatcher = re.compile(rf"\/?{re.escape(seriesuid)}\/")
        seriesresults = [s for s in allfiles if sereismatcher.search(s)]

        if len(seriesresults) == 0:
            logger.info(f"No validation results found in minio for series {seriesuid}")
            return

        for result in seriesresults:
            self.minio_client.remove_object(self.project_bucket, result)
            logger.info(f"{result} is removed from minio")

        return

    def start(self):
        """
        Main execution method called by Airflow to run the operator.

        Returns:
            None
        """

        logger.info("Start Deleting Validation results")

        batch_folder = [
            f for f in glob.glob(os.path.join(self.workflow_dir, self.batch_name, "*"))
        ]

        for batch_element_dir in batch_folder:
            jsonfiles = sorted(
                glob.glob(
                    os.path.join(batch_element_dir, self.operator_in_dir, "*.json*"),
                    recursive=True,
                )
            )

            for metafile in jsonfiles:
                logger.info(f"Deleting validation results for file {metafile}")

                with open(metafile) as fs:
                    metadata = json.load(fs)

                seriesuid = metadata[
                    DicomTags.series_uid_tag
                ]  # "0020000E SeriesInstanceUID_keyword"

                self.remove_from_minio(seriesuid)
                self.remove_field_in_opensearch(
                    seriesuid, tagfield=self.validation_field
                )


if __name__ == "__main__":

    static_results_dir = getenv("STATIC_RESULTS_DIR", None)
    validation_tag = getenv("VALIDATION_TAG", None)
    opensearch_index = getenv("OPENSEARCH_INDEX", None)

    operator = ClearValidationResultOperator(
        static_results_dir=static_results_dir,
        validation_tag=validation_tag,
        opensearch_index=opensearch_index,
    )

    operator.start()
