#!/usr/bin/env bash

set -euf -o pipefail

MODE="${1:-test}"
AWS_ACCOUNT="${AWS_ACCOUNT}"
AWS_HOST="${AWS_HOST}"
DB_USER="${DB_USER}"
RDS_DBNAME="${RDS_DBNAME}"
RDS_PORT=63333
CLUSTER_PORT=6432
CLUSTER_DBNAME="${CLUSTER_DBNAME}"

if [[ "${MODE}" == "prod" || "${MODE}" == "production" ]]; then
    RDS_PASS="${RDS_PASS_PROD}"
    RDS_URL="${RDS_URL_PROD}"
    CLUSTER="${CLUSTER_PROD}"
    CLUSTER_URL="${CLUSTER_URL_PROD}"
else
    RDS_PASS="${RDS_PASS_TEST}"
    RDS_URL="${RDS_URL_TEST}"
    CLUSTER="${CLUSTER_TEST}"
    CLUSTER_URL="${CLUSTER_URL_TEST}"
fi

function decrypt_rds_pass(){
    local _pass="$1"

    aws --region=eu-central-1 kms decrypt --ciphertext-blob fileb://<(echo "$_pass" | base64 --decode) --query Plaintext --output text | base64 --decode
}

function decrypt_cluster_pass(){
    local _user="$1"
    local _db_url="$2"

    zkubectl get secrets "$_user.$_db_url.credentials" -o jsonpath={.data.password} | base64 --decode
}

function test_piu_connection {
    local _user="${1}"
    local _pass="${2}"
    local _host="${3}"
    local _port="${4}"
    local _db="${5}"
    local tunnel_cmd="piu odd-eu-central-1.$AWS_ACCOUNT.$AWS_HOST 'migrating db' && ssh -L $_port:$_host.eu-central-1.rds.amazonaws.com:5432 odd-eu-central-1.$AWS_ACCOUNT.$AWS_HOST"
    local _dbname="postgresql://$_user:$_pass@localhost:$_port/$_db"

    psql --no-password --dbname="$_dbname" -l -q &>/dev/null || \
        (echo -e "A remote tunnel is required! Please run:\n\e[93m${tunnel_cmd}\e[39m\n" && exit 1)
}

function test_cluster_connection {
    local _user="${1}"
    local _pass="${2}"
    local _host="${3}"
    local _port="${4}"
    local _db="${5}"
    local tunnel_cmd="zkubectl port-forward $(zkubectl get pod -l version="$_host",spilo-role=master -o jsonpath={.items..metadata.name}) $_port:5432"
    local _dbname="postgresql://$_user:$_pass@localhost:$_port/$_db"

    psql --no-password --dbname="$_dbname" -l -q &>/dev/null || \
        (echo -e "A remote tunnel is required! Please run:\n\e[93m${tunnel_cmd}\e[39m\n" && exit 1)
}

function migrate(){
    local _rds_pass="$(decrypt_rds_pass "$RDS_PASS")"
    local _rds_dbname="postgresql://$DB_USER:$_rds_pass@localhost:$RDS_PORT/$RDS_DBNAME"
    local _cluster_pass="$(decrypt_cluster_pass "$DB_USER" "$CLUSTER_URL")"
    local _cluster_dbname="postgresql://$DB_USER:$_cluster_pass@localhost:$CLUSTER_PORT/$CLUSTER_DBNAME"

    pg_dump -Fc --no-password --dbname="$_rds_dbname" | \
            pg_restore --clean --no-password --dbname="$_cluster_dbname"
}

zaws re "$AWS_ACCOUNT"
zkubectl login "$CLUSTER"

test_piu_connection "$DB_USER" "$(decrypt_rds_pass "$RDS_PASS")" "$RDS_URL" "$RDS_PORT" "$RDS_DBNAME"
test_cluster_connection "$DB_USER" "$(decrypt_cluster_pass "$DB_USER" "$CLUSTER_URL")" "$CLUSTER_URL" "$CLUSTER_PORT" "$CLUSTER_DBNAME"
migrate