FROM local-only/base-installer:latest

LABEL IMAGE="dag-study-monitoring-central-extractor"
LABEL VERSION="0.0.0"
LABEL CI_IGNORE="False"

COPY files/study_monitoring /kaapana/tmp/dags/study_monitoring
COPY files/dag_study_monitoring_central_extractor.py /kaapana/tmp/dags/dag_study_monitoring_central_extractor.py
COPY files/dag_study_monitoring_central_extractor_trigger_rule.json /kaapana/tmp/dags/dag_study_monitoring_central_extractor_trigger_rule.json