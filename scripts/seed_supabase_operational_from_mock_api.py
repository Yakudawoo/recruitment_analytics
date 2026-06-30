import argparse
import json
import os
import uuid
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv


load_dotenv()

MOCK_API_BASE_URL = os.getenv("MOCK_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
UPSERT_BATCH_SIZE = 500
DISPLAY_ONLY_APPLICATION_COLUMNS = [
    "application_id",
    "candidate_full_name",
    "candidate_name",
    "job_title",
    "office_name",
    "department_name",
    "recruiter_name",
    "recruiter_email",
]


def require_env_vars() -> None:
    missing = []

    for variable in ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"]:
        if not os.getenv(variable):
            missing.append(variable)

    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}"
        )


def request_json(url: str) -> Any:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json"},
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8")
        raise RuntimeError(f"GET {url} failed: {error.code} {detail}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"GET {url} failed: {error.reason}") from error


def fetch_mock_paginated(endpoint: str, limit: int = 500) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    offset = 0

    while True:
        query = urllib.parse.urlencode(
            {
                "limit": limit,
                "offset": offset,
            }
        )
        payload = request_json(f"{MOCK_API_BASE_URL}/{endpoint.lstrip('/')}?{query}")
        page = payload.get("data", [])
        records.extend(page)

        count = payload.get("count")
        offset += limit

        if not page:
            break

        if count is not None and offset >= int(count):
            break

        if len(page) < limit:
            break

    return records


def get_key(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)

        if value is None:
            continue

        if str(value).strip().lower() == "(null)":
            continue

        return value

    return None


def to_int(value: Any) -> int | None:
    if value is None:
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_job_context(jobs: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    context: dict[int, dict[str, Any]] = {}

    for job in jobs:
        job_id = to_int(get_key(job, "ghjb_job_id", "job_id", "id"))

        if job_id is None:
            continue

        context[job_id] = {
            "job_title": get_key(job, "ghjb_job_name", "job_name", "title"),
            "recruiter": get_key(job, "ghjb_recruiter_name", "recruiter_name"),
            "recruiter_name": get_key(job, "ghjb_recruiter_name", "recruiter_name"),
            "recruiter_email": get_key(job, "ghjb_recruiter_email", "recruiter_email"),
            "office": get_key(job, "ghjb_gh_office_name", "office_name"),
            "office_name": get_key(job, "ghjb_gh_office_name", "office_name"),
            "department": get_key(job, "ghjb_gh_department_name", "department_name"),
            "department_name": get_key(job, "ghjb_gh_department_name", "department_name"),
        }

    return context


def build_candidate_context(candidates: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    context: dict[int, dict[str, Any]] = {}

    for candidate in candidates:
        candidate_id = to_int(get_key(candidate, "ghca_candidate_id", "candidate_id", "id"))

        if candidate_id is None:
            continue

        first_name = get_key(candidate, "ghca_first_name", "first_name")
        last_name = get_key(candidate, "ghca_last_name", "last_name")
        candidate_name = " ".join(
            part for part in [first_name, last_name] if part
        ).strip()

        context[candidate_id] = {
            "candidate_name": candidate_name or None,
            "created_at": get_key(candidate, "ghca_created_at", "created_at"),
        }

    return context


def build_application_rows(
    applications: list[dict[str, Any]],
    job_context: dict[int, dict[str, Any]],
    candidate_context: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []

    for application in applications:
        application_id = to_int(
            get_key(application, "ghap_application_id", "application_id", "id")
        )
        job_id = to_int(get_key(application, "ghap_job_id", "job_id"))
        candidate_id = to_int(
            get_key(application, "ghap_candidate_id", "candidate_id")
        )

        if application_id is None:
            continue

        context = job_context.get(job_id or -1, {})
        candidate = candidate_context.get(candidate_id or -1, {})
        updated_at = get_key(
            application,
            "ghap_last_activity_at",
            "last_activity_at",
            "updated_at",
        )
        applied_at = get_key(
            application,
            "ghap_applied_at",
            "applied_at",
            "created_at",
        )
        created_at = get_key(application, "created_at") or applied_at or candidate.get("created_at")
        status = get_key(application, "ghap_status", "status") or "active"

        rows.append(
            {
                "application_id": application_id,
                "candidate_id": candidate_id,
                "job_id": job_id,
                "candidate_full_name": candidate.get("candidate_name"),
                "candidate_name": candidate.get("candidate_name"),
                "job_title": context.get("job_title"),
                "current_stage": get_key(
                    application,
                    "ghap_application_current_stage",
                    "current_stage",
                ),
                "status": status,
                "recruiter": context.get("recruiter"),
                "recruiter_name": context.get("recruiter_name"),
                "recruiter_email": context.get("recruiter_email"),
                "office": context.get("office"),
                "office_name": context.get("office_name"),
                "department": context.get("department"),
                "department_name": context.get("department_name"),
                "applied_at": applied_at,
                "created_at": created_at,
                "hired_at": updated_at if status == "hired" else None,
                "updated_at": updated_at or now_utc(),
            }
        )

    return rows


def build_display_application_rows(
    applications: list[dict[str, Any]],
    job_context: dict[int, dict[str, Any]],
    candidate_context: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []

    for application in applications:
        application_id = to_int(
            get_key(application, "ghap_application_id", "application_id", "id")
        )
        job_id = to_int(get_key(application, "ghap_job_id", "job_id"))
        candidate_id = to_int(
            get_key(application, "ghap_candidate_id", "candidate_id")
        )

        if application_id is None:
            continue

        context = job_context.get(job_id or -1, {})
        candidate = candidate_context.get(candidate_id or -1, {})

        rows.append(
            {
                "application_id": application_id,
                "candidate_full_name": candidate.get("candidate_name"),
                "candidate_name": candidate.get("candidate_name"),
                "job_title": context.get("job_title"),
                "office_name": context.get("office_name"),
                "department_name": context.get("department_name"),
                "recruiter_name": context.get("recruiter_name"),
                "recruiter_email": context.get("recruiter_email"),
            }
        )

    return rows


def build_stage_event_rows(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []

    for event in events:
        application_id = to_int(get_key(event, "application_id"))
        new_stage = get_key(event, "current_stage", "new_stage")

        if application_id is None or not new_stage:
            continue

        changed_at = get_key(event, "last_activity_at", "changed_at") or now_utc()
        event_id = uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"mock_greenhouse_seed:{application_id}:{get_key(event, 'previous_stage')}:{new_stage}:{changed_at}",
        )

        rows.append(
            {
                "event_id": str(event_id),
                "application_id": application_id,
                "previous_stage": get_key(event, "previous_stage"),
                "new_stage": new_stage,
                "changed_by_email": "mock_api_seed",
                "changed_at": changed_at,
                "source": "mock_api_seed",
                "metadata": {
                    "mock_action": get_key(event, "action"),
                    "previous_status": get_key(event, "previous_status"),
                    "current_status": get_key(event, "current_status"),
                },
            }
        )

    return rows


def supabase_upsert(
    table_name: str,
    rows: list[dict[str, Any]],
    conflict_columns: str,
) -> int:
    if not rows:
        return 0

    total = 0

    for index in range(0, len(rows), UPSERT_BATCH_SIZE):
        batch = rows[index : index + UPSERT_BATCH_SIZE]
        query = urllib.parse.urlencode({"on_conflict": conflict_columns})
        url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/{table_name}?{query}"
        request = urllib.request.Request(
            url,
            data=json.dumps(batch, default=str).encode("utf-8"),
            headers={
                "apikey": SUPABASE_SERVICE_ROLE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Prefer": "resolution=merge-duplicates,return=minimal",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=60):
                total += len(batch)
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8")
            raise RuntimeError(
                f"Supabase upsert failed for {table_name}: {error.code} {detail}"
            ) from error
        except urllib.error.URLError as error:
            raise RuntimeError(
                f"Supabase upsert failed for {table_name}: {error.reason}"
            ) from error

    return total


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed Supabase operational tables from the Mock Greenhouse API."
    )
    parser.add_argument(
        "--display-fields-only",
        action="store_true",
        help=(
            "Only upsert display/business context columns on public.applications. "
            "Operational status, stage and event tables are not modified."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned changes without writing to Supabase.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    require_env_vars()

    print("Seeding Supabase operational tables from Mock Greenhouse API")
    print(f"Mock API base URL: {MOCK_API_BASE_URL}")
    print(f"Supabase URL: {SUPABASE_URL}")

    if args.display_fields_only:
        print(
            "Display-only enrichment mode: operational status/stage fields will "
            "not be modified."
        )
        print(
            "Display-only payload columns: "
            + ", ".join(DISPLAY_ONLY_APPLICATION_COLUMNS)
        )

    request_json(f"{MOCK_API_BASE_URL}/health")

    jobs = fetch_mock_paginated("/jobs")
    candidates = fetch_mock_paginated("/candidates")
    applications = fetch_mock_paginated("/applications")
    print(f"Applications fetched: {len(applications)}")

    job_context = build_job_context(jobs)
    candidate_context = build_candidate_context(candidates)

    if args.display_fields_only:
        display_rows = build_display_application_rows(
            applications,
            job_context,
            candidate_context,
        )
        print(f"Display rows prepared: {len(display_rows)}")

        if args.dry_run:
            print("Dry-run mode: no Supabase writes performed.")
            print("Display rows upserted: 0")
            return

        display_rows_upserted = supabase_upsert(
            table_name="applications",
            rows=display_rows,
            conflict_columns="application_id",
        )
        print(f"Display rows upserted: {display_rows_upserted}")
        print("Display-only enrichment completed successfully")
        return

    application_rows = build_application_rows(
        applications,
        job_context,
        candidate_context,
    )

    applications_upserted = supabase_upsert(
        table_name="applications",
        rows=application_rows,
        conflict_columns="application_id",
    )

    print(f"Applications inserted/updated: {applications_upserted}")

    try:
        events = fetch_mock_paginated("/application-events")
        print(f"Stage events fetched: {len(events)}")
    except RuntimeError as error:
        print(f"Skipping application_stage_events seed: {error}")
        events = []

    stage_event_rows = build_stage_event_rows(events)
    stage_events_upserted = supabase_upsert(
        table_name="application_stage_events",
        rows=stage_event_rows,
        conflict_columns="event_id",
    )

    print(f"Application stage events inserted/updated: {stage_events_upserted}")
    print("Supabase operational seed completed successfully")


if __name__ == "__main__":
    main()
