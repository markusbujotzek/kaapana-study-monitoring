from airflow.utils.log.logging_mixin import LoggingMixin
from airflow.utils.dates import days_ago
from datetime import timedelta
from airflow.models import DAG

from kaapana.operators.GetInputOperator import GetInputOperator
from kaapana.operators.MinioOperator import MinioOperator
from kaapana.operators.LocalWorkflowCleanerOperator import LocalWorkflowCleanerOperator
from example.ExtractStudyIdOperator import ExtractStudyIdOperator


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
            }
        },
    }
}

log = LoggingMixin().log

args = {
    "ui_forms": ui_forms,
    "ui_visible": True,
    "owner": "kaapana",
    "start_date": days_ago(0),
    "retries": 0,
    "retry_delay": timedelta(seconds=30),
}

dag = DAG(
    dag_id="example-dcm-extract-study-id", default_args=args, schedule_interval=None
)


get_input = GetInputOperator(dag=dag)
extract = ExtractStudyIdOperator(
    dag=dag, input_operator=get_input
)
put_to_minio = MinioOperator(dag=dag, action="put", batch_input_operators=[extract])
clean = LocalWorkflowCleanerOperator(dag=dag, clean_workflow_dir=True)

get_input >> extract >> put_to_minio >> clean
