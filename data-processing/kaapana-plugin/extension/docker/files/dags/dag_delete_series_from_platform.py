from datetime import timedelta
import glob
import json
import os
from pathlib import Path

from airflow.models import DAG
from airflow.utils.dates import days_ago
from airflow.utils.log.logging_mixin import LoggingMixin
from airflow.exceptions import AirflowSkipException

from kaapana.blueprints.kaapana_global_variables import AIRFLOW_WORKFLOW_DIR, BATCH_NAME
from kaapana.operators.DeleteFromMetaOperator import DeleteFromMetaOperator
from kaapana.operators.DeleteFromPacsOperator import DeleteFromPacsOperator
from kaapana.operators.GetInputOperator import GetInputOperator
from kaapana.operators.KaapanaPythonBaseOperator import KaapanaPythonBaseOperator
from kaapana.operators.LocalWorkflowCleanerOperator import LocalWorkflowCleanerOperator

log = LoggingMixin().log
ui_forms = {
    "workflow_form": {
        "type": "object",
        "properties": {
            "single_execution": {
                "title": "single execution",
                "description": "Should each series be processed separately?",
                "type": "boolean",
                "default": False,
                "readOnly": False,
            },
            "delete_complete_study": {
                "title": "Delete entire study",
                "default": False,
                "type": "boolean",
                "readOnly": False,
            },
        },
    }
}


args = {
    "ui_visible": True,
    "ui_forms": ui_forms,
    "owner": "kaapana",
    "start_date": days_ago(0),
    "retries": 1,
    "retry_delay": timedelta(seconds=15),
}

dag = DAG(
    dag_id="delete-series-from-platform",
    default_args=args,
    concurrency=30,
    max_active_runs=1,
    schedule_interval=None,
)

get_input = GetInputOperator(dag=dag, data_type="json")

def set_skip_if_dcm_is_external(ds, **kwargs):
    batch_dir = Path(AIRFLOW_WORKFLOW_DIR) / kwargs["dag_run"].run_id / BATCH_NAME
    batch_folder = [f for f in glob.glob(os.path.join(batch_dir, "*"))]

    for batch_element_dir in batch_folder:
        input_dir = Path(batch_element_dir) / get_input.operator_out_dir
        json_files = sorted(
            glob.glob(
                os.path.join(input_dir, "*.json*"),
                recursive=True,
            )
        )
        for json_file in json_files:
            with open(json_file, "r") as f:
                metadata = json.load(f)
            if metadata.get("00020016 SourceApplicationEntityTitle") == "kaapana_external":
                raise AirflowSkipException("DICOM file is comes from external PACS")
    return


skip_if_dcm_is_external = KaapanaPythonBaseOperator(
    name="skip_if_dcm_is_external",
    pool="default_pool",
    pool_slots=1,
    python_callable=set_skip_if_dcm_is_external,
    dag=dag,
)


delete_dcm_pacs = DeleteFromPacsOperator(
    dag=dag, input_operator=get_input, delete_complete_study=False, retries=1
)
delete_dcm_meta = DeleteFromMetaOperator(
    dag=dag, input_operator=get_input, delete_complete_study=False, retries=1
)
clean = LocalWorkflowCleanerOperator(dag=dag, clean_workflow_dir=True)

get_input >> skip_if_dcm_is_external >> delete_dcm_meta >> clean

(skip_if_dcm_is_external >> delete_dcm_pacs >> clean)
