from __future__ import annotations

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator, get_current_context


PROJECT_ROOT = "/Users/olivierkdw/projets/recruitment_analytics"

DEMO_DATASET_EXPORTS = """
export USE_SUPABASE_OPERATIONAL_SOURCE=true
export BQ_RAW_DATASET=raw_greenhouse_demo
export BQ_STG_DATASET=stg_greenhouse_demo
export BQ_CORE_DATASET=core_greenhouse_demo
export BQ_MARTS_DATASET=marts_recruitment_demo
export BQ_LOCATION=EU
"""

DEMO_DATASETS = {
    "raw_dataset": "raw_greenhouse_demo",
    "stg_dataset": "stg_greenhouse_demo",
    "core_dataset": "core_greenhouse_demo",
    "marts_dataset": "marts_recruitment_demo",
    "bq_location": "EU",
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

{DEMO_DATASET_EXPORTS}

echo "Supabase demo BigQuery datasets:"
echo "  RAW:   $BQ_RAW_DATASET"
echo "  STG:   $BQ_STG_DATASET"
echo "  CORE:  $BQ_CORE_DATASET"
echo "  MARTS: $BQ_MARTS_DATASET"
echo "  LOCATION: $BQ_LOCATION"

{command}
"""


def check_supabase_demo_config() -> None:
    missing = [
        name
        for name in ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"]
        if not os.getenv(name)
    ]

    if missing:
        raise RuntimeError(
            "Missing required Airflow environment variables: "
            + ", ".join(missing)
        )

    context = get_current_context()
    dag_run = context.get("dag_run")
    dag_conf = (dag_run.conf if dag_run else {}) or {}

    if dag_conf.get("pipeline") not in {None, "supabase_demo"}:
        raise RuntimeError(
            f"Refusing non-demo pipeline conf: {dag_conf.get('pipeline')}"
        )

    for key, expected_value in DEMO_DATASETS.items():
        actual_value = dag_conf.get(key, expected_value)

        if actual_value != expected_value:
            raise RuntimeError(
                f"Refusing to run with {key}={actual_value}. "
                f"Expected demo value {expected_value}."
            )

    print("Supabase configuration is present. Secret values are not printed.")
    print("Validated Airflow dag_run.conf for Supabase demo pipeline.")
    print("Supabase demo BigQuery datasets:")
    for key, value in DEMO_DATASETS.items():
        print(f"  {key}: {value}")


with DAG(
    dag_id="supabase_recruitment_analytics_demo_pipeline",
    description=(
        "Runs the Supabase operational-source recruitment analytics pipeline "
        "against demo-only BigQuery datasets."
    ),
    default_args=default_args,
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    tags=["supabase", "bigquery", "dbt", "demo", "recruitment-analytics"],
) as dag:

    check_supabase_config = PythonOperator(
        task_id="check_supabase_config",
        python_callable=check_supabase_demo_config,
    )

    ingest_supabase_to_bigquery_raw_demo = BashOperator(
        task_id="ingest_supabase_to_bigquery_raw_demo",
        bash_command=project_command(
            ".venv/bin/python -m ingestion.load_supabase_operational_to_bigquery"
        ),
    )

    run_dbt_staging_demo = BashOperator(
        task_id="run_dbt_staging_demo",
        bash_command=project_command(
            ".venv/bin/dbt run "
            "--select path:models/staging "
            "--project-dir dbt_recruitment_analytics "
            "--profiles-dir dbt_recruitment_analytics"
        ),
    )

    run_dbt_core_demo = BashOperator(
        task_id="run_dbt_core_demo",
        bash_command=project_command(
            ".venv/bin/dbt run "
            "--select path:models/core "
            "--project-dir dbt_recruitment_analytics "
            "--profiles-dir dbt_recruitment_analytics"
        ),
    )

    run_dbt_marts_demo = BashOperator(
        task_id="run_dbt_marts_demo",
        bash_command=project_command(
            ".venv/bin/dbt run "
            "--select path:models/marts "
            "--project-dir dbt_recruitment_analytics "
            "--profiles-dir dbt_recruitment_analytics"
        ),
    )

    run_dbt_tests_demo = BashOperator(
        task_id="run_dbt_tests_demo",
        bash_command=project_command(
            ".venv/bin/dbt test "
            "--project-dir dbt_recruitment_analytics "
            "--profiles-dir dbt_recruitment_analytics"
        ),
    )

    (
        check_supabase_config
        >> ingest_supabase_to_bigquery_raw_demo
        >> run_dbt_staging_demo
        >> run_dbt_core_demo
        >> run_dbt_marts_demo
        >> run_dbt_tests_demo
    )
