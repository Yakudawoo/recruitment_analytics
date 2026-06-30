import json
import os
import urllib.error
import urllib.parse
import urllib.request
from functools import lru_cache
from typing import Any

try:
    from streamlit_app.supabase_auth import get_current_supabase_access_token
except ModuleNotFoundError:
    from supabase_auth import get_current_supabase_access_token


BASE_APPLICATION_SELECT_COLUMNS = [
    "application_id",
    "candidate_id",
    "job_id",
    "status",
    "current_stage",
    "updated_at",
]
OPTIONAL_APPLICATION_DISPLAY_COLUMNS = [
    "candidate_full_name",
    "candidate_name",
    "job_title",
    "office_name",
    "department_name",
    "office",
    "department",
    "recruiter_name",
    "recruiter_email",
    "recruiter",
    "created_at",
]


def require_supabase_config() -> tuple[str, str]:
    supabase_url = os.getenv("SUPABASE_URL")
    anon_key = os.getenv("SUPABASE_ANON_KEY")

    if not supabase_url or not anon_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_ANON_KEY are required.")

    return supabase_url.rstrip("/"), anon_key


def supabase_rest_request(
    path: str,
    method: str = "GET",
    payload: dict[str, Any] | list[dict[str, Any]] | None = None,
    access_token: str | None = None,
    prefer: str | None = None,
) -> Any:
    supabase_url, anon_key = require_supabase_config()
    token = access_token or get_current_supabase_access_token()

    if not token:
        raise RuntimeError("Supabase access token is required.")

    headers = {
        "apikey": anon_key,
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    if payload is not None:
        headers["Content-Type"] = "application/json"

    if prefer:
        headers["Prefer"] = prefer

    request = urllib.request.Request(
        f"{supabase_url}/rest/v1/{path.lstrip('/')}",
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else None
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8")
        raise RuntimeError(f"Supabase REST request failed: {error.code} {detail}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Supabase REST request failed: {error.reason}") from error


def rpc(function_name: str, payload: dict[str, Any]) -> Any:
    return supabase_rest_request(
        f"rpc/{function_name}",
        method="POST",
        payload=payload,
    )


@lru_cache(maxsize=1)
def list_application_columns() -> set[str]:
    try:
        rows = supabase_rest_request("applications?select=*&limit=1") or []
    except RuntimeError:
        return set(BASE_APPLICATION_SELECT_COLUMNS)

    if not rows:
        return set(BASE_APPLICATION_SELECT_COLUMNS)

    return set(rows[0].keys())


def build_application_select_columns(include_display: bool = True) -> str:
    available_columns = list_application_columns()
    desired_columns = list(BASE_APPLICATION_SELECT_COLUMNS)

    if include_display:
        desired_columns.extend(OPTIONAL_APPLICATION_DISPLAY_COLUMNS)

    selected_columns = [
        column
        for column in desired_columns
        if column in available_columns or column in BASE_APPLICATION_SELECT_COLUMNS
    ]

    return ",".join(dict.fromkeys(selected_columns))


def get_current_user_roles() -> list[dict[str, Any]]:
    return supabase_rest_request(
        "app_user_roles?select=user_id,email,role,is_active&is_active=eq.true",
    ) or []


def create_stage_change_dry_run(
    target_stage: str,
    next_stage: str,
    selection_mode: str,
    requested_limit: int,
    reason: str,
    application_ids: list[int] | None = None,
) -> str:
    payload: dict[str, Any] = {
        "p_target_stage": target_stage,
        "p_next_stage": next_stage,
        "p_requested_limit": requested_limit,
        "p_selection_mode": selection_mode,
        "p_reason": reason,
    }

    if application_ids is not None:
        payload["p_application_ids"] = application_ids

    result = rpc("create_stage_change_dry_run", payload)

    if isinstance(result, str):
        return result

    if isinstance(result, list) and result:
        return str(result[0])

    return str(result)


def approve_stage_change_request(request_id: str) -> Any:
    return rpc(
        "approve_stage_change_request",
        {
            "p_request_id": request_id,
        },
    )


def apply_stage_change_request(request_id: str) -> Any:
    return rpc(
        "apply_stage_change_request",
        {
            "p_request_id": request_id,
        },
    )


def create_hiring_outcome_dry_run(
    selection_mode: str,
    requested_limit: int,
    reason: str,
    application_ids: list[int] | None = None,
) -> str:
    payload: dict[str, Any] = {
        "p_selection_mode": selection_mode,
        "p_requested_limit": requested_limit,
        "p_reason": reason,
    }

    if application_ids is not None:
        payload["p_application_ids"] = application_ids

    result = rpc("create_hiring_outcome_dry_run", payload)

    if isinstance(result, str):
        return result

    if isinstance(result, list) and result:
        return str(result[0])

    return str(result)


def approve_hiring_outcome_request(request_id: str) -> Any:
    return rpc(
        "approve_hiring_outcome_request",
        {
            "p_request_id": request_id,
        },
    )


def apply_hiring_outcome_request(request_id: str) -> Any:
    return rpc(
        "apply_hiring_outcome_request",
        {
            "p_request_id": request_id,
        },
    )


def create_rejection_outcome_dry_run(
    selection_mode: str,
    requested_limit: int,
    reason: str,
    application_ids: list[int] | None = None,
) -> str:
    payload: dict[str, Any] = {
        "p_selection_mode": selection_mode,
        "p_requested_limit": requested_limit,
        "p_reason": reason,
    }

    if application_ids is not None:
        payload["p_application_ids"] = application_ids

    result = rpc("create_rejection_outcome_dry_run", payload)

    if isinstance(result, str):
        return result

    if isinstance(result, list) and result:
        return str(result[0])

    return str(result)


def approve_rejection_outcome_request(request_id: str) -> Any:
    return rpc(
        "approve_rejection_outcome_request",
        {
            "p_request_id": request_id,
        },
    )


def apply_rejection_outcome_request(request_id: str) -> Any:
    return rpc(
        "apply_rejection_outcome_request",
        {
            "p_request_id": request_id,
        },
    )


def list_recent_stage_change_requests(limit: int = 10) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode(
        {
            "select": "*",
            "order": "requested_at.desc",
            "limit": str(limit),
        }
    )

    return supabase_rest_request(f"stage_change_requests?{query}") or []


def get_stage_change_request(request_id: str) -> dict[str, Any] | None:
    query = urllib.parse.urlencode(
        {
            "select": "*",
            "request_id": f"eq.{request_id}",
            "limit": "1",
        }
    )
    rows = supabase_rest_request(f"stage_change_requests?{query}") or []

    return rows[0] if rows else None


def list_recent_outcome_change_requests(
    limit: int = 10,
    outcome: str | None = None,
) -> list[dict[str, Any]]:
    params = {
        "select": "*",
        "order": "requested_at.desc",
        "limit": str(limit),
    }

    if outcome:
        params["outcome"] = f"eq.{outcome}"

    query = urllib.parse.urlencode(params)

    return supabase_rest_request(f"outcome_change_requests?{query}") or []


def get_outcome_change_request(request_id: str) -> dict[str, Any] | None:
    query = urllib.parse.urlencode(
        {
            "select": "*",
            "request_id": f"eq.{request_id}",
            "limit": "1",
        }
    )
    rows = supabase_rest_request(f"outcome_change_requests?{query}") or []

    return rows[0] if rows else None


def list_request_items(request_id: str) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode(
        {
            "select": "*",
            "request_id": f"eq.{request_id}",
            "order": "application_id.asc",
        }
    )

    return supabase_rest_request(f"stage_change_request_items?{query}") or []


def list_outcome_request_items(request_id: str) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode(
        {
            "select": "*",
            "request_id": f"eq.{request_id}",
            "order": "application_id.asc",
        }
    )

    return supabase_rest_request(f"outcome_change_request_items?{query}") or []


def build_applications_by_ids_query(application_ids: list[int]) -> str | None:
    if not application_ids:
        return None

    selected_ids = ",".join(str(application_id) for application_id in application_ids)
    query = urllib.parse.urlencode(
        {
            "select": build_application_select_columns(include_display=True),
            "application_id": f"in.({selected_ids})",
            "order": "application_id.asc",
        }
    )

    return f"applications?{query}"


def list_applications_by_ids(application_ids: list[int]) -> list[dict[str, Any]]:
    query = build_applications_by_ids_query(application_ids)

    if not query:
        return []

    return supabase_rest_request(query) or []


def list_applications(
    limit: int = 5000,
    page_size: int = 1000,
    status: str | None = None,
    stages: list[str] | set[str] | None = None,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    offset = 0
    safe_page_size = max(1, min(page_size, 1000))
    safe_limit = max(1, limit)
    stage_values = [stage for stage in stages or [] if stage]

    while len(records) < safe_limit:
        page_limit = min(safe_page_size, safe_limit - len(records))
        params = {
            "select": build_application_select_columns(include_display=True),
            "order": "updated_at.asc.nullslast,application_id.asc",
            "limit": str(page_limit),
            "offset": str(offset),
        }

        if status:
            params["status"] = f"eq.{status}"

        if stage_values:
            params["current_stage"] = f"in.({','.join(stage_values)})"

        query = urllib.parse.urlencode(params)
        page = supabase_rest_request(f"applications?{query}") or []

        if not page:
            break

        records.extend(page)
        offset += page_limit

        if len(page) < page_limit:
            break

    return records


def list_eligible_hiring_applications(limit: int = 500) -> list[dict[str, Any]]:
    return list_active_applications(limit=limit)


def list_active_applications(
    limit: int = 5000,
    page_size: int = 1000,
) -> list[dict[str, Any]]:
    return list_applications(limit=limit, page_size=page_size, status="active")


def list_active_applications_for_stages(
    stages: list[str] | set[str],
    limit: int = 5000,
) -> list[dict[str, Any]]:
    stage_values = [stage for stage in stages if stage]

    if not stage_values:
        return list_active_applications(limit=limit)

    stage_set = set(stage_values)
    return [
        application
        for application in list_active_applications(limit=limit)
        if application.get("current_stage") in stage_set
    ]


def log_admin_action(
    action: str,
    object_type: str | None = None,
    object_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> Any:
    return supabase_rest_request(
        "admin_audit_logs",
        method="POST",
        payload={
            "action": action,
            "object_type": object_type,
            "object_id": object_id,
            "payload": payload or {},
        },
        prefer="return=minimal",
    )
