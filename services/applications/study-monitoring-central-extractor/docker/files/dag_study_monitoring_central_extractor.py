from airflow.utils.dates import days_ago
from datetime import timedelta
from airflow.models import DAG
from kaapana.operators.LocalWorkflowCleanerOperator import LocalWorkflowCleanerOperator
from kaapana.operators.LocalGetInputDataOperator import LocalGetInputDataOperator
from kaapana.operators.Bin2DcmOperator import Bin2DcmOperator
from racoon_monitoring.LocalPushToPromOperator import LocalPushToPromOperator
from kaapana.operators.DeleteFromMetaOperator import DeleteFromMetaOperator
from kaapana.operators.DeleteFromPacsOperator import DeleteFromPacsOperator

max_active_runs = 5

ui_forms = {
    "workflow_form": {
        "type": "object",
        "properties": {
            "single_execution": {
                "title": "single execution",
                "description": "Should each series be processed separately?",
                "type": "boolean",
                "default": True,
                "readOnly": False,
            }
        },
    }
}

args = {
    "ui_visible": True,
    "ui_forms": ui_forms,
    "owner": "kaapana",
    "start_date": days_ago(0),
    "retries": 3,
    "retry_delay": timedelta(seconds=30),
}

dag = DAG(
    dag_id="study-monitoring-central-extractor",
    default_args=args,
    concurrency=4,
    max_active_runs=1,
    schedule_interval=None,
)

get_input = LocalGetInputDataOperator(dag=dag)

dcm2txt = Bin2DcmOperator(
    dag=dag, input_operator=get_input, name="extract-binary", file_extensions="*.dcm"
)

push_metrics = LocalPushToPromOperator(dag=dag, input_operator=dcm2txt)

delete_dcm_pacs = DeleteFromPacsOperator(
    dag=dag, input_operator=get_input, delete_complete_study=True, retries=1
)
delete_dcm_meta = DeleteFromMetaOperator(
    dag=dag, input_operator=get_input, delete_complete_study=True, retries=1
)

clean = LocalWorkflowCleanerOperator(dag=dag, clean_workflow_dir=True)

get_input >> dcm2txt >> push_metrics >> delete_dcm_pacs >> delete_dcm_meta
get_input >> delete_dcm_meta >> clean
