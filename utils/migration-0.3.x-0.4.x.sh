#!/bin/bash
set -eu -o pipefail

CONTAINER_REGISTRY_URL=registry.hzdr.de/kaapana/releases
IMAGE_POSTGRES_OLD=${CONTAINER_REGISTRY_URL}/postgres-15.6-alpine:0.3.5
IMAGE_POSTGRES_NEW=${CONTAINER_REGISTRY_URL}/postgres-17.2-alpine:0.4.0
IMAGE_POSTGRES_DCM4CHE_OLD=${CONTAINER_REGISTRY_URL}/dcm4che-postgres:0.3.5
IMAGE_POSTGRES_DCM4CHE_NEW=${CONTAINER_REGISTRY_URL}/dcm4che-postgres:0.4.0

TMP_MIGRATION_DIR=/home/ubuntu/kaapana-migration
FAST_DATA_DIR=/home/kaapana

TMP_DATABASE_DUMP_DIR=${TMP_MIGRATION_DIR}/dumps
mkdir -p ${TMP_DATABASE_DUMP_DIR}

docker pull ${IMAGE_POSTGRES_OLD}
docker pull ${IMAGE_POSTGRES_NEW}
docker pull ${IMAGE_POSTGRES_DCM4CHE_OLD}
docker pull ${IMAGE_POSTGRES_DCM4CHE_NEW}

#### Backend
echo "Start migration of kaapana-backend database"

if [ ! -d ${TMP_MIGRATION_DIR}/backend ]; then
    mkdir -p ${TMP_MIGRATION_DIR}/backend
    cp -r ${FAST_DATA_DIR}/postgres-backend ${TMP_MIGRATION_DIR}/backend/backup
fi

docker run --name postgres15-backend -d -e POSTGRES_USER=kaapanauser -e POSTGRES_PASSWORD=kaapanapassword -v ${TMP_MIGRATION_DIR}/backend/backup/:/var/lib/postgresql/data ${IMAGE_POSTGRES_OLD}
sleep 5
docker exec postgres15-backend pg_dumpall --username kaapanauser > ${TMP_DATABASE_DUMP_DIR}/backend.dump

docker run --name postgres17-backend -d -v ${TMP_MIGRATION_DIR}/backend/data:/var/lib/postgresql/data -v ${TMP_DATABASE_DUMP_DIR}/:/db/dumps/  -e POSTGRES_USER=kaapanauser -e POSTGRES_PASSWORD=kaapanapassword ${IMAGE_POSTGRES_NEW}
sleep 5
docker exec postgres17-backend psql --username=kaapanauser -f /db/dumps/backend.dump

docker stop postgres15-backend postgres17-backend
docker rm postgres15-backend postgres17-backend

rm -r ${FAST_DATA_DIR}/postgres-backend
cp -r ${TMP_MIGRATION_DIR}/backend/data ${FAST_DATA_DIR}/postgres-backend

echo "Completed migration of kaapana-backend database"

#### Keycloak
echo "Start migration of Keycloak database"

if [ ! -d ${TMP_MIGRATION_DIR}/keycloak ]; then
    mkdir -p ${TMP_MIGRATION_DIR}/keycloak
    cp -r ${FAST_DATA_DIR}/keycloak ${TMP_MIGRATION_DIR}/keycloak/backup
fi

docker run --name postgres15-keycloak -d -e PGDATA="/db/db-files" -e POSTGRES_DB=keycloak -e POSTGRES_USER=keycloak -e POSTGRES_PASSWORD=keycloak -v ${TMP_MIGRATION_DIR}/keycloak/backup/db-files/:/db/db-files ${IMAGE_POSTGRES_OLD}
sleep 5
docker exec postgres15-keycloak pg_dumpall --username keycloak > ${TMP_DATABASE_DUMP_DIR}/keycloak.dump

docker run --name postgres17-keycloak -d -v ${TMP_MIGRATION_DIR}/keycloak/data/:/db/db-files/ -v ${TMP_DATABASE_DUMP_DIR}/:/db/dumps/ -e PGDATA="/db/db-files" -e POSTGRES_DB=keycloak -e POSTGRES_USER=keycloak -e POSTGRES_PASSWORD=keycloak ${IMAGE_POSTGRES_NEW}
sleep 5
docker exec postgres17-keycloak psql -d keycloak --username=keycloak -f /db/dumps/keycloak.dump

docker stop postgres15-keycloak postgres17-keycloak
docker rm postgres15-keycloak postgres17-keycloak

rm -r ${FAST_DATA_DIR}/keycloak/db-files
cp -r ${TMP_MIGRATION_DIR}/keycloak/data ${FAST_DATA_DIR}/keycloak/db-files

