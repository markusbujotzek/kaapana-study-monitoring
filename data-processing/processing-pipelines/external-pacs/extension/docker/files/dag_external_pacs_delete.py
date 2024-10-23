import json
from datetime import timedelta

import requests
from airflow.models import DAG
from airflow.utils.dates import days_ago
from airflow.utils.log.logging_mixin import LoggingMixin
from external_pacs.LocalExternalPacsOperator import LocalExternalPacsOperator
from kaapana.operators.LocalWorkflowCleanerOperator import LocalWorkflowCleanerOperator

log = LoggingMixin().log

# TODO This is called way too many times by airflow_webserver.
def get_endpoints():
    response = requests.get(
        LocalExternalPacsOperator.DICOM_WEB_MULTIPLEXER_SERVICE + "/endpoints/"
    )
    return [e["endpoint"] for e in json.loads(response.content.decode("utf-8"))]


external_endpoints = get_endpoints()

ui_form = {
    "data_form": {},
    "workflow_form": {
        "type": "object",
        "properties": {
            "dcmweb_endpoint": {
                "title": "External dicomWeb endpoint",
                "description": "Choose which dicomWeb endpoint to remove",
                "type": "string",
                "enum": list(set(external_endpoints)),
                "required": True,
            },
        },
    },
}


args = {
    "ui_visible": True,
    "ui_forms": ui_form,
    "owner": "kaapana",
    "start_date": days_ago(0),
    "retries": 1,
    "retry_delay": timedelta(seconds=30),
}

dag = DAG(
    dag_id="external-pacs-delete",
    default_args=args,
    max_active_runs=1,
    schedule_interval=None,
)
init_operator = LocalExternalPacsOperator(dag=dag, action="delete")
clean = LocalWorkflowCleanerOperator(dag=dag, clean_workflow_dir=True)

(init_operator >> clean)  # type: ignore
