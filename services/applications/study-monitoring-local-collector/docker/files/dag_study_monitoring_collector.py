from airflow.utils.dates import days_ago
from datetime import timedelta, datetime
from airflow.models import DAG
from kaapana.operators.Bin2DcmOperator import Bin2DcmOperator
from study_monitoring.LocalGetMetricsOperator import LocalGetMetricsOperator
from study_monitoring.LocalAggregateMetricsOperator import (
    LocalAggregateMetricsOperator,
)
from airflow.utils.trigger_rule import TriggerRule
from kaapana.operators.LocalWorkflowCleanerOperator import LocalWorkflowCleanerOperator
from kaapana.blueprints.kaapana_global_variables import (
    KAAPANA_BUILD_VERSION,
    INSTANCE_NAME,
    SERVICES_NAMESPACE,
)
from kaapana.operators.DcmSendOperator import DcmSendOperator

CENTRAL_IP_ADDRESS = "10.128.129.41"
CENTRAL_DICOM_PORT = 1112


max_active_runs = 5
args = {
    "ui_visible": True,
    "owner": "kaapana",
    "start_date": days_ago(0),
    "retries": 1,
    "retry_delay": timedelta(seconds=30),
}

dag = DAG(
    dag_id="cronjob-study-monitoring-local-collector",
    default_args=args,
    concurrency=4,
    max_active_runs=1,
    schedule_interval=None,
    # schedule_interval="@daily",
    # schedule_interval="*/15 * * * *",
)

get_kaapana_metrics = LocalGetMetricsOperator(
    dag=dag,
    component_id="kaapana",
    metrics_endpoint=f"http://kaapana-backend-service.{SERVICES_NAMESPACE}.svc:5000/monitoring/metrics/scrape",
    verify_ssl=False,
)


# TODO: uncomment to collect metrics from further third-party systems
# get_third_party_metrics = LocalGetMetricsOperator(
#     dag=dag,
#     component_id="third_party",
#     metrics_endpoint=f"https://:{THRID_PARTY}/metrics",
#     verify_ssl=False,
# )

aggregate_metrics = LocalAggregateMetricsOperator(
    dag=dag,
    metrics_operators=[
        get_kaapana_metrics,
        # TODO: uncomment to collect metrics from further third-party systems
        # get_third_party_metrics,
    ],
    instance_name=INSTANCE_NAME,
    version=KAAPANA_BUILD_VERSION,
    trigger_rule=TriggerRule.ALL_DONE,
)

txt2dcm = Bin2DcmOperator(
    dag=dag,
    name="metrics2dicom",
    patient_name="node-metrics",
    instance_name=INSTANCE_NAME,
    manufacturer="Kaapana",
    manufacturer_model="node-metrics",
    version=KAAPANA_BUILD_VERSION,
    study_id="node-metrics",
    study_uid=None,
    protocol_name=None,
    study_description=None,
    series_description=f"Node metrics from {INSTANCE_NAME} | {datetime.now().astimezone().replace(microsecond=0).isoformat()}",
    size_limit=10,
    input_operator=aggregate_metrics,
    file_extensions="*.txt",
)

dcm_send_int = DcmSendOperator(
    dag=dag,
    name="dcm-send-internal",
    level="batch",
    pacs_host=f"ctp-dicom-service.{SERVICES_NAMESPACE}.svc",
    pacs_port="11112",
    ae_title="node-metrics",
    input_operator=txt2dcm,
)

dcm_send_to_central = DcmSendOperator(
    dag=dag,
    name="dcm-send-central",
    level="batch",
    pacs_host=CENTRAL_IP_ADDRESS,
    pacs_port=f"{CENTRAL_DICOM_PORT}",
    ae_title="node-metrics",
    input_operator=txt2dcm,
)

clean = LocalWorkflowCleanerOperator(dag=dag, clean_workflow_dir=True)

get_kaapana_metrics >> aggregate_metrics
# TODO: uncomment to collect metrics from further third-party systems
# get_third_party_metrics >> aggregate_metrics
aggregate_metrics >> txt2dcm >> dcm_send_int >> clean
txt2dcm >> dcm_send_to_central >> clean