echo "Completed migration of Keycloak database"

#### Airflow
echo "Start migration of Airflow database"

if [ ! -d ${TMP_MIGRATION_DIR}/airflow ]; then
    mkdir -p ${TMP_MIGRATION_DIR}/airflow
    cp -r ${FAST_DATA_DIR}/postgres-airflow ${TMP_MIGRATION_DIR}/airflow/backup
fi
docker run --name postgres15-airflow -d -e POSTGRES_DB=airflow -e POSTGRES_USER=root -e POSTGRES_PASSWORD=root -v ${TMP_MIGRATION_DIR}/airflow/backup/:/var/lib/postgresql/data ${IMAGE_POSTGRES_OLD}
sleep 5
docker exec postgres15-airflow pg_dumpall --username root > ${TMP_DATABASE_DUMP_DIR}/airflow.dump

docker run --name postgres17-airflow -d -v ${TMP_MIGRATION_DIR}/airflow/data:/var/lib/postgresql/data -v ${TMP_DATABASE_DUMP_DIR}/:/db/dumps/  -e POSTGRES_DB=airflow -e POSTGRES_USER=root -e POSTGRES_PASSWORD=root ${IMAGE_POSTGRES_NEW}
sleep 5
docker exec postgres17-airflow psql -d airflow --username=root -f /db/dumps/airflow.dump

docker stop postgres15-airflow postgres17-airflow
docker rm postgres15-airflow postgres17-airflow

rm -r ${FAST_DATA_DIR}/postgres-airflow
cp -r ${TMP_MIGRATION_DIR}/airflow/data ${FAST_DATA_DIR}/postgres-airflow

echo "Completed migration of Airflow database"

#### Dcm4chee 5.32.0 to 5.33.1
echo "Start migration of dcm4che database"

if [ ! -d ${TMP_MIGRATION_DIR}/dcm4che ]; then
    mkdir -p ${TMP_MIGRATION_DIR}/dcm4che
    cp -r ${FAST_DATA_DIR}/postgres-dcm4che ${TMP_MIGRATION_DIR}/dcm4che/backup
fi

curl https://raw.githubusercontent.com/dcm4che/dcm4chee-arc-light/refs/heads/master/dcm4chee-arc-entity/src/main/resources/sql/psql/update-5.33-psql.sql -o ${TMP_MIGRATION_DIR}/dcm4che/update-5.33-psql.sql
cp -r ${TMP_MIGRATION_DIR}/dcm4che/backup ${TMP_MIGRATION_DIR}/dcm4che/data-updated-schema
docker run --name postgres15-dcm4che -d -e POSTGRES_DB=pacsdb -e POSTGRES_USER=pacs -e POSTGRES_PASSWORD=pacs -v ${TMP_MIGRATION_DIR}/dcm4che/update-5.33-psql.sql:/sql/update-5.33-psql.sql -v ${TMP_MIGRATION_DIR}/dcm4che/data-updated-schema/:/var/lib/postgresql/data ${IMAGE_POSTGRES_DCM4CHE_OLD}
sleep 5
docker exec postgres15-dcm4che update-schema 5.33
docker exec postgres15-dcm4che pg_dumpall --username pacs > ${TMP_DATABASE_DUMP_DIR}/dcm4che.dump

docker run --name postgres17-dcm4che -d -v ${TMP_MIGRATION_DIR}/dcm4che/data:/var/lib/postgresql/data -v ${TMP_DATABASE_DUMP_DIR}/:/db/dumps/  -e POSTGRES_DB=pacsdb -e POSTGRES_USER=pacs -e POSTGRES_PASSWORD=pacs ${IMAGE_POSTGRES_NEW}
sleep 5
docker exec postgres17-dcm4che psql -d pacsdb --username=pacs -f /db/dumps/dcm4che.dump

docker stop postgres15-dcm4che postgres17-dcm4che
docker rm postgres15-dcm4che postgres17-dcm4che

rm -r ${FAST_DATA_DIR}/postgres-dcm4che
cp -r ${TMP_MIGRATION_DIR}/dcm4che/data ${FAST_DATA_DIR}/postgres-dcm4che

echo "Completed migration of dcm4che database"

#### Opensearch
echo "Backup opensearch data and remove opensearch directory from FAST_DATA_DIR."

if [ ! -d ${TMP_MIGRATION_DIR}/os ]; then
    mkdir -p ${TMP_MIGRATION_DIR}/opensearch
    cp -r ${FAST_DATA_DIR}/os ${TMP_MIGRATION_DIR}/opensearch/backup
fi
rm -r ${FAST_DATA_DIR}/os

echo "Completed migration script successfully."