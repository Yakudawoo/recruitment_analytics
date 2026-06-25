import os
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
import requests
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
GENERATED_DATA_DIR = DATA_DIR / "generated"

MOCK_DATASET_PROFILE = os.getenv("MOCK_DATASET_PROFILE", "original").lower()

if MOCK_DATASET_PROFILE == "large":
    EXCEL_FILE = GENERATED_DATA_DIR / "hiring_data_large.xlsx"
    WEBHOOK_FILE = GENERATED_DATA_DIR / "webhook_application_events_large.json"
else:
    EXCEL_FILE = DATA_DIR / "hiring_data.xlsx"
    WEBHOOK_FILE = DATA_DIR / "webhook_application_events.json"

class WebhookRegistration(BaseModel):
    url: str


class StageChangeRequest(BaseModel):
    new_stage: str
    current_status: str = "active"


class DecisionRequest(BaseModel):
    reason: Optional[str] = None


app = FastAPI(
    title="Mock Greenhouse API",
    description=(
        "A lightweight Greenhouse API simulator seeded from the exercise dataset. "
        "This is used to emulate Greenhouse REST API and webhook behavior."
    ),
    version="1.0.0",
)


@app.get("/dataset-profile")
def get_dataset_profile():
    return {
        "profile": MOCK_DATASET_PROFILE,
        "excel_file": str(EXCEL_FILE),
        "webhook_file": str(WEBHOOK_FILE),
    }


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def serialize_value(value):
    if pd.isna(value):
        return None

    if isinstance(value, pd.Timestamp):
        return value.isoformat()

    if isinstance(value, datetime):
        return value.isoformat()

    return value


def dataframe_to_records(df):
    records = []

    clean_df = df.replace("(null)", pd.NA)

    for row in clean_df.to_dict(orient="records"):
        clean_row = {}

        for key, value in row.items():
            clean_row[key] = serialize_value(value)

        records.append(clean_row)

    return records


def load_seed_data():
    if not EXCEL_FILE.exists():
        raise FileNotFoundError(f"Missing seed file: {EXCEL_FILE}")

    if not WEBHOOK_FILE.exists():
        raise FileNotFoundError(f"Missing webhook seed file: {WEBHOOK_FILE}")

    sheets = pd.read_excel(EXCEL_FILE, sheet_name=None)

    with open(WEBHOOK_FILE, "r", encoding="utf-8") as file:
        events = json.load(file)

    normalized_events = []

    for event in events:
        normalized_event = dict(event)

        if "current__stage" in normalized_event:
            normalized_event["current_stage"] = normalized_event.pop("current__stage")

        normalized_events.append(normalized_event)

    return {
        "jobs": dataframe_to_records(sheets["ghjb_jobs"]),
        "openings": dataframe_to_records(sheets["ghop_openings"]),
        "candidates": dataframe_to_records(sheets["ghca_candidates"]),
        "applications": dataframe_to_records(sheets["ghap_applications"]),
        "offers": dataframe_to_records(sheets["ghof_offers"]),
        "application_events": normalized_events,
        "registered_webhooks": [],
    }


STATE = load_seed_data()


def paginate(records, limit, offset):
    return {
        "count": len(records),
        "limit": limit,
        "offset": offset,
        "data": records[offset : offset + limit],
    }


def filter_records(records, filters):
    filtered = records

    for field_name, expected_value in filters.items():
        if expected_value is None:
            continue

        filtered = [
            record
            for record in filtered
            if str(record.get(field_name)) == str(expected_value)
        ]

    return filtered


def find_application(application_id):
    for application in STATE["applications"]:
        if str(application.get("ghap_application_id")) == str(application_id):
            return application

    raise HTTPException(
        status_code=404,
        detail=f"Application not found: {application_id}",
    )


def get_latest_application_event(application_id):
    events = [
        event
        for event in STATE["application_events"]
        if str(event.get("application_id")) == str(application_id)
    ]

    if not events:
        return None

    return sorted(
        events,
        key=lambda event: event.get("last_activity_at") or "",
    )[-1]


def update_application_state(application_id, status=None, stage=None):
    application = find_application(application_id)

    if status is not None:
        application["ghap_status"] = status

    if stage is not None:
        application["ghap_application_current_stage"] = stage

    application["ghap_last_activity_at"] = now_utc()

    return application


def build_event(
    application_id,
    action,
    previous_status,
    current_status,
    previous_stage,
    current_stage,
    rejection_reason=None,
):
    return {
        "organization_id": 8020479101,
        "organization_name": "Teads",
        "action": action,
        "application_id": int(application_id),
        "previous_status": previous_status,
        "current_status": current_status,
        "last_activity_at": now_utc(),
        "rejected_at": now_utc() if action == "reject_candidate" else None,
        "rejection_reason": rejection_reason,
        "rejection_details": None,
        "previous_stage": previous_stage,
        "current_stage": current_stage,
    }


