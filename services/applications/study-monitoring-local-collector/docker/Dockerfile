FROM local-only/base-installer:latest

LABEL IMAGE="dag-study-monitoring-local-collector"
LABEL VERSION="0.0.0"
LABEL CI_IGNORE="False"

COPY files/study_monitoring /kaapana/tmp/dags/study_monitoring
COPY files/dag_study_monitoring_collector.py /kaapana/tmp/dags/dag_study_monitoring_collector.py