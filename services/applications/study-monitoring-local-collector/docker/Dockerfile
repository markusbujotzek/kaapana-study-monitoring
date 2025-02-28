FROM local-only/base-installer:latest

LABEL IMAGE="dag-study-monitoring-local-collector"
LABEL VERSION="0.0.0"
LABEL CI_IGNORE="False"

COPY files/racoon_monitoring /kaapana/tmp/dags/racoon_monitoring
COPY files/dag_racoon_monitoring_collector.py /kaapana/tmp/dags/dag_racoon_monitoring_collector.py