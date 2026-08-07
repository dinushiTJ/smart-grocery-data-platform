"""Daily Smart Grocery ingestion and loading workflow."""

from datetime import timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from pendulum import datetime


PROJECT_DIR = "/opt/smart-grocery"

default_args = {
    "owner": "smart-grocery",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="smart_grocery_pipeline",
    description="Extract, generate prices, validate, and load grocery data",
    default_args=default_args,
    schedule="@daily",
    start_date=datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    tags=["smart-grocery", "batch", "etl"],
) as dag:
    extract_products = BashOperator(
        task_id="extract_products",
        bash_command="python ingestion/extract_products.py",
        cwd=PROJECT_DIR,
        append_env=True,
    )

    generate_prices = BashOperator(
        task_id="generate_prices",
        bash_command="python ingestion/generate_prices.py",
        cwd=PROJECT_DIR,
        append_env=True,
    )

    clean_validate_and_load = BashOperator(
        task_id="clean_validate_and_load",
        bash_command="python -m processing.run_pipeline",
        cwd=PROJECT_DIR,
        append_env=True,
    )

    extract_products >> generate_prices >> clean_validate_and_load
