import os
import uuid
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from google.cloud import bigquery

from ingestion.greenhouse_api_client import GreenhouseApiClient


load_dotenv()

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
RAW_DATASET = os.getenv("BQ_RAW_DATASET", "raw_greenhouse")


RESOURCE_TO_RAW_TABLE = {
    "jobs": "raw_greenhouse_jobs",
    "openings": "raw_greenhouse_openings",
    "candidates": "raw_greenhouse_candidates",
    "applications": "raw_greenhouse_applications",
    "offers": "raw_greenhouse_offers",
    "application_events": "raw_greenhouse_application_events",
}


def require_env_vars() -> None:
    missing = []

    for variable in ["GCP_PROJECT_ID", "BQ_RAW_DATASET", "MOCK_GREENHOUSE_BASE_URL"]:
        if not os.getenv(variable):
            missing.append(variable)

    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}"
        )


def build_raw_dataframe(
    records: list[dict[str, Any]],
    source_object: str,
    batch_id: str,
) -> pd.DataFrame:
    df = pd.DataFrame(records)

    if df.empty:
        df = pd.DataFrame(columns=["_empty_payload"])

    df = df.replace("(null)", pd.NA)

    # RAW layer contract:
    # keep fields as string-friendly raw values and let dbt cast/clean downstream.
    for column in df.columns:
        df[column] = df[column].astype("string")

    df["_ingestion_batch_id"] = batch_id
    df["_ingested_at"] = datetime.now(timezone.utc).isoformat()
    df["_source_system"] = "greenhouse"
    df["_source_object"] = source_object
    df["_loaded_by"] = "workato_api_sync_simulator"

    return df


def load_dataframe_to_bigquery(
    client: bigquery.Client,
    df: pd.DataFrame,
    table_name: str,
) -> None:
    table_id = f"{PROJECT_ID}.{RAW_DATASET}.{table_name}"

    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        autodetect=True,
    )

    job = client.load_table_from_dataframe(
        df,
        table_id,
        job_config=job_config,
    )

    job.result()

    destination_table = client.get_table(table_id)

    print(f"Loaded {destination_table.num_rows} rows into {table_id}")


def main() -> None:
    require_env_vars()

    batch_id = str(uuid.uuid4())

    print("Starting Workato API sync simulator")
    print(f"GCP project: {PROJECT_ID}")
    print(f"BigQuery RAW dataset: {RAW_DATASET}")
    print(f"Ingestion batch ID: {batch_id}")

    greenhouse_client = GreenhouseApiClient()
    bigquery_client = bigquery.Client(project=PROJECT_ID)

    health = greenhouse_client.health()
    print(f"Mock Greenhouse health: {health['status']}")

    resources = {
        "jobs": greenhouse_client.get_jobs(),
        "openings": greenhouse_client.get_openings(),
        "candidates": greenhouse_client.get_candidates(),
        "applications": greenhouse_client.get_applications(),
        "offers": greenhouse_client.get_offers(),
        "application_events": greenhouse_client.get_application_events(),
    }

    for resource_name, records in resources.items():
        table_name = RESOURCE_TO_RAW_TABLE[resource_name]

        df = build_raw_dataframe(
            records=records,
            source_object=resource_name,
            batch_id=batch_id,
        )

        load_dataframe_to_bigquery(
            client=bigquery_client,
            df=df,
            table_name=table_name,
        )

    print("Workato API sync simulator completed successfully")


if __name__ == "__main__":
    main()
