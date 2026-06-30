import json
import os
import uuid
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from google.cloud import bigquery


load_dotenv()

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
RAW_DATASET = os.getenv("BQ_RAW_DATASET", "raw_greenhouse")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

TABLE_TO_RAW_TABLE = {
    "applications": "raw_supabase_applications",
    "application_stage_events": "raw_supabase_application_stage_events",
    "application_status_events": "raw_supabase_application_status_events",
    "stage_change_requests": "raw_supabase_stage_change_requests",
    "stage_change_request_items": "raw_supabase_stage_change_request_items",
    "outcome_change_requests": "raw_supabase_outcome_change_requests",
    "outcome_change_request_items": "raw_supabase_outcome_change_request_items",
}


def require_env_vars() -> None:
    missing = []

    for variable in ["GCP_PROJECT_ID", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"]:
        if not os.getenv(variable):
            missing.append(variable)

    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}"
        )


def supabase_select_all(table_name: str, page_size: int = 1000) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    offset = 0

    while True:
        query = urllib.parse.urlencode(
            {
                "select": "*",
                "limit": str(page_size),
                "offset": str(offset),
            }
        )
        url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/{table_name}?{query}"
        request = urllib.request.Request(
            url,
            headers={
                "apikey": SUPABASE_SERVICE_ROLE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
                "Accept": "application/json",
            },
            method="GET",
        )

        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                page = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8")
            raise RuntimeError(
                f"Supabase read failed for {table_name}: {error.code} {detail}"
            ) from error
        except urllib.error.URLError as error:
            raise RuntimeError(
                f"Supabase read failed for {table_name}: {error.reason}"
            ) from error

        records.extend(page)

        if len(page) < page_size:
            break

        offset += page_size

    return records


def build_raw_dataframe(
    records: list[dict[str, Any]],
    source_object: str,
    batch_id: str,
) -> pd.DataFrame:
    df = pd.DataFrame(records)

    if df.empty:
        df = pd.DataFrame(columns=["_empty_payload"])

    for column in df.columns:
        df[column] = df[column].map(
            lambda value: json.dumps(value, default=str)
            if isinstance(value, (dict, list))
            else value
        )
        df[column] = df[column].astype("string")

    df["_ingestion_batch_id"] = batch_id
    df["_ingested_at"] = datetime.now(timezone.utc).isoformat()
    df["_source_system"] = "supabase_operational_source"
    df["_source_object"] = source_object
    df["_loaded_by"] = "supabase_operational_sync"

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


def build_greenhouse_compatible_applications(
    records: list[dict[str, Any]],
    status_events: list[dict[str, Any]],
    stage_events: list[dict[str, Any]],
    batch_id: str,
) -> pd.DataFrame:
    mapped_records = []
    hired_at_by_application_id = {}
    applied_at_by_application_id = {}

    for event in status_events:
        if str(event.get("new_status") or "").lower() != "hired":
            continue

        application_id = event.get("application_id")
        changed_at = event.get("changed_at")

        if application_id is None or changed_at is None:
            continue

        existing_changed_at = hired_at_by_application_id.get(application_id)

        if existing_changed_at is None or str(changed_at) < str(existing_changed_at):
            hired_at_by_application_id[application_id] = changed_at

    for event in stage_events:
        application_id = event.get("application_id")
        changed_at = event.get("changed_at")

        if application_id is None or changed_at is None:
            continue

        existing_changed_at = applied_at_by_application_id.get(application_id)

        if existing_changed_at is None or str(changed_at) < str(existing_changed_at):
            applied_at_by_application_id[application_id] = changed_at

    for record in records:
        status = str(record.get("status") or "").lower()
        hired_at = record.get("hired_at") or hired_at_by_application_id.get(
            record.get("application_id")
        )
        if status == "hired" and not hired_at:
            hired_at = record.get("updated_at")

        applied_at = (
            record.get("applied_at")
            or record.get("created_at")
            or applied_at_by_application_id.get(record.get("application_id"))
        )
        last_activity_at = hired_at if status == "hired" and hired_at else record.get("updated_at")
        mapped_records.append(
            {
                "ghap_application_id": record.get("application_id"),
                "ghap_candidate_id": record.get("candidate_id"),
                "ghap_job_id": record.get("job_id"),
                "ghap_applied_at": applied_at,
                "ghap_rejected_at": None,
                "ghap_last_activity_at": last_activity_at,
                "ghap_hired_at": hired_at,
                "ghap_source": "supabase_operational_source",
                "ghap_rejection_reason": None,
                "ghap_status": record.get("status"),
                "ghap_application_current_stage": record.get("current_stage"),
                "ghap_jobs_count": None,
            }
        )

    return build_raw_dataframe(
        records=mapped_records,
        source_object="applications",
        batch_id=batch_id,
    )


def build_greenhouse_compatible_application_events(
    records: list[dict[str, Any]],
    batch_id: str,
) -> pd.DataFrame:
    mapped_records = []

    for record in records:
        mapped_records.append(
            {
                "organization_id": None,
                "organization_name": "Supabase operational source",
                "action": "candidate_stage_change",
                "application_id": record.get("application_id"),
                "previous_status": "active",
                "current_status": "active",
                "previous_stage": record.get("previous_stage"),
                "current_stage": record.get("new_stage"),
                "last_activity_at": record.get("changed_at"),
                "rejected_at": None,
                "rejection_reason": None,
                "rejection_details": None,
            }
        )

    return build_raw_dataframe(
        records=mapped_records,
        source_object="application_stage_events",
        batch_id=batch_id,
    )


def main() -> None:
    require_env_vars()

    batch_id = str(uuid.uuid4())
    bigquery_client = bigquery.Client(project=PROJECT_ID)

    print("Starting Supabase operational source sync")
    print(f"GCP project: {PROJECT_ID}")
    print(f"BigQuery RAW dataset: {RAW_DATASET}")
    print(f"Ingestion batch ID: {batch_id}")

    loaded_records: dict[str, list[dict[str, Any]]] = {}

    for source_table, raw_table in TABLE_TO_RAW_TABLE.items():
        records = supabase_select_all(source_table)
        loaded_records[source_table] = records
        df = build_raw_dataframe(
            records=records,
            source_object=source_table,
            batch_id=batch_id,
        )
        load_dataframe_to_bigquery(
            client=bigquery_client,
            df=df,
            table_name=raw_table,
        )

    compatible_applications = build_greenhouse_compatible_applications(
        loaded_records.get("applications", []),
        loaded_records.get("application_status_events", []),
        loaded_records.get("application_stage_events", []),
        batch_id,
    )
    load_dataframe_to_bigquery(
        client=bigquery_client,
        df=compatible_applications,
        table_name="raw_greenhouse_applications",
    )

    compatible_events = build_greenhouse_compatible_application_events(
        loaded_records.get("application_stage_events", []),
        batch_id,
    )
    load_dataframe_to_bigquery(
        client=bigquery_client,
        df=compatible_events,
        table_name="raw_greenhouse_application_events",
    )

    print("Supabase operational source sync completed successfully")


if __name__ == "__main__":
    main()
