#!/usr/bin/env bash

set -euf pipefail

AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_SESSION_TOKEN=
AWS_SESSION_EXPIRATION=

function aws_login {
    local _role="${S3_ACCESS_ROLE:-arn:aws:iam::<account>:role/<role>}"

    echo "Assuming $_role role"
    local _creds_json=$(aws sts assume-role --role-arn "$_role" --role-session-name datalake-session)

    AWS_SESSION_EXPIRATION="$(echo "$_creds_json" | jq -r .Credentials.Expiration)"
    AWS_ACCESS_KEY_ID="$(echo "$_creds_json" | jq -r .Credentials.AccessKeyId)"
    AWS_SECRET_ACCESS_KEY="$(echo "$_creds_json" | jq -r .Credentials.SecretAccessKey)"
    AWS_SESSION_TOKEN="$(echo "$_creds_json" | jq -r .Credentials.SessionToken)"
}

function aws_with_role() {
    [[ -z "$AWS_SESSION_EXPIRATION" || $(date +%s) -ge $(date -d "$AWS_SESSION_EXPIRATION" +%s) ]] && aws_login

    AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
    AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
    AWS_SESSION_TOKEN="$AWS_SESSION_TOKEN" aws $@
}

function bq_login() {
    local _bq_key="$1"
    local _bq_project="$2"

    echo "Activating ${_bq_project} BQ project"
    gcloud auth activate-service-account --key-file="${_bq_key}" --project="${_bq_project}"
}

function is_bucket() {
    local _key="$1"

    [[ "$_key" == */ ]] && echo true || echo false
}

function load_s3_to_bq() {
    local _s3_key="$1"
    local _local_dir="$2"
    local _bq_project="$3"
    local _bq_dataset="$4"
    local _bq_table="$5"
    local _bq_format="$6"
    local _bq_key="$7"

    echo "Uploading from ${_s3_key} to ${_local_dir}"
    aws_with_role s3 ls --summarize --human-readable "$_s3_key"

    data_files=$(aws_with_role s3 ls "$_s3_key" | awk '{print $4}')
    for path in ${data_files};
    do
        local _remote_path=$([[ $(is_bucket "${_s3_key}") == true ]] && echo "$_s3_key$path" || echo "$_s3_key")
        local _local_path="${_local_dir}/${path}"

        aws_with_role s3 cp "$_remote_path" "$_local_path"
        bq_login "$_bq_key" "$_bq_project"
        bq --project_id="$_bq_project" load --autodetect --source_format="$_bq_format" "$_bq_dataset.$_bq_table" "$_local_path"

        rm "$_local_path"
    done
}

function cleanup() {
    local _dir="$1"
    echo "Cleaning up $_dir" && rm -Rf "${_dir}"
}

PROC_NAME="${DAG_ID:-dl_to_bq}"
TEMP_DIR=$(mktemp -d -t "${PROC_NAME}.XXXXX")
trap 'cleanup ${TEMP_DIR}' EXIT SIGINT SIGTERM


S3_DATA_BUCKET="${S3_DATA_BUCKET:-"s3://<bucket>/"}"
BQ_PROJECT="${BQ_PROJECT:-"<bq_project>"}"
BQ_DATASET="${BQ_DATASET:-"dl_load"}"
BQ_TABLE="${BQ_TABLE:-"sales_avro_small"}"
BQ_FORMAT="${BQ_FORMAT:-AVRO}"
BQ_KEY="${BQ_KEY:-${AIRFLOW_HOME-.}/keys/bq-$BQ_PROJECT.json}"

load_s3_to_bq "$S3_DATA_BUCKET" "$TEMP_DIR" "$BQ_PROJECT" "$BQ_DATASET" "$BQ_TABLE" "$BQ_FORMAT" "$BQ_KEY"
