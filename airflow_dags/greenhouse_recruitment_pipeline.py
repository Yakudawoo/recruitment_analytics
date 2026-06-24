from __future__ import annotations

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator


PROJECT_ROOT = "/Users/olivierkdw/projets/recruitment_analytics"

DEFAULT_ENV = {
    "PROJECT_ROOT": PROJECT_ROOT,
}


default_args = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


def project_command(command: str) -> str:
    return f"""
set -euo pipefail

cd {PROJECT_ROOT}

set -a
source .env
set +a

{command}
"""


with DAG(
    dag_id="greenhouse_recruitment_analytics_pipeline",
    description="Orchestrates Mock Greenhouse API ingestion, BigQuery RAW loading, dbt transformations and dbt tests.",
    default_args=default_args,
    start_date=datetime(2026, 1, 1),
    schedule="@daily",
    catchup=False,
    max_active_runs=1,
    tags=["greenhouse", "bigquery", "dbt", "recruitment-analytics"],
) as dag:

    check_mock_greenhouse_api = BashOperator(
        task_id="check_mock_greenhouse_api",
        bash_command=project_command(
            'curl -sf "$MOCK_GREENHOUSE_BASE_URL/health"'
        ),
        env=DEFAULT_ENV,
    )

    load_greenhouse_api_to_bigquery_raw = BashOperator(
        task_id="load_greenhouse_api_to_bigquery_raw",
        bash_command=project_command(
            ".venv/bin/python -m ingestion.load_greenhouse_api_to_bigquery"
        ),
        env=DEFAULT_ENV,
    )

    dbt_run_staging = BashOperator(
        task_id="dbt_run_staging",
        bash_command=project_command(
            ".venv/bin/dbt run "
            "--select path:models/staging "
            "--project-dir dbt_recruitment_analytics "
            "--profiles-dir dbt_recruitment_analytics"
        ),
        env=DEFAULT_ENV,
    )

    dbt_run_core = BashOperator(
        task_id="dbt_run_core",
        bash_command=project_command(
            ".venv/bin/dbt run "
            "--select path:models/core "
            "--project-dir dbt_recruitment_analytics "
            "--profiles-dir dbt_recruitment_analytics"
        ),
        env=DEFAULT_ENV,
    )

    dbt_run_marts = BashOperator(
        task_id="dbt_run_marts",
        bash_command=project_command(
            ".venv/bin/dbt run "
            "--select path:models/marts "
            "--project-dir dbt_recruitment_analytics "
            "--profiles-dir dbt_recruitment_analytics"
        ),
        env=DEFAULT_ENV,
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=project_command(
            ".venv/bin/dbt test "
            "--project-dir dbt_recruitment_analytics "
            "--profiles-dir dbt_recruitment_analytics"
        ),
        env=DEFAULT_ENV,
    )

    (
        check_mock_greenhouse_api
        >> load_greenhouse_api_to_bigquery_raw
        >> dbt_run_staging
        >> dbt_run_core
        >> dbt_run_marts
        >> dbt_test
    )
