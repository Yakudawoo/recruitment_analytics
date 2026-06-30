import json
import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import streamlit as st


REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATED_DATA_DIR = REPO_ROOT / "data" / "generated"
DEFAULT_TARGET_STAGE = "Reference Check"
DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"
FINAL_DEMO_STAGE = "Offer"
PLANNED_STAGE_SEQUENCE = (DEFAULT_TARGET_STAGE, FINAL_DEMO_STAGE)
FOCUSED_GROUP_MODE = "Focused group"
GLOBAL_IMPACT_MODE = "Global impact"


def get_demo_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _request_json(
    api_base_url: str,
    endpoint: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: int = 15,
) -> dict[str, Any]:
    base_url = api_base_url.rstrip("/")
    path = endpoint if endpoint.startswith("/") else f"/{endpoint}"
    url = f"{base_url}{path}"

    data = None
    headers = {"Accept": "application/json"}

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_body = response.read().decode("utf-8")
            return json.loads(response_body) if response_body else {}
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8")
        raise RuntimeError(f"{method} {url} failed: {error.code} {detail}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"{method} {url} failed: {error.reason}") from error


def fetch_paginated(api_base_url: str, endpoint: str, limit: int = 500) -> list[dict]:
    records: list[dict] = []
    offset = 0

    while True:
        separator = "&" if "?" in endpoint else "?"
        paged_endpoint = f"{endpoint}{separator}{urllib.parse.urlencode({'limit': limit, 'offset': offset})}"
        payload = _request_json(api_base_url, paged_endpoint)
        page_records = payload.get("data", [])

        records.extend(page_records)

        count = payload.get("count")
        offset += limit

        if not page_records:
            break

        if count is not None and offset >= int(count):
            break

        if len(page_records) < limit:
            break

    return records


def get_key(row: dict, *keys: str):
    for key in keys:
        value = row.get(key)

        if value is None:
            continue

        if str(value).strip().lower() == "(null)":
            continue

        return value

    return None


def build_job_context(jobs: list[dict]) -> dict[int, dict]:
    context: dict[int, dict] = {}

    for job in jobs:
        job_id = get_key(job, "ghjb_job_id", "job_id", "id")

        if job_id is None:
            continue

        context[int(job_id)] = {
            "job_id": int(job_id),
            "job_name": get_key(job, "ghjb_job_name", "job_name"),
            "recruiter": get_key(job, "ghjb_recruiter_name", "recruiter_name"),
            "office": get_key(job, "ghjb_gh_office_name", "office_name"),
            "department": get_key(job, "ghjb_gh_department_name", "department_name"),
        }

    return context


def _application_to_demo_record(application: dict, job_context: dict[int, dict]) -> dict:
    job_id = get_key(application, "ghap_job_id", "job_id")
    context = job_context.get(int(job_id), {}) if job_id is not None else {}

    return {
        "application_id": get_key(
            application,
            "ghap_application_id",
            "application_id",
            "id",
        ),
        "job_id": job_id,
        "current_stage": get_key(
            application,
            "ghap_application_current_stage",
            "current_stage",
        ),
        "status": get_key(application, "ghap_status", "status"),
        "recruiter": context.get("recruiter"),
        "office": context.get("office"),
        "department": context.get("department"),
        "job_name": context.get("job_name"),
    }


def select_demo_applications(
    applications,
    job_context,
    target_stage,
    requested_limit,
    selection_mode=FOCUSED_GROUP_MODE,
):
    candidates = []
    seen_application_ids = set()
    final_stage = PLANNED_STAGE_SEQUENCE[-1]

    for application in applications:
        current_stage = get_key(
            application,
            "ghap_application_current_stage",
            "current_stage",
        )
        status = get_key(application, "ghap_status", "status")
        application_id = get_key(
            application,
            "ghap_application_id",
            "application_id",
            "id",
        )
        job_id = get_key(application, "ghap_job_id", "job_id")

        if application_id is None or job_id is None:
            continue

        if application_id in seen_application_ids:
            continue

        if str(status).lower() != "active":
            continue

        if str(current_stage).strip().lower() == str(final_stage).strip().lower():
            continue

        if int(job_id) not in job_context:
            continue

        seen_application_ids.add(application_id)
        candidates.append(_application_to_demo_record(application, job_context))

    if selection_mode == GLOBAL_IMPACT_MODE:
        return {
            "selection_mode": selection_mode,
            "selected_scope": None,
            "applications": candidates[:requested_limit],
            "available_candidates": len(candidates),
            "selected_group_candidates": None,
        }

    grouped: dict[tuple[str, str, str], list[dict]] = defaultdict(list)

    for application in candidates:
        scope = (
            application.get("recruiter") or "Unknown recruiter",
            application.get("office") or "Unknown office",
            application.get("department") or "Unknown department",
        )
        grouped[scope].append(application)

    if not grouped:
        return {
            "selection_mode": selection_mode,
            "selected_scope": None,
            "applications": [],
            "available_candidates": 0,
            "selected_group_candidates": 0,
        }

    selected_scope_tuple, selected_applications = max(
        grouped.items(),
        key=lambda item: len(item[1]),
    )

    selected_scope = {
        "recruiter": selected_scope_tuple[0],
        "office": selected_scope_tuple[1],
        "department": selected_scope_tuple[2],
    }

    return {
        "selection_mode": selection_mode,
        "selected_scope": selected_scope,
        "applications": selected_applications[:requested_limit],
        "available_candidates": len(candidates),
        "selected_group_candidates": len(selected_applications),
    }


def apply_stage_changes(
    api_base_url,
    applications,
    target_stage,
    planned_stage_sequence=PLANNED_STAGE_SEQUENCE,
):
    results = []

    for application in applications:
        application_id = application["application_id"]
        for stage in planned_stage_sequence:
            endpoint = f"/applications/{application_id}/stage-change"
            payload = {
                "current_stage": stage,
                "new_stage": stage,
            }

            try:
                response = _request_json(
                    api_base_url,
                    endpoint,
                    method="POST",
                    payload=payload,
                )
                results.append(
                    {
                        "application_id": application_id,
                        "stage": stage,
                        "success": True,
                        "response": response,
                    }
                )
            except RuntimeError as error:
                results.append(
                    {
                        "application_id": application_id,
                        "stage": stage,
                        "success": False,
                        "error": str(error),
                    }
                )

    return results


def write_audit_payload(
    mode,
    target_stage,
    limit,
    selected_scope,
    applications,
    selection_mode=FOCUSED_GROUP_MODE,
    available_candidates=0,
    planned_stage_sequence=PLANNED_STAGE_SEQUENCE,
    api_results=None,
):
    GENERATED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = GENERATED_DATA_DIR / f"api_demo_stage_change_{timestamp}_{mode}.json"

    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "selection_mode": selection_mode,
        "target_stage": target_stage,
        "planned_stage_sequence": list(planned_stage_sequence),
        "limit": limit,
        "selected_scope": selected_scope,
        "eligible_applications_found": available_candidates,
        "application_count": len(applications),
        "expected_new_api_events": len(applications) * len(planned_stage_sequence),
        "application_ids": [application["application_id"] for application in applications],
        "applications": applications,
        "api_results": api_results or [],
    }

    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    return path


