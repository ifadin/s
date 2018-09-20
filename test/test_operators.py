import unittest
from datetime import datetime
from unittest import mock

from airflow import DAG

from operators import BigQueryInsertOperator, BQSDKHook


class BigQueryInsertOperatorTest(unittest.TestCase):

    def setUp(self):
        self.task_id = 'test_task'
        self.conn_id = 'test_conn'
        self.project = 'test_project'
        self.dataset = 'test_dataset'
        self.table = 'test_table'

        self.expected_table_id = '.'.join((self.project, self.dataset, self.table))

    def __construct_operator(self, data):
        dag = DAG('test_dag', start_date=datetime(2017, 1, 1))

        return BigQueryInsertOperator(
            dag=dag,
            task_id=self.task_id,
            bq_conn_id=self.conn_id,
            dataset=self.dataset,
            table=self.table,
            data=data
        )

    @mock.patch('operators.BQSDKHook')
    def test_insert_operator(self, bq_class_hook):
        bq_hook = mock.Mock(spec=BQSDKHook)
        type(bq_hook).project_id = mock.PropertyMock(return_value=self.project)
        bq_class_hook.return_value = bq_hook

        expected_data = []
        self.__construct_operator(expected_data).execute(None)

        bq_class_hook.assert_called_with(gcp_conn_id=self.conn_id)
        bq_hook.insert_rows.assert_called_with(self.expected_table_id, expected_data)

        expected_data = [{'col1': 'row1_data'}, {'col2': 'row1_data'}, {'col1': 'row2_data'}]
        self.__construct_operator(expected_data).execute(None)
        bq_hook.insert_rows.assert_called_with(self.expected_table_id, expected_data)
