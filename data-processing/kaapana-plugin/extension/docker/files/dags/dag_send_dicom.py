from datetime import timedelta

from airflow.models import DAG
from airflow.utils.dates import days_ago
from airflow.utils.log.logging_mixin import LoggingMixin
from kaapana.operators.DcmSendOperator import DcmSendOperator
from kaapana.operators.GetInputOperator import GetInputOperator
from kaapana.operators.LocalWorkflowCleanerOperator import LocalWorkflowCleanerOperator

log = LoggingMixin().log

ae_title = "NONE"
pacs_port = 11112

ui_forms = {
    "workflow_form": {
        "type": "object",
        "properties": {
            "pacs_host": {
                "title": "Receiver host",
                "description": "Specify the url/IP of the DICOM receiver.",
                "type": "string",
                "default": pacs_host,
                "required": True,
            },
            "pacs_port": {
                "title": "Receiver port",
                "description": "Specify the port of the DICOM receiver.",
                "type": "integer",
                "default": pacs_port,
            },
            "aetitle": {
                "title": "Receiver AE-title",
                "description": "Specify the port of the DICOM receiver.",
                "type": "string",
                "default": ae_title,
                "required": True,
            },
            "single_execution": {
                "title": "single execution",
                "description": "Should each series be processed separately?",
                "type": "boolean",
                "default": True,
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
    "retries": 0,
    "retry_delay": timedelta(seconds=30),
}

dag = DAG(
    dag_id="send-dicom",
    default_args=args,
    concurrency=10,
    max_active_runs=10,
    schedule_interval=None,
)

get_input = GetInputOperator(dag=dag)
dcm_send = DcmSendOperator(
    dag=dag,
    input_operator=get_input,
    ae_title=ae_title,
    pacs_host=pacs_host,
    pacs_port=pacs_port,
    level="element",
    enable_proxy=True,
    no_proxy=".svc,.svc.cluster,.svc.cluster.local",
    labels={"network-access-external-ips": "true"},
)

clean = LocalWorkflowCleanerOperator(dag=dag, clean_workflow_dir=True)

get_input >> dcm_send >> clean
