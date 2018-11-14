import io
import os
import tempfile
from typing import List, Union

from airflow.contrib.hooks.gcp_api_base_hook import GoogleCloudBaseHook
from airflow.hooks.S3_hook import S3Hook
from airflow.models import BaseOperator
from airflow.operators.python_operator import PythonOperator
from airflow.utils import apply_defaults
from google.cloud import bigquery
from google.cloud.bigquery import TableReference, LoadJobConfig, LoadJob, WriteDisposition
from pandas.io import gbq

from utils import file_download_progress


class TemplatedPythonOperator(PythonOperator):
    """
    PythonOperator with templating on op_kwargs.
    """
    template_fields = PythonOperator.template_fields + ('op_args', 'op_kwargs')


class BigQueryInsertOperator(BaseOperator):
    """
    Insert rows into a BigQuery table using native Python SDK and streaming API.

    .. seealso::
        For more details about these operation:
        https://google-cloud-python.readthedocs.io/en/latest/bigquery/usage.html

    :param dataset: BigQuery dataset to use
    :type dataset: string
    :param table: BigQuery table to use
    :type table: string
    :param data: data to insert.
    :type data: List[dict]
    :param bq_conn_id: BigQuery Airflow connection.
    :type bq_conn_id: string
    """
    template_fields = ('dataset', 'table', 'data')
    ui_color = '#e4e6f0'

    @apply_defaults
    def __init__(self,
                 dataset,
                 table,
                 data,
                 bq_conn_id='bigquery_default',
                 *args,
                 **kwargs):
        super(BigQueryInsertOperator, self).__init__(*args, **kwargs)
        self.dataset = dataset
        self.table = table
        self.data = data
        self.bq_conn_id = bq_conn_id

    def execute(self, context):
        hook = BQSDKHook(gcp_conn_id=self.bq_conn_id)
        hook.insert_rows('.'.join((hook.project_id, self.dataset, self.table)), self.data)


class BQSDKHook(GoogleCloudBaseHook):

    def get_conn(self):
        GoogleCloudBaseHook.get_conn(self)

    def get_records(self, sql):
        GoogleCloudBaseHook.get_records(self, sql)

    def get_pandas_df(self, sql):
        GoogleCloudBaseHook.get_pandas_df(self, sql)

    def run(self, sql):
        GoogleCloudBaseHook.run(self, sql)

    @property
    def key_path(self):
        return self._get_field('key_path')

    def get_bq_client(self):
        return bigquery.Client.from_service_account_json(self.key_path)

    def insert_rows(self, table_id, data):
        self.log.info('Inserting data {} into BigQuery table {}'.format(data, table_id))

        client = bigquery.Client.from_service_account_json(self.key_path)

        table = client.get_table(TableReference.from_string(table_id))
        errors = client.insert_rows(table, data)

        if errors:
            raise Exception('BigQuery insert failed. Errors: {}', errors)

        return errors

    def load_file(self, data_file: Union[io.IOBase or str], dataset_id, table_id,
                  job_config: LoadJobConfig = None) -> LoadJob:
        """
        Loads data into a BigQuery table.

        .. seealso::
            https://googlecloudplatform.github.io/google-cloud-python/latest/bigquery/usage.html#tables
        """

        self.log.info(f'Loading {data_file} into BigQuery table {dataset_id}:{table_id}')
        client = bigquery.Client.from_service_account_json(self.key_path)

        dataset_ref = client.dataset(dataset_id)
        table_ref = dataset_ref.table(table_id)

        if not job_config:
            job_config = bigquery.LoadJobConfig()

        job: LoadJob = None
        try:
            with open(data_file, 'rb') if isinstance(data_file, str) else data_file as f:
                job = client.load_table_from_file(f, table_ref, location='EU', job_config=job_config)
                self.log.info('Starting job {}'.format(job.job_id))

            job.result()  # Waits for table load to complete.
            self.log.info('Loaded {} rows into {}:{}.'.format(job.output_rows, dataset_id, table_id))

            return job
        except Exception as err:
            if job:
                if job.errors:
                    self.log.error(f'Job failed: {job.errors}')
                job.cancel()
            raise err

    def get_rows_df(self, dataset, table):
        client = bigquery.Client.from_service_account_json(self.key_path)

        dataset_ref = client.dataset(dataset)
        table_ref = dataset_ref.table(table)
        table = client.get_table(table_ref)

        return client.list_rows(table).to_dataframe()

    def query_df(self, query, dialect='standard'):
        return gbq.read_gbq(query=query, dialect=dialect,
                            project_id=self.project_id, private_key=self.key_path)


