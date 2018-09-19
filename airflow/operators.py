from airflow.operators.python_operator import PythonOperator


class TemplatedPythonOperator(PythonOperator):
    """
    PythonOperator with templating on op_kwargs.
    """
    template_fields = PythonOperator.template_fields + ('op_args', 'op_kwargs')