def _load_demo_selection(
    api_base_url: str,
    target_stage: str,
    limit: int,
    selection_mode: str,
) -> dict:
    _request_json(api_base_url, "/health")

    jobs = fetch_paginated(api_base_url, "/jobs")
    applications = fetch_paginated(api_base_url, "/applications")
    job_context = build_job_context(jobs)

    return select_demo_applications(
        applications,
        job_context,
        target_stage,
        limit,
        selection_mode,
    )


def _build_scope_breakdown(applications: list[dict]) -> dict[str, int]:
    breakdown: dict[str, int] = defaultdict(int)

    for application in applications:
        key = " / ".join(
            [
                application.get("recruiter") or "Unknown recruiter",
                application.get("office") or "Unknown office",
                application.get("department") or "Unknown department",
            ]
        )
        breakdown[key] += 1

    return dict(
        sorted(
            breakdown.items(),
            key=lambda item: item[1],
            reverse=True,
        )
    )


def _render_selection_result(selection: dict, audit_path: Path, requested_limit: int):
    selected_scope = selection["selected_scope"] or {}
    applications = selection["applications"]
    selection_mode = selection.get("selection_mode", FOCUSED_GROUP_MODE)

    st.write("Selection summary")
    summary = {
        "Requested limit": requested_limit,
        "Eligible applications found": selection.get("available_candidates", 0),
        "Selected applications": len(applications),
        "Selection mode": selection_mode,
        "Expected new API events": len(applications) * len(PLANNED_STAGE_SEQUENCE),
    }

    if selection_mode == FOCUSED_GROUP_MODE:
        summary["Eligible applications in selected group"] = selection.get(
            "selected_group_candidates",
            0,
        )

    st.json(summary)

    if selection_mode == FOCUSED_GROUP_MODE:
        st.write("Selected scope")
        st.json(selected_scope)
    else:
        st.write("Breakdown by recruiter / office / department")
        st.json(_build_scope_breakdown(applications))

    st.write("First 10 application IDs")
    st.code(", ".join(str(app["application_id"]) for app in applications[:10]))
    st.caption(f"Audit file: {audit_path}")