class S3ToBigQueryOperator(BaseOperator):
    """
    Loads data into a BigQuery table from S3 bucket.

    :param s3_bucket: S3 data bucket
    :type s3_bucket: string
    :param s3_prefix: S3 key prefix
    :type s3_prefix: string
    :param data_format: data format (bigquery.SourceFormat.PARQUET)
    :type data_format: string
    :param bq_dataset: BigQuery dataset to use
    :type bq_dataset: string
    :param bq_table: BigQuery table to use
    :type bq_table: string
    :param s3_conn_id: AWS hook with S3 access.
    :type s3_conn_id: string
    :param bq_conn_id: BigQuery hook.
    :type bq_conn_id: string
    """
    template_fields = ('s3_bucket', 's3_prefix', 'bq_dataset', 'bq_table')

    @apply_defaults
    def __init__(self,
                 s3_bucket: str,
                 s3_prefix: str,
                 bq_dataset: str,
                 bq_table: str,
                 bq_job_config: LoadJobConfig = None,
                 s3_conn_id='aws_default',
                 bq_conn_id='bigquery_default',
                 *args,
                 **kwargs):
        super().__init__(*args, **kwargs)

        self.s3_bucket = s3_bucket
        self.s3_prefix = s3_prefix

        self.bq_dataset = bq_dataset
        self.bq_table = bq_table
        self.bq_job_config: LoadJobConfig = bq_job_config

        self.s3_conn_id = s3_conn_id
        self.bq_conn_id = bq_conn_id

    def execute(self, context):
        s3_hook = S3Hook(aws_conn_id=self.s3_conn_id)
        bq_hook = BQSDKHook(gcp_conn_id=self.bq_conn_id)

        s3_files = self.get_files(s3_hook)
        self.log.info(f'Found s3 files: {s3_files}')

        return self.load_files(s3_files, s3_hook, bq_hook)

    def get_files(self, s3_hook: S3Hook):
        return [f for f in s3_hook.get_conn().list_objects_v2(
            Bucket=self.s3_bucket,
            Prefix=self.s3_prefix
        ).get('Contents', []) if f.get('Size', 0) > 0]

    def _get_file_write_disposition(self, first_key, curr_key):
        """
        we should WRITE_TRUNCATE only for the first file to make sure that the whole task is idempotent,
        but for the other files we should use WRITE_APPEND so that all files actually are imported (and not just the last one 'wins')
        """
        if curr_key != first_key and self.bq_job_config.write_disposition == WriteDisposition.WRITE_TRUNCATE:
            return WriteDisposition.WRITE_APPEND
        else:
            return self.bq_job_config.write_disposition

    def load_files(self, files, s3_hook: S3Hook, bq_hook: BQSDKHook):

        with tempfile.TemporaryDirectory() as tmp_dir:
            for f in files:
                s3_key = f['Key']
                s3_size = f['Size']
                data_file = os.path.join(tmp_dir, s3_key.split('/')[-1])
                self.log.info(f'Downloading s3://{self.s3_bucket}/{s3_key} to {data_file}')

                s3_hook.get_conn().download_file(
                    self.s3_bucket, s3_key, data_file,
                    Callback=file_download_progress(s3_size, self.log))

                job_config: LoadJobConfig = self.bq_job_config
                job_config.write_disposition = self._get_file_write_disposition(first_key=files[0]['Key'],
                                                                                curr_key=s3_key)

                bq_hook.load_file(data_file, self.bq_dataset, self.bq_table, job_config)
