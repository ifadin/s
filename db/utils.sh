#!/usr/bin/env bash

set -e
set -o pipefail

PASS_FILE

function shred_files {
  echo "Shredding file $PASS_FILE"
  rm -f ${PASS_FILE}
}
trap shred_files EXIT

function decrypt_pgpass {
  local pass_secret="keys/pgpass.secret"
  PASS_FILE="keys/.pgpass"

  export PGPASSFILE="$PASS_FILE"
  aws --region=eu-central-1 kms decrypt --ciphertext-blob fileb://${pass_secret} --output text --query Plaintext | base64 --decode > ${PASS_FILE}
  chmod 0600 "$PASS_FILE"
}

function test_remote_connection {
    local tunnel_port=61234
    local db_url="${1:-$DB_URL}"
    local db_user="${2:-$DB_USER}"
    local db_name="${3:-$DB_NAME}"
    local tunnel_cmd="<open-tunnel> && ssh -L ${tunnel_port}:${db_url}.eu-central-1.rds.amazonaws.com:5432 <ssh-host>"

    psql --no-password -l -q -h localhost -p "${tunnel_port}" -U "${db_user}" "${db_name}" &>/dev/null || \
        (echo -e "A remote tunnel is required! Please run:\n\e[93m${tunnel_cmd}\e[39m\n" && exit 1)
}

function test_local_connection {
    local db_user="${1:-$DB_USER}"
    local db_name="${2:-$DB_NAME}"
    local create_user="CREATE USER ${db_user} WITH PASSWORD '${db_user}';ALTER USER ${db_user} WITH SUPERUSER;"
    local local_postgres="docker run -d --name local-postgres -p 5432:5432 postgres && psql -h localhost -p 5432 -U ${db_user} -c \"${create_user}\" postgres"

    psql --no-password -l -q -h localhost -p 5432 -U postgres &>/dev/null || \
        (echo -e "Local postgres is required! Please run:\n\e[93m${local_postgres}\e[39m\n" && exit 1)
}

function dump_n_restore {
    local src_h="${DB_SRC_HOST:-localhost}"
    local src_p="${DB_SRC_PORT:-61234}"
    local src_u="${DB_SRC_USER:-postgres}"
    local src_n="${DB_SRC_NAME:-postgres}"

    local dest_h="${DB_DEST_HOST:-localhost}"
    local dest_p="${DB_DEST_PORT:-5432}"
    local dest_u="${DB_DEST_USER:-postgres}"
    local dest_n="${DB_DEST_NAME:-postgres}"

    echo -e "\e[94m Dumping from ${src_h}:${src_p} to ${dest_h}:${dest_p} ... \e[39m"
    pg_dump -Fc --no-password -h "${src_h}" -p "${src_p}" -U "${src_u}" "${src_n}" | \
        pg_restore --clean --no-password -h "${dest_h}" -p "${dest_p}" -U "${dest_u}" -d "${dest_n}"
    echo -e "\e[32m replication succeeded. \e[39m"
}
