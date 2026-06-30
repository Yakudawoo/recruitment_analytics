import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from google.cloud import bigquery


load_dotenv()

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
RAW_DATASET = os.getenv("BQ_RAW_DATASET", "raw_greenhouse")
LOCAL_DATA_DIR = Path(os.getenv("LOCAL_DATA_DIR", "data"))

EXCEL_FILE = LOCAL_DATA_DIR / "hiring_data.xlsx"
WEBHOOK_FILE = LOCAL_DATA_DIR / "webhook_application_events.json"


SHEET_TO_RAW_TABLE = {
    "ghjb_jobs": "raw_greenhouse_jobs",
    "ghop_openings": "raw_greenhouse_openings",
    "ghca_candidates": "raw_greenhouse_candidates",
    "ghap_applications": "raw_greenhouse_applications",
    "ghof_offers": "raw_greenhouse_offers",
}


def require_env_vars():
    missing = []

    for variable in ["GCP_PROJECT_ID"]:
        if not os.getenv(variable):
            missing.append(variable)

    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}"
        )


def clean_dataframe_for_raw_load(df, source_object, batch_id):
    raw_df = df.copy()

    raw_df = raw_df.replace("(null)", pd.NA)

    for column in raw_df.columns:
        raw_df[column] = raw_df[column].astype("string")

    raw_df["_ingestion_batch_id"] = batch_id
    raw_df["_ingested_at"] = datetime.now(timezone.utc).isoformat()
    raw_df["_source_system"] = "greenhouse"
    raw_df["_source_object"] = source_object
    raw_df["_loaded_by"] = "workato_simulator"

    return raw_df


def load_dataframe_to_bigquery(client, df, table_name):
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

    print(
        f"Loaded {destination_table.num_rows} rows into {table_id}"
    )


def load_excel_sheets(client, batch_id):
    if not EXCEL_FILE.exists():
        raise FileNotFoundError(f"Excel file not found: {EXCEL_FILE}")

    sheets = pd.read_excel(EXCEL_FILE, sheet_name=None)

    for sheet_name, table_name in SHEET_TO_RAW_TABLE.items():
        if sheet_name not in sheets:
            raise RuntimeError(f"Missing expected sheet in Excel file: {sheet_name}")

        df = clean_dataframe_for_raw_load(
            sheets[sheet_name],
            source_object=sheet_name,
            batch_id=batch_id,
        )

        load_dataframe_to_bigquery(client, df, table_name)


def load_webhook_events(client, batch_id):
    if not WEBHOOK_FILE.exists():
        raise FileNotFoundError(f"Webhook file not found: {WEBHOOK_FILE}")

    with open(WEBHOOK_FILE, "r", encoding="utf-8") as file:
        events = json.load(file)

    df = pd.DataFrame(events)

    if "current__stage" in df.columns:
        df = df.rename(columns={"current__stage": "current_stage"})

    if "last_activity_at" in df.columns:
        df["_event_id"] = (
            df["application_id"].astype(str)
            + "_"
            + df["action"].astype(str)
            + "_"
            + df["last_activity_at"].astype(str)
        )
    else:
        df["_event_id"] = [str(uuid.uuid4()) for _ in range(len(df))]

    df = clean_dataframe_for_raw_load(
        df,
        source_object="webhook_application_events",
        batch_id=batch_id,
    )

    load_dataframe_to_bigquery(
        client,
        df,
        "raw_greenhouse_application_events",
    )


def main():
    require_env_vars()

    batch_id = str(uuid.uuid4())

    print("Starting Workato simulator ingestion")
    print(f"GCP project: {PROJECT_ID}")
    print(f"BigQuery raw dataset: {RAW_DATASET}")
    print(f"Ingestion batch ID: {batch_id}")

    client = bigquery.Client(project=PROJECT_ID)

    load_excel_sheets(client, batch_id)
    load_webhook_events(client, batch_id)

    print("Workato simulator ingestion completed successfully")


if __name__ == "__main__":
    main()