def dispatch_event_to_registered_webhooks(event):
    deliveries = []

    for url in STATE["registered_webhooks"]:
        try:
            response = requests.post(url, json=event, timeout=3)

            deliveries.append(
                {
                    "url": url,
                    "status_code": response.status_code,
                    "success": 200 <= response.status_code < 300,
                }
            )

        except requests.RequestException as error:
            deliveries.append(
                {
                    "url": url,
                    "status_code": None,
                    "success": False,
                    "error": str(error),
                }
            )

    return deliveries


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "mock_greenhouse_api",
        "seeded_objects": {
            "jobs": len(STATE["jobs"]),
            "openings": len(STATE["openings"]),
            "candidates": len(STATE["candidates"]),
            "applications": len(STATE["applications"]),
            "offers": len(STATE["offers"]),
            "application_events": len(STATE["application_events"]),
        },
    }


@app.get("/jobs")
def get_jobs(
    status: Optional[str] = None,
    office: Optional[str] = None,
    department: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    records = filter_records(
        STATE["jobs"],
        {
            "ghjb_job_status": status,
            "ghjb_gh_office_name": office,
            "ghjb_gh_department_name": department,
        },
    )

    return paginate(records, limit, offset)


@app.get("/openings")
def get_openings(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    return paginate(STATE["openings"], limit, offset)


@app.get("/candidates")
def get_candidates(
    recruiter: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    records = filter_records(
        STATE["candidates"],
        {
            "ghca_recruiter_name": recruiter,
        },
    )

    return paginate(records, limit, offset)


@app.get("/applications")
def get_applications(
    status: Optional[str] = None,
    stage: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    records = filter_records(
        STATE["applications"],
        {
            "ghap_status": status,
            "ghap_application_current_stage": stage,
        },
    )

    return paginate(records, limit, offset)


@app.get("/offers")
def get_offers(
    status: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    records = filter_records(
        STATE["offers"],
        {
            "ghof_status": status,
        },
    )

    return paginate(records, limit, offset)


@app.get("/application-events")
def get_application_events(
    application_id: Optional[int] = None,
    action: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    records = filter_records(
        STATE["application_events"],
        {
            "application_id": application_id,
            "action": action,
        },
    )

    return paginate(records, limit, offset)


@app.post("/webhooks/register")
def register_webhook(payload: WebhookRegistration):
    if payload.url not in STATE["registered_webhooks"]:
        STATE["registered_webhooks"].append(payload.url)

    return {
        "registered_webhooks": STATE["registered_webhooks"],
    }


@app.post("/applications/{application_id}/stage-change")
def change_application_stage(application_id: int, payload: StageChangeRequest):
    application = find_application(application_id)
    latest_event = get_latest_application_event(application_id)

    previous_stage = (
        latest_event.get("current_stage")
        if latest_event
        else application.get("ghap_application_current_stage")
    )

    previous_status = (
        latest_event.get("current_status")
        if latest_event
        else application.get("ghap_status")
    )

    event = build_event(
        application_id=application_id,
        action="candidate_stage_change",
        previous_status=previous_status,
        current_status=payload.current_status,
        previous_stage=previous_stage,
        current_stage=payload.new_stage,
    )

    STATE["application_events"].append(event)

    update_application_state(
        application_id,
        status=payload.current_status,
        stage=payload.new_stage,
    )

    deliveries = dispatch_event_to_registered_webhooks(event)

    return {
        "event": event,
        "webhook_deliveries": deliveries,
    }


@app.post("/applications/{application_id}/reject")
def reject_candidate(application_id: int, payload: DecisionRequest):
    application = find_application(application_id)
    latest_event = get_latest_application_event(application_id)

    current_stage = (
        latest_event.get("current_stage")
        if latest_event
        else application.get("ghap_application_current_stage")
    )

    previous_status = (
        latest_event.get("current_status")
        if latest_event
        else application.get("ghap_status")
    )

    event = build_event(
        application_id=application_id,
        action="reject_candidate",
        previous_status=previous_status,
        current_status="rejected",
        previous_stage=current_stage,
        current_stage=current_stage,
        rejection_reason=payload.reason,
    )

    STATE["application_events"].append(event)

    update_application_state(
        application_id,
        status="rejected",
        stage=current_stage,
    )

    deliveries = dispatch_event_to_registered_webhooks(event)

    return {
        "event": event,
        "webhook_deliveries": deliveries,
    }


@app.post("/applications/{application_id}/hire")
def hire_candidate(application_id: int):
    application = find_application(application_id)
    latest_event = get_latest_application_event(application_id)

    current_stage = (
        latest_event.get("current_stage")
        if latest_event
        else application.get("ghap_application_current_stage")
    )

    previous_status = (
        latest_event.get("current_status")
        if latest_event
        else application.get("ghap_status")
    )

    event = build_event(
        application_id=application_id,
        action="hire_candidate",
        previous_status=previous_status,
        current_status="hired",
        previous_stage=current_stage,
        current_stage=current_stage,
    )

    STATE["application_events"].append(event)

    update_application_state(
        application_id,
        status="hired",
        stage=current_stage,
    )

    deliveries = dispatch_event_to_registered_webhooks(event)

    return {
        "event": event,
        "webhook_deliveries": deliveries,
    }
