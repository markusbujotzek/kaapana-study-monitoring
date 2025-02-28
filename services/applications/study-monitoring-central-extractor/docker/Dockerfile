FROM local-only/base-installer:latest

LABEL IMAGE="dag-study-monitoring-central-extractor"
LABEL VERSION="0.0.0"
LABEL CI_IGNORE="False"

COPY files/racoon_monitoring /kaapana/tmp/dags/racoon_monitoring
COPY files/dag_racoon_monitoring_central_extractor.py /kaapana/tmp/dags/dag_racoon_monitoring_central_extractor.py
COPY files/dag_racoon_monitoring_central_extractor_trigger_rule.json /kaapana/tmp/dags/dag_racoon_monitoring_central_extractor_trigger_rule.json