def render_demo_controls():
    if not get_demo_flag("ENABLE_DEMO_MUTATION"):
        return

    with st.sidebar.expander("Local API simulation demo", expanded=False):
        st.warning(
            "Local demo controls only. Hidden by default on the public Hugging Face dashboard."
        )

        api_base_url = st.text_input(
            "Mock API base URL",
            value=os.getenv("MOCK_API_BASE_URL", DEFAULT_API_BASE_URL),
        )
        target_stage = st.text_input("Target stage", value=DEFAULT_TARGET_STAGE)
        st.caption(f"Planned stage sequence: {' -> '.join(PLANNED_STAGE_SEQUENCE)}")
        selection_mode = st.radio(
            "Demo selection mode",
            [FOCUSED_GROUP_MODE, GLOBAL_IMPACT_MODE],
        )
        if selection_mode == FOCUSED_GROUP_MODE:
            st.caption("Best for showing a scoped dashboard impact with filters.")
        else:
            st.caption("Best for making KPI changes more visible across the full dashboard.")
        limit = st.number_input(
            "Application limit",
            min_value=10,
            max_value=500,
            value=100,
            step=10,
            help="This is a maximum. The actual selected count depends on eligible applications.",
        )

        if st.button("Dry-run API simulation"):
            try:
                selection = _load_demo_selection(
                    api_base_url,
                    target_stage,
                    int(limit),
                    selection_mode,
                )
                audit_path = write_audit_payload(
                    mode="dry_run",
                    target_stage=target_stage,
                    limit=int(limit),
                    selected_scope=selection["selected_scope"],
                    applications=selection["applications"],
                    selection_mode=selection_mode,
                    available_candidates=selection["available_candidates"],
                )

                if selection["applications"]:
                    st.success("Dry-run completed without mutating the Mock API.")
                else:
                    st.info("No active applications eligible for this target stage.")

                _render_selection_result(selection, audit_path, int(limit))
            except RuntimeError as error:
                st.error(str(error))

        if st.button("Apply API simulation"):
            try:
                selection = _load_demo_selection(
                    api_base_url,
                    target_stage,
                    int(limit),
                    selection_mode,
                )

                if not selection["applications"]:
                    audit_path = write_audit_payload(
                        mode="applied",
                        target_stage=target_stage,
                        limit=int(limit),
                        selected_scope=selection["selected_scope"],
                        applications=selection["applications"],
                        selection_mode=selection_mode,
                        available_candidates=selection["available_candidates"],
                    )
                    st.info("No active applications eligible for this target stage.")
                    _render_selection_result(selection, audit_path, int(limit))
                    return

                api_results = apply_stage_changes(
                    api_base_url,
                    selection["applications"],
                    target_stage,
                )
                audit_path = write_audit_payload(
                    mode="applied",
                    target_stage=target_stage,
                    limit=int(limit),
                    selected_scope=selection["selected_scope"],
                    applications=selection["applications"],
                    selection_mode=selection_mode,
                    available_candidates=selection["available_candidates"],
                    api_results=api_results,
                )

                success_count = sum(1 for result in api_results if result["success"])
                st.success(f"API simulation applied with {success_count} stage-change events.")
                _render_selection_result(selection, audit_path, int(limit))
            except RuntimeError as error:
                st.error(str(error))

        if get_demo_flag("ALLOW_LOCAL_PIPELINE_TRIGGER"):
            st.warning(
                "This demo writes to *_demo BigQuery datasets only. Production marts are not modified."
            )

            if st.button("Run local ELT pipeline"):
                try:
                    result = subprocess.run(
                        ["./scripts/run_recruitment_pipeline_demo.sh"],
                        cwd=REPO_ROOT,
                        capture_output=True,
                        text=True,
                        timeout=600,
                        check=False,
                    )
                    st.code(result.stdout or "(no stdout)", language="bash")

                    if result.stderr:
                        st.code(result.stderr, language="bash")

                    if result.returncode == 0:
                        st.success("Local ELT pipeline completed successfully.")
                    else:
                        st.error(
                            f"Local ELT pipeline failed with exit code {result.returncode}."
                        )
                except subprocess.TimeoutExpired as error:
                    st.error("Local ELT pipeline timed out after 10 minutes.")
                    if error.stdout:
                        st.code(error.stdout, language="bash")
                    if error.stderr:
                        st.code(error.stderr, language="bash")
        else:
            st.info(
                "Pipeline trigger is disabled. Run the pipeline manually through "
                "Airflow or ./scripts/run_recruitment_pipeline_demo.sh, or set "
                "ALLOW_LOCAL_PIPELINE_TRIGGER=true locally."
            )
