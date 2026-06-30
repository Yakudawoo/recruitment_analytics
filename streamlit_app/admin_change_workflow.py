import json
import os
import re
import ssl
import subprocess
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import streamlit as st

try:
    from streamlit_app import supabase_operational_source as supabase_ops
    from streamlit_app.demo_controls import (
        DEFAULT_API_BASE_URL,
        FOCUSED_GROUP_MODE,
        GLOBAL_IMPACT_MODE,
        _build_scope_breakdown,
        _request_json,
        build_job_context,
        fetch_paginated,
        get_key,
    )
    from streamlit_app.supabase_auth import render_supabase_auth_panel
except ModuleNotFoundError:
    import supabase_operational_source as supabase_ops
    from demo_controls import (
        DEFAULT_API_BASE_URL,
        FOCUSED_GROUP_MODE,
        GLOBAL_IMPACT_MODE,
        _build_scope_breakdown,
        _request_json,
        build_job_context,
        fetch_paginated,
        get_key,
    )
    from supabase_auth import render_supabase_auth_panel


REPO_ROOT = Path(__file__).resolve().parents[1]
ADMIN_REPORT_DIR = REPO_ROOT / "data" / "generated" / "admin_change_requests"

DEFAULT_TARGET_STAGE = "Reference Check"
DEFAULT_NEXT_STAGE = "Offer"
DEFAULT_AIRFLOW_API_BASE_URL = "http://localhost:8080"
DEMO_AIRFLOW_DAG_ID = "supabase_recruitment_analytics_demo_pipeline"
DEMO_DATASETS = {
    "raw_dataset": "raw_greenhouse_demo",
    "stg_dataset": "stg_greenhouse_demo",
    "core_dataset": "core_greenhouse_demo",
    "marts_dataset": "marts_recruitment_demo",
    "bq_location": "EU",
}
AIRFLOW_AUTO_MONITORING_AVAILABLE = False
AIRFLOW_TERMINAL_STATES = {"success", "failed", "error", "canceled"}
AIRFLOW_ACTIVE_STATES = {"queued", "running"}
HIRING_OUTCOME_STAGES = {
    "Offer",
    "Reference Check",
    "Final Interview",
    "Final (Executive) Interview",
}
REJECTION_OUTCOME_STAGES = {
    "Application Review",
    "Recruiter Interview",
    "Hiring Manager Review",
    "Hiring Manager Interview",
    "Take Home Test",
    "Face to Face",
    "HR Interview",
    "Final Interview",
    "Final (Executive) Interview",
    "Reference Check",
    "Offer",
}
REJECTION_REASON_OPTIONS = [
    "Reference check inconclusive",
    "Candidate not selected after interview",
    "Take Home test inconclusive",
    "Role requirements mismatch",
    "Process stopped by hiring team",
    "Other",
]
ALLOWED_RECRUITMENT_STAGES = [
    "Application Review",
    "AI Recommendation Review",
    "Recruiter Interview",
    "Hiring Manager Review",
    "Hiring Manager Interview",
    "Take Home Test",
    "Face to Face",
    "HR Interview",
    "Final Interview",
    "Final (Executive) Interview",
    "Reference Check",
    "Offer",
]

SUPPORTED_ROLES = {
    "super_admin",
    "dev_admin",
    "hr_manager",
    "business_manager",
    "analyst_readonly",
}


def get_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def get_airflow_dag_id() -> str:
    return os.getenv("AIRFLOW_DAG_ID", DEMO_AIRFLOW_DAG_ID).strip()


def is_airflow_trigger_available() -> bool:
    return (
        get_flag("ENABLE_ADMIN_AIRFLOW_TRIGGER")
        and get_flag("USE_SUPABASE_OPERATIONAL_SOURCE")
        and get_flag("ENABLE_ADMIN_CHANGE_WORKFLOW")
        and os.getenv("BQ_MARTS_DATASET", "marts_recruitment") == "marts_recruitment_demo"
        and get_airflow_dag_id() == DEMO_AIRFLOW_DAG_ID
    )


def get_airflow_api_base_url() -> str:
    base_url = os.getenv(
        "AIRFLOW_API_BASE_URL",
        DEFAULT_AIRFLOW_API_BASE_URL,
    ).strip().rstrip("/")
    parsed_url = urllib.parse.urlparse(base_url)
    hostname = (parsed_url.hostname or "").lower()
    is_localhost = hostname in {"localhost", "127.0.0.1", "::1"}
    is_hugging_face = any(
        os.getenv(name)
        for name in ["SPACE_ID", "SPACE_HOST", "HF_SPACE_ID", "HUGGING_FACE_SPACE_ID"]
    )

    if not parsed_url.scheme or not parsed_url.netloc:
        raise RuntimeError(
            "AIRFLOW_API_BASE_URL must be the public ngrok HTTPS base URL, "
            "for example https://xxxxx.ngrok-free.dev"
        )

    if parsed_url.path.rstrip("/") in {"/auth/token", "/api/v2"}:
        raise RuntimeError(
            "AIRFLOW_API_BASE_URL must be the public ngrok HTTPS base URL, "
            "for example https://xxxxx.ngrok-free.dev"
        )

    if is_hugging_face and is_localhost:
        raise RuntimeError(
            "AIRFLOW_API_BASE_URL cannot point to localhost from Hugging Face. "
            "AIRFLOW_API_BASE_URL must be the public ngrok HTTPS base URL, "
            "for example https://xxxxx.ngrok-free.dev"
        )

    if parsed_url.scheme != "https" and (is_hugging_face or not is_localhost):
        raise RuntimeError(
            "AIRFLOW_API_BASE_URL must be the public ngrok HTTPS base URL, "
            "for example https://xxxxx.ngrok-free.dev"
        )

    return base_url


def airflow_unreachable_message() -> str:
    return (
        "Airflow API is unreachable through the configured HTTPS tunnel. Check "
        "that ngrok is online, the forwarding URL is current, and "
        "AIRFLOW_API_BASE_URL points to the public HTTPS ngrok URL."
    )


def is_ssl_url_error(error: urllib.error.URLError) -> bool:
    reason = error.reason

    return isinstance(reason, ssl.SSLError) or "ssl" in str(reason).lower()


def get_airflow_base_headers(content_type: str = "application/json") -> dict[str, str]:
    return {
        "Accept": "application/json",
        "Content-Type": content_type,
        "ngrok-skip-browser-warning": "true",
    }


def redact_airflow_secret_text(value: str) -> str:
    redacted = re.sub(
        r'("(?:access_token|token)"\s*:\s*")[^"]+(")',
        r"\1***redacted***\2",
        value,
        flags=re.IGNORECASE,
    )
    redacted = re.sub(
        r"(Bearer\s+)[A-Za-z0-9._~+/=-]+",
        r"\1***redacted***",
        redacted,
        flags=re.IGNORECASE,
    )

    return redacted


def sanitize_airflow_response_debug(
    status_code: int | None,
    body_text: str,
    parsed_body: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "status_code": status_code,
        "response_json_keys": sorted(parsed_body.keys()) if parsed_body else [],
        "response_text_first_300_chars": redact_airflow_secret_text(body_text)[:300],
    }


def store_airflow_debug_value(key: str, value: Any):
    st.session_state[key] = value


def request_airflow_token(
    payload_data: bytes,
    content_type: str,
) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{get_airflow_api_base_url()}/auth/token",
        data=payload_data,
        headers=get_airflow_base_headers(content_type),
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
            status_code = getattr(response, "status", None)
            try:
                parsed_body = json.loads(body) if body else {}
            except json.JSONDecodeError:
                parsed_body = {}
            store_airflow_debug_value("airflow_last_auth_status_code", status_code)
            store_airflow_debug_value(
                "airflow_last_auth_debug",
                sanitize_airflow_response_debug(status_code, body, parsed_body),
            )
            return parsed_body
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8")
        parsed_detail = None

        try:
            parsed_detail = json.loads(detail) if detail else None
        except json.JSONDecodeError:
            parsed_detail = None

        store_airflow_debug_value("airflow_last_auth_status_code", error.code)
        store_airflow_debug_value(
            "airflow_last_auth_debug",
            sanitize_airflow_response_debug(error.code, detail, parsed_detail),
        )
        raise RuntimeError(f"{error.code} {detail}") from error
    except urllib.error.URLError as error:
        if is_ssl_url_error(error):
            raise RuntimeError(airflow_unreachable_message()) from error
        raise RuntimeError(str(error.reason)) from error


def normalize_bearer_token(raw_token: str) -> str:
    token = raw_token.strip()

    if token.lower().startswith("bearer "):
        return token[7:].strip()

    return token


def get_airflow_access_token(force_refresh: bool = False) -> str:
    bearer_token = os.getenv("AIRFLOW_BEARER_TOKEN", "").strip()

    if bearer_token:
        token = normalize_bearer_token(bearer_token)
        st.session_state["airflow_access_token"] = token
        st.session_state["airflow_token_source"] = "env"
        return token

    cached_token = st.session_state.get("airflow_access_token")

    if cached_token and not force_refresh:
        st.session_state["airflow_token_source"] = "session"
        return str(cached_token)

    username = os.getenv("AIRFLOW_USERNAME", "").strip()
    password = os.getenv("AIRFLOW_PASSWORD", "")

    if not username or not password:
        raise RuntimeError(
            "Airflow authentication failed. Configure AIRFLOW_BEARER_TOKEN or "
            "AIRFLOW_USERNAME and AIRFLOW_PASSWORD."
        )

    token_payload = {
        "username": username,
        "password": password,
    }
    errors = []

    try:
        response = request_airflow_token(
            json.dumps(token_payload).encode("utf-8"),
            "application/json",
        )
    except RuntimeError as error:
        errors.append(str(error))
    else:
        access_token = response.get("access_token") or response.get("token")

        if access_token:
            token = normalize_bearer_token(str(access_token))
            st.session_state["airflow_access_token"] = token
            st.session_state["airflow_token_source"] = "/auth/token"
            return token

        errors.append("JSON token response did not include access_token or token")

    try:
        response = request_airflow_token(
            urllib.parse.urlencode(token_payload).encode("utf-8"),
            "application/x-www-form-urlencoded",
        )
    except RuntimeError as error:
        errors.append(str(error))
    else:
        access_token = response.get("access_token") or response.get("token")

        if access_token:
            token = normalize_bearer_token(str(access_token))
            st.session_state["airflow_access_token"] = token
            st.session_state["airflow_token_source"] = "/auth/token"
            return token

        errors.append("Form token response did not include access_token or token")

    st.session_state["airflow_last_auth_errors"] = errors
    raise RuntimeError(
        "Airflow authentication failed. Could not retrieve Airflow access token."
    )


def get_airflow_api_headers(force_refresh_token: bool = False) -> dict[str, str]:
    headers = get_airflow_base_headers()
    headers["Authorization"] = f"Bearer {get_airflow_access_token(force_refresh_token)}"

    return headers


def airflow_api_request(
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    debug_status_key: str | None = None,
    allow_auth_retry: bool = True,
) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{get_airflow_api_base_url()}{path}",
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers=get_airflow_api_headers(),
        method=method,
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
            status_code = getattr(response, "status", None)

            if debug_status_key:
                store_airflow_debug_value(debug_status_key, status_code)

            if not body:
                return {}

            try:
                return json.loads(body)
            except json.JSONDecodeError:
                return {
                    "_response_text_first_300_chars": redact_airflow_secret_text(body)[
                        :300
                    ]
                }
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8")

        if debug_status_key:
            store_airflow_debug_value(debug_status_key, error.code)

        if error.code in {401, 403} and allow_auth_retry:
            retry_request = urllib.request.Request(
                f"{get_airflow_api_base_url()}{path}",
                data=json.dumps(payload).encode("utf-8") if payload is not None else None,
                headers=get_airflow_api_headers(force_refresh_token=True),
                method=method,
            )

            try:
                with urllib.request.urlopen(retry_request, timeout=30) as response:
                    body = response.read().decode("utf-8")
                    status_code = getattr(response, "status", None)

                    if debug_status_key:
                        store_airflow_debug_value(debug_status_key, status_code)

                    return json.loads(body) if body else {}
            except urllib.error.HTTPError as retry_error:
                detail = retry_error.read().decode("utf-8")

                if debug_status_key:
                    store_airflow_debug_value(debug_status_key, retry_error.code)

                raise RuntimeError(f"{retry_error.code} {detail}") from retry_error
            except urllib.error.URLError as retry_error:
                if is_ssl_url_error(retry_error):
                    raise RuntimeError(airflow_unreachable_message()) from retry_error
                raise RuntimeError(str(retry_error.reason)) from retry_error

        if error.code == 422:
            raise RuntimeError(
                "Airflow rejected the DAG trigger payload. Check logical_date "
                f"and dag_run_id. {detail}"
            ) from error
        raise RuntimeError(f"{error.code} {detail}") from error
    except urllib.error.URLError as error:
        if is_ssl_url_error(error):
            raise RuntimeError(airflow_unreachable_message()) from error
        raise RuntimeError(str(error.reason)) from error


def build_airflow_demo_conf(user_email: str) -> dict[str, Any]:
    return {
        "source": "streamlit_admin",
        "pipeline": "supabase_demo",
        **DEMO_DATASETS,
        "triggered_by_email": user_email,
        "reason": "Admin analytics refresh after Supabase operational changes",
    }


def build_airflow_dag_run_payload(user_email: str) -> dict[str, Any]:
    triggered_at = datetime.now(timezone.utc).replace(microsecond=0)
    logical_date = triggered_at.isoformat().replace("+00:00", "Z")
    dag_run_id = f"streamlit_admin_{triggered_at.strftime('%Y%m%dT%H%M%SZ')}"

    return {
        "dag_run_id": dag_run_id,
        "logical_date": logical_date,
        "conf": build_airflow_demo_conf(user_email),
    }


def trigger_airflow_demo_dag(user_email: str) -> dict[str, Any]:
    dag_id = get_airflow_dag_id()

    if dag_id != DEMO_AIRFLOW_DAG_ID:
        raise RuntimeError(
            f"Refusing to trigger non-demo DAG: {dag_id}. "
            f"Expected {DEMO_AIRFLOW_DAG_ID}."
        )

    return airflow_api_request(
        "POST",
        f"/api/v2/dags/{dag_id}/dagRuns",
        payload=build_airflow_dag_run_payload(user_email),
        debug_status_key="airflow_last_trigger_status_code",
    )


def get_airflow_demo_run_status(dag_run_id: str) -> dict[str, Any]:
    dag_id = get_airflow_dag_id()

    if dag_id != DEMO_AIRFLOW_DAG_ID:
        raise RuntimeError(
            f"Refusing to inspect non-demo DAG: {dag_id}. "
            f"Expected {DEMO_AIRFLOW_DAG_ID}."
        )

    return airflow_api_request(
        "GET",
        f"/api/v2/dags/{dag_id}/dagRuns/{urllib.parse.quote(dag_run_id, safe='')}",
        debug_status_key="airflow_last_status_check_status_code",
    )


def get_airflow_monitoring_strategy() -> str:
    return "st.fragment(run_every=10s)" if AIRFLOW_AUTO_MONITORING_AVAILABLE else "manual fallback"


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def format_elapsed_time(started_at: str | None) -> str:
    started = parse_iso_datetime(started_at)

    if not started:
        return "N/A"

    elapsed_seconds = max(
        0,
        int((datetime.now(timezone.utc) - started).total_seconds()),
    )
    minutes, seconds = divmod(elapsed_seconds, 60)

    return f"{minutes}m {seconds:02d}s"


def update_airflow_monitoring_state(response: dict[str, Any]) -> str:
    state = str(response.get("state") or "unknown")
    checked_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    st.session_state["airflow_last_dag_run_id"] = response.get(
        "dag_run_id",
        st.session_state.get("airflow_last_dag_run_id"),
    )
    st.session_state["airflow_demo_dag_run_id"] = st.session_state.get(
        "airflow_last_dag_run_id"
    )
    st.session_state["airflow_last_state"] = state
    st.session_state["airflow_last_checked_at"] = checked_at
    st.session_state["airflow_last_response"] = response

    if state in AIRFLOW_TERMINAL_STATES:
        st.session_state["airflow_monitoring_enabled"] = False

    return state


def check_airflow_status_once(dag_run_id: str) -> dict[str, Any]:
    response = get_airflow_demo_run_status(dag_run_id)
    update_airflow_monitoring_state(response)
    return response


def sanitize_airflow_base_url_for_debug() -> str:
    try:
        parsed_url = urllib.parse.urlparse(get_airflow_api_base_url())
    except RuntimeError as error:
        return f"Invalid AIRFLOW_API_BASE_URL: {error}"

    netloc = parsed_url.hostname or ""

    if parsed_url.port:
        netloc = f"{netloc}:{parsed_url.port}"

    return urllib.parse.urlunparse(
        (
            parsed_url.scheme,
            netloc,
            parsed_url.path.rstrip("/"),
            "",
            "",
            "",
        )
    )


def render_airflow_api_debug():
    dag_id = get_airflow_dag_id()
    dag_run_id = st.session_state.get("airflow_last_dag_run_id") or st.session_state.get(
        "airflow_demo_dag_run_id"
    )
    status_endpoint = (
        f"/api/v2/dags/{dag_id}/dagRuns/{urllib.parse.quote(str(dag_run_id), safe='')}"
        if dag_run_id
        else None
    )

    with st.expander("Airflow API debug", expanded=False):
        st.json(
            {
                "AIRFLOW_API_BASE_URL": sanitize_airflow_base_url_for_debug(),
                "AIRFLOW_DAG_ID": dag_id,
                "auth_endpoint_path": "/auth/token",
                "dag_trigger_endpoint_path": f"/api/v2/dags/{dag_id}/dagRuns",
                "status_endpoint_path": status_endpoint,
                "last_auth_status_code": st.session_state.get(
                    "airflow_last_auth_status_code"
                ),
                "last_trigger_status_code": st.session_state.get(
                    "airflow_last_trigger_status_code"
                ),
                "last_status_check_status_code": st.session_state.get(
                    "airflow_last_status_check_status_code"
                ),
                "last_dag_run_id": dag_run_id,
                "token_source": st.session_state.get("airflow_token_source"),
            }
        )

        if st.session_state.get("airflow_last_auth_debug"):
            st.caption("Last auth response debug")
            st.json(st.session_state["airflow_last_auth_debug"])

        if st.session_state.get("airflow_last_status_error"):
            st.caption("Last status monitoring error")
            st.code(st.session_state["airflow_last_status_error"], language=None)


def render_airflow_status_panel():
    dag_run_id = st.session_state.get("airflow_last_dag_run_id") or st.session_state.get(
        "airflow_demo_dag_run_id"
    )

    if not dag_run_id:
        render_airflow_api_debug()
        return

    state = st.session_state.get("airflow_last_state", "unknown")
    last_checked_at = st.session_state.get("airflow_last_checked_at")
    started_at = st.session_state.get("airflow_started_at")
    monitoring_enabled = bool(st.session_state.get("airflow_monitoring_enabled"))

    st.write("Airflow analytics refresh status")
    status_col, action_col = st.columns([2, 1])

    with status_col:
        st.json(
            {
                "dag_id": DEMO_AIRFLOW_DAG_ID,
                "dag_run_id": dag_run_id,
                "state": state,
                "last_checked_at": last_checked_at or "Not checked yet",
                "elapsed_time": format_elapsed_time(started_at),
                "monitoring": "enabled" if monitoring_enabled else "stopped",
                "monitoring_strategy": get_airflow_monitoring_strategy(),
            }
        )

    with action_col:
        if monitoring_enabled:
            if st.button("Stop monitoring Airflow run"):
                st.session_state["airflow_monitoring_enabled"] = False
                st.rerun()
        else:
            if state not in AIRFLOW_TERMINAL_STATES and st.button("Resume monitoring"):
                st.session_state["airflow_monitoring_enabled"] = True
                st.rerun()

    if state == "success":
        st.success(
            "Airflow analytics refresh completed. You can now click Refresh BigQuery data."
        )
        st.info("Next step: click Refresh BigQuery data.")
    elif state in {"failed", "error"}:
        st.error("Airflow analytics refresh failed. Open Airflow logs for details.")
        with st.expander("Airflow DAG run debug payload"):
            st.json(st.session_state.get("airflow_last_response", {}))
    elif state == "canceled":
        st.error("Airflow analytics refresh was canceled. Open Airflow logs for details.")
        with st.expander("Airflow DAG run debug payload"):
            st.json(st.session_state.get("airflow_last_response", {}))
    elif monitoring_enabled and state in AIRFLOW_ACTIVE_STATES | {"unknown"}:
        st.info("Monitoring Airflow run automatically every 10 seconds.")


def render_airflow_manual_status_check():
    dag_run_id = st.session_state.get("airflow_last_dag_run_id") or st.session_state.get(
        "airflow_demo_dag_run_id"
    )

    if not dag_run_id:
        return

    if st.button("Check Airflow run status"):
        try:
            check_airflow_status_once(dag_run_id)
            st.session_state.pop("airflow_last_status_error", None)
            st.rerun()
        except RuntimeError as error:
            st.session_state["airflow_last_status_error"] = str(error)
            st.warning(
                "DAG was triggered, but Streamlit could not retrieve the latest status."
            )


def render_airflow_status_monitor_once():
    dag_run_id = st.session_state.get("airflow_last_dag_run_id") or st.session_state.get(
        "airflow_demo_dag_run_id"
    )

    if not dag_run_id or not st.session_state.get("airflow_monitoring_enabled"):
        return

    state = st.session_state.get("airflow_last_state")

    if state in AIRFLOW_TERMINAL_STATES:
        st.session_state["airflow_monitoring_enabled"] = False
        return

    try:
        check_airflow_status_once(dag_run_id)
        st.session_state.pop("airflow_last_status_error", None)
    except RuntimeError as error:
        st.session_state["airflow_last_status_error"] = str(error)
        st.warning(
            "DAG was triggered, but Streamlit could not retrieve the latest status."
        )
        return

    render_airflow_status_panel()


try:
    if hasattr(st, "fragment"):

        @st.fragment(run_every="10s")
        def render_airflow_auto_monitor_fragment():
            render_airflow_status_monitor_once()

        AIRFLOW_AUTO_MONITORING_AVAILABLE = True

    else:

        def render_airflow_auto_monitor_fragment():
            if st.session_state.get("airflow_monitoring_enabled"):
                st.info(
                    "Automatic polling requires a Streamlit version with st.fragment. "
                    "Use the manual status check fallback below."
                )
except TypeError:

    def render_airflow_auto_monitor_fragment():
        if st.session_state.get("airflow_monitoring_enabled"):
            st.info(
                "Automatic polling requires Streamlit st.fragment(run_every=...). "
                "Use the manual status check fallback below."
            )


def get_float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def get_int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_allowed_emails() -> set[str]:
    raw_value = os.getenv("ADMIN_ALLOWED_EMAILS", "")

    return {
        email.strip().lower()
        for email in raw_value.split(",")
        if email.strip()
    }


def parse_role_map() -> dict[str, str]:
    raw_value = os.getenv("ADMIN_ROLE_MAP_JSON", "").strip()

    if not raw_value:
        return {}

    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        return {}

    role_map = {}

    for email, role in parsed.items():
        normalized_role = str(role).strip()

        if normalized_role not in SUPPORTED_ROLES:
            normalized_role = "analyst_readonly"

        role_map[str(email).strip().lower()] = normalized_role

    return role_map


def get_role(email: str) -> str:
    return parse_role_map().get(email.lower(), "analyst_readonly")


def can_dry_run(role: str) -> bool:
    return role in {"super_admin", "dev_admin", "hr_manager", "business_manager"}


def can_approve(role: str) -> bool:
    return role in {"super_admin", "dev_admin", "hr_manager", "business_manager"}


def can_apply(role: str) -> bool:
    if role == "super_admin":
        return True

    if role == "dev_admin":
        return True

    if role == "hr_manager":
        return get_flag("ALLOW_HR_MANAGER_APPLY")

    if role == "business_manager":
        return get_flag("ALLOW_BUSINESS_MANAGER_APPLY")

    return False


def authenticate(email: str, password: str, otp: str) -> tuple[bool, str]:
    normalized_email = email.strip().lower()
    allowed_emails = parse_allowed_emails()

    if not allowed_emails:
        return False, "ADMIN_ALLOWED_EMAILS is not configured."

    if normalized_email not in allowed_emails:
        return False, "Email is not authorized for the admin workflow."

    expected_password = os.getenv("ADMIN_DEMO_PASSWORD")

    if expected_password and password != expected_password:
        return False, "Invalid demo password."

    if get_flag("ADMIN_REQUIRE_OTP", default=True):
        expected_otp = os.getenv("ADMIN_DEMO_OTP")

        if not expected_otp:
            return False, "ADMIN_DEMO_OTP is required but not configured."

        if otp != expected_otp:
            return False, "Invalid demo OTP."

    return True, "Authenticated."


def get_source_api_base_url() -> str | None:
    real_api_enabled = get_flag("REAL_GREENHOUSE_API_ENABLED")

    if not real_api_enabled:
        return os.getenv("MOCK_API_BASE_URL", DEFAULT_API_BASE_URL)

    if not os.getenv("GREENHOUSE_API_KEY"):
        st.error(
            "REAL_GREENHOUSE_API_ENABLED=true requires GREENHOUSE_API_KEY or an "
            "equivalent auth configuration. Refusing to run."
        )
        return None

    st.error(
        "Real Greenhouse API execution is intentionally not implemented in this demo. "
        "Disable REAL_GREENHOUSE_API_ENABLED to use the Mock Greenhouse API."
    )
    return None


def normalize_stage_sequence(target_stage: str, next_stage: str) -> list[str]:
    stages = []

    for stage in [target_stage, next_stage]:
        normalized_stage = stage.strip()

        if normalized_stage and normalized_stage not in stages:
            stages.append(normalized_stage)

    return stages


def application_to_admin_record(application: dict, job_context: dict[int, dict]) -> dict:
    job_id = get_key(application, "ghap_job_id", "job_id")
    context = job_context.get(int(job_id), {}) if job_id is not None else {}

    current_stage = get_key(
        application,
        "ghap_application_current_stage",
        "current_stage",
    )

    return {
        "application_id": get_key(
            application,
            "ghap_application_id",
            "application_id",
            "id",
        ),
        "job_id": job_id,
        "status": get_key(application, "ghap_status", "status"),
        "previous_stage": current_stage,
        "current_stage": current_stage,
        "recruiter": context.get("recruiter"),
        "office": context.get("office"),
        "department": context.get("department"),
        "job_name": context.get("job_name"),
    }


def select_admin_applications(
    applications: list[dict],
    job_context: dict[int, dict],
    planned_stage_sequence: list[str],
    requested_limit: int,
    selection_mode: str,
) -> dict:
    candidates = []
    seen_application_ids = set()
    final_stage = planned_stage_sequence[-1] if planned_stage_sequence else None

    for application in applications:
        application_id = get_key(
            application,
            "ghap_application_id",
            "application_id",
            "id",
        )
        job_id = get_key(application, "ghap_job_id", "job_id")
        status = get_key(application, "ghap_status", "status")
        current_stage = get_key(
            application,
            "ghap_application_current_stage",
            "current_stage",
        )

        if application_id is None or job_id is None:
            continue

        if application_id in seen_application_ids:
            continue

        if str(status).strip().lower() != "active":
            continue

        if final_stage and str(current_stage).strip().lower() == final_stage.lower():
            continue

        if int(job_id) not in job_context:
            continue

        seen_application_ids.add(application_id)
        candidates.append(application_to_admin_record(application, job_context))

    if selection_mode == GLOBAL_IMPACT_MODE:
        return {
            "selection_mode": selection_mode,
            "selected_scope": None,
            "applications": candidates[:requested_limit],
            "eligible_count": len(candidates),
            "selected_group_count": None,
        }

    grouped: dict[tuple[str, str, str], list[dict]] = {}

    for application in candidates:
        scope = (
            application.get("recruiter") or "Unknown recruiter",
            application.get("office") or "Unknown office",
            application.get("department") or "Unknown department",
        )
        grouped.setdefault(scope, []).append(application)

    if not grouped:
        return {
            "selection_mode": selection_mode,
            "selected_scope": None,
            "applications": [],
            "eligible_count": 0,
            "selected_group_count": 0,
        }

    selected_scope_tuple, selected_applications = max(
        grouped.items(),
        key=lambda item: len(item[1]),
    )

    return {
        "selection_mode": selection_mode,
        "selected_scope": {
            "recruiter": selected_scope_tuple[0],
            "office": selected_scope_tuple[1],
            "department": selected_scope_tuple[2],
        },
        "applications": selected_applications[:requested_limit],
        "eligible_count": len(candidates),
        "selected_group_count": len(selected_applications),
    }


def build_change_plan(
    api_base_url: str,
    requested_by_email: str,
    target_stage: str,
    next_stage: str,
    selection_mode: str,
    requested_limit: int,
    reason: str,
) -> dict:
    _request_json(api_base_url, "/health")

    jobs = fetch_paginated(api_base_url, "/jobs")
    applications = fetch_paginated(api_base_url, "/applications")
    job_context = build_job_context(jobs)
    planned_stage_sequence = normalize_stage_sequence(target_stage, next_stage)

    if not planned_stage_sequence:
        raise RuntimeError("At least one target stage is required.")

    selection = select_admin_applications(
        applications,
        job_context,
        planned_stage_sequence,
        requested_limit,
        selection_mode,
    )
    change_request_id = f"admchg_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"

    return {
        "change_request_id": change_request_id,
        "status": "dry_run",
        "requested_by_email": requested_by_email,
        "requested_at": now_utc(),
        "target_stage": target_stage,
        "next_stage": next_stage,
        "planned_stage_sequence": planned_stage_sequence,
        "selection_mode": selection_mode,
        "requested_limit": requested_limit,
        "eligible_count": selection["eligible_count"],
        "selected_count": len(selection["applications"]),
        "selected_scope": selection["selected_scope"],
        "selected_group_count": selection["selected_group_count"],
        "selected_applications": selection["applications"],
        "reason": reason,
        "approval_status": "pending",
        "api_results": [],
    }


def change_request_path(change_request_id: str) -> Path:
    return ADMIN_REPORT_DIR / f"{change_request_id}.json"


def save_report(report: dict) -> Path:
    ADMIN_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = change_request_path(report["change_request_id"])
    path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return path


def load_report(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def response_excerpt(response: dict, max_length: int = 1200) -> str:
    return json.dumps(response, default=str)[:max_length]


def apply_change_plan(api_base_url: str, report: dict, applied_by_email: str) -> dict:
    max_batch_size = get_int_env("ADMIN_MAX_BATCH_SIZE", 500)
    stop_on_error_rate = get_float_env("ADMIN_STOP_ON_ERROR_RATE", 0.05)
    sleep_seconds = get_float_env("ADMIN_API_SLEEP_SECONDS", 0.1)

    selected_applications = report.get("selected_applications", [])[:max_batch_size]
    planned_stage_sequence = report.get("planned_stage_sequence", [])
    api_results = []
    failed_count = 0
    applied_count = 0
    skipped_count = max(0, len(report.get("selected_applications", [])) - len(selected_applications))
    batch_id = f"batch_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    stopped_early = False

    for application in selected_applications:
        application_id = application["application_id"]
        previous_stage = application.get("previous_stage")

        for stage in planned_stage_sequence:
            timestamp = now_utc()

            try:
                response = _request_json(
                    api_base_url,
                    f"/applications/{application_id}/stage-change",
                    method="POST",
                    payload={
                        "current_stage": stage,
                        "new_stage": stage,
                    },
                    timeout=30,
                )
                api_results.append(
                    {
                        "application_id": application_id,
                        "previous_stage": previous_stage,
                        "requested_stage": stage,
                        "new_stage": stage,
                        "response_status": "success",
                        "response_body_excerpt": response_excerpt(response),
                        "timestamp": timestamp,
                        "batch_id": batch_id,
                        "changed_by": applied_by_email,
                        "changed_at": timestamp,
                    }
                )
                applied_count += 1
            except RuntimeError as error:
                failed_count += 1
                api_results.append(
                    {
                        "application_id": application_id,
                        "previous_stage": previous_stage,
                        "requested_stage": stage,
                        "new_stage": stage,
                        "response_status": "failed",
                        "response_body_excerpt": str(error)[:1200],
                        "timestamp": timestamp,
                        "batch_id": batch_id,
                        "changed_by": applied_by_email,
                        "changed_at": timestamp,
                    }
                )

            total_attempts = applied_count + failed_count
            error_rate = failed_count / total_attempts if total_attempts else 0

            if total_attempts and error_rate > stop_on_error_rate:
                stopped_early = True
                break

            if sleep_seconds:
                time.sleep(sleep_seconds)

        if stopped_early:
            break

    if failed_count == 0 and not stopped_early:
        status = "applied"
    elif applied_count > 0:
        status = "partially_applied"
    else:
        status = "failed"

    attempted_applications = {
        result["application_id"]
        for result in api_results
    }
    skipped_count += max(0, len(selected_applications) - len(attempted_applications))

    report.update(
        {
            "status": status,
            "applied_by_email": applied_by_email,
            "applied_at": now_utc(),
            "applied_count": applied_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "stopped_early": stopped_early,
            "batch_id": batch_id,
            "api_results": api_results,
        }
    )

    return report


def render_authentication_panel() -> bool:
    if st.session_state.get("admin_authenticated"):
        email = st.session_state.get("admin_email")
        role = st.session_state.get("admin_role")
        st.success(f"Authenticated as {email} ({role}).")

        if st.button("Sign out admin workflow"):
            for key in [
                "admin_authenticated",
                "admin_email",
                "admin_role",
                "admin_report_path",
            ]:
                st.session_state.pop(key, None)
            st.rerun()

        return True

    st.info(
        "Local demo authentication only. In real production this should be replaced "
        "by company SSO / OAuth / SAML and RBAC."
    )

    email = st.text_input("Admin email")
    password = st.text_input("Demo password", type="password")
    otp = ""

    if get_flag("ADMIN_REQUIRE_OTP", default=True):
        otp = st.text_input("Demo OTP", type="password")

    if st.button("Authenticate admin workflow"):
        is_authenticated, message = authenticate(email, password, otp)

        if is_authenticated:
            normalized_email = email.strip().lower()
            st.session_state["admin_authenticated"] = True
            st.session_state["admin_email"] = normalized_email
            st.session_state["admin_role"] = get_role(normalized_email)
            st.success(message)
            st.rerun()
        else:
            st.error(message)

    return False


def render_plan_summary(report: dict):
    st.write("Change request summary")
    summary = {
        "change_request_id": report["change_request_id"],
        "status": report["status"],
        "approval_status": report.get("approval_status"),
        "requested_by_email": report["requested_by_email"],
        "target_stage": report["target_stage"],
        "next_stage": report.get("next_stage"),
        "planned_stage_sequence": report["planned_stage_sequence"],
        "selection_mode": report["selection_mode"],
        "requested_limit": report["requested_limit"],
        "eligible_count": report["eligible_count"],
        "selected_count": report["selected_count"],
        "expected_api_calls": report["selected_count"] * len(report["planned_stage_sequence"]),
        "reason": report["reason"],
    }

    if report.get("selected_group_count") is not None:
        summary["selected_group_count"] = report["selected_group_count"]

    st.json(summary)

    if report.get("selected_scope"):
        st.write("Selected scope")
        st.json(report["selected_scope"])
    else:
        st.write("Breakdown by recruiter / office / department")
        st.json(_build_scope_breakdown(report.get("selected_applications", [])))

    st.write("First 10 application IDs")
    st.code(
        ", ".join(
            str(application["application_id"])
            for application in report.get("selected_applications", [])[:10]
        )
    )


def render_dry_run(api_base_url: str, email: str, role: str):
    st.subheader("1. Dry-run")

    if not can_dry_run(role):
        st.info("Your role can view the workflow but cannot create dry-runs.")
        return

    target_stage = st.text_input(
        "Target stage",
        value=DEFAULT_TARGET_STAGE,
        key="admin_target_stage",
    )
    next_stage = st.text_input(
        "Optional next stage",
        value=DEFAULT_NEXT_STAGE,
        key="admin_next_stage",
    )
    selection_mode = st.radio(
        "Selection mode",
        [FOCUSED_GROUP_MODE, GLOBAL_IMPACT_MODE],
        key="admin_selection_mode",
    )
    requested_limit = st.number_input(
        "Application limit",
        min_value=10,
        max_value=500,
        value=100,
        step=10,
        key="admin_application_limit",
        help="This is a maximum. The actual selected count depends on eligible applications.",
    )
    reason = st.text_area(
        "Reason for change",
        key="admin_change_reason",
        placeholder="Explain why this operational change is required.",
    )

    if st.button("Create dry-run change plan"):
        if not reason.strip():
            st.error("Reason for change is required.")
            return

        try:
            report = build_change_plan(
                api_base_url=api_base_url,
                requested_by_email=email,
                target_stage=target_stage,
                next_stage=next_stage,
                selection_mode=selection_mode,
                requested_limit=int(requested_limit),
                reason=reason.strip(),
            )
            path = save_report(report)
            st.session_state["admin_report_path"] = str(path)
            st.success(f"Dry-run report saved: {path}")
            render_plan_summary(report)
        except RuntimeError as error:
            st.error(str(error))


def render_approval(report: dict, report_path: Path, email: str, role: str):
    st.subheader("2. Approve")
    render_plan_summary(report)

    if not can_approve(role):
        st.info("Your role can view the plan but cannot approve it.")
        return

    approved = st.checkbox(
        "I confirm that this change has been reviewed and approved.",
        key="admin_approval_checkbox",
    )
    typed_change_request_id = st.text_input(
        "Type the change_request_id to approve",
        key="admin_approval_change_request_id",
    )

    if st.button("Approve change request"):
        if not approved:
            st.error("Approval checkbox is required.")
            return

        if typed_change_request_id.strip() != report["change_request_id"]:
            st.error("The typed change_request_id does not match.")
            return

        report.update(
            {
                "approval_status": "approved",
                "approved_by_email": email,
                "approved_at": now_utc(),
                "status": "approved",
            }
        )
        save_report(report)
        st.session_state["admin_report_path"] = str(report_path)
        st.success("Change request approved.")
        st.rerun()


def render_apply(api_base_url: str, report: dict, report_path: Path, email: str, role: str):
    st.subheader("3. Apply")
    st.caption(
        "Rollback for operational state changes is a compensating action, not a simple "
        "database revert. The audit file keeps previous stages so an authorized admin "
        "can move applications back if required."
    )

    if report.get("approval_status") != "approved":
        st.info("Apply is disabled until a dry-run report is approved.")
        return

    if not can_apply(role):
        st.info("Your role cannot apply this change request.")
        return

    if report.get("status") in {"applied", "partially_applied", "failed"}:
        st.info(f"This change request has already reached status: {report.get('status')}.")
        return

    st.warning(
        "Apply will mutate the configured source system through the stage-change API. "
        "It will not write directly to BigQuery."
    )

    typed_change_request_id = st.text_input(
        "Type the change_request_id to apply",
        key="admin_apply_change_request_id",
    )

    if st.button("Apply approved source-system changes"):
        if typed_change_request_id.strip() != report["change_request_id"]:
            st.error("The typed change_request_id does not match.")
            return

        updated_report = apply_change_plan(
            api_base_url=api_base_url,
            report=report,
            applied_by_email=email,
        )
        save_report(updated_report)
        st.session_state["admin_report_path"] = str(report_path)
        st.success(f"Apply completed with status: {updated_report['status']}")
        st.json(
            {
                "applied_count": updated_report.get("applied_count", 0),
                "failed_count": updated_report.get("failed_count", 0),
                "skipped_count": updated_report.get("skipped_count", 0),
                "stopped_early": updated_report.get("stopped_early", False),
            }
        )


def render_production_pipeline_button():
    if not get_flag("ALLOW_PROD_PIPELINE_TRIGGER"):
        return

    st.subheader("Production analytics refresh")
    st.warning(
        "This runs the production analytics pipeline and updates production BigQuery "
        "marts from the source system."
    )

    if st.button("Run production ingestion pipeline"):
        try:
            result = subprocess.run(
                ["./scripts/run_recruitment_pipeline.sh"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=900,
                check=False,
            )
            st.code(result.stdout or "(no stdout)", language="bash")

            if result.stderr:
                st.code(result.stderr, language="bash")

            if result.returncode == 0:
                st.success("Production ingestion pipeline completed successfully.")
            else:
                st.error(
                    f"Production ingestion pipeline failed with exit code {result.returncode}."
                )
        except subprocess.TimeoutExpired as error:
            st.error("Production ingestion pipeline timed out after 15 minutes.")
            if error.stdout:
                st.code(error.stdout, language="bash")
            if error.stderr:
                st.code(error.stderr, language="bash")


def get_supabase_role(user_email: str) -> str:
    roles = supabase_ops.get_current_user_roles()
    active_roles = [
        role["role"]
        for role in roles
        if str(role.get("email", "")).lower() == user_email.lower()
        and role.get("is_active", True)
    ]

    for role in [
        "super_admin",
        "dev_admin",
        "hr_manager",
        "business_manager",
        "analyst_readonly",
    ]:
        if role in active_roles:
            return role

    return "analyst_readonly"


def render_supabase_request_summary(request: dict, items: list[dict]):
    application_ids = [
        int(item["application_id"])
        for item in items
        if item.get("application_id") is not None
    ]
    application_details = []

    if application_ids:
        try:
            application_details = supabase_ops.list_applications_by_ids(application_ids)
        except RuntimeError as error:
            st.warning(
                "Application details could not be fetched. Showing request item IDs only."
            )
            with st.expander("Supabase application detail fetch error"):
                st.code(str(error), language=None)

    st.write("Business review: stage-change request")
    st.json(
        {
            "status": request.get("status"),
            "target_stage": request.get("target_stage"),
            "next_stage": request.get("next_stage"),
            "selection_mode": request.get("selection_mode"),
            "selected_count": request.get("selected_count") or len(items),
            "reason": request.get("reason"),
            "expected_stage_events": (request.get("selected_count") or len(items)),
        }
    )

    if application_details:
        render_application_business_table(
            "Candidates/applications selected for stage change",
            application_details,
            target_stage=request.get("target_stage"),
            next_stage=request.get("next_stage"),
        )

    with st.expander("Audit / technical details", expanded=False):
        st.json(
            {
                "request_id": request.get("request_id"),
                "status": request.get("status"),
                "requested_by_email": request.get("requested_by_email"),
                "target_stage": request.get("target_stage"),
                "next_stage": request.get("next_stage"),
                "selection_mode": request.get("selection_mode"),
                "requested_limit": request.get("requested_limit"),
                "eligible_count": request.get("eligible_count"),
                "selected_count": request.get("selected_count"),
                "reason": request.get("reason"),
            }
        )
        st.write("First 10 application IDs")
        st.code(", ".join(str(application_id) for application_id in application_ids[:10]))


def render_supabase_outcome_summary(request: dict, items: list[dict]):
    outcome = request.get("outcome") or "outcome"
    selected_count = request.get("selected_count") or len(items)
    summary = {
        "request_id": request.get("request_id"),
        "status": request.get("status"),
        "requested_by_email": request.get("requested_by_email"),
        "outcome": outcome,
        "selection_mode": request.get("selection_mode"),
        "requested_limit": request.get("requested_limit"),
        "eligible_count": request.get("eligible_count"),
        "selected_count": selected_count,
        "reason": request.get("reason"),
        "expected_active_applications_decrease": f"up to {selected_count}",
    }

    if outcome == "hired":
        summary["expected_hired_kpi_increase"] = f"up to {selected_count}"
        summary["expected_rejected_kpi_increase"] = "0"
    elif outcome == "rejected":
        summary["expected_rejected_kpi_increase"] = f"up to {selected_count}"
        summary["expected_hired_kpi_increase"] = "0"

    st.write(f"Business review: {outcome} outcome request")
    st.json(
        {
            "status": summary["status"],
            "outcome": outcome,
            "selection_mode": summary["selection_mode"],
            "selected_count": summary["selected_count"],
            "reason": summary["reason"],
            "expected_active_applications_decrease": summary[
                "expected_active_applications_decrease"
            ],
            "expected_hired_kpi_increase": summary.get("expected_hired_kpi_increase"),
            "expected_rejected_kpi_increase": summary.get(
                "expected_rejected_kpi_increase"
            ),
        }
    )
    application_ids = [
        int(item["application_id"])
        for item in items
        if item.get("application_id") is not None
    ]
    try:
        application_details = supabase_ops.list_applications_by_ids(application_ids)
    except RuntimeError as error:
        application_details = []
        st.warning(
            "Application details could not be fetched. Showing request item IDs only."
        )
        with st.expander("Supabase application detail fetch error"):
            st.code(str(error), language=None)

    if application_details:
        render_hiring_candidate_table(application_details, items)
    else:
        st.write("Candidates selected for outcome")
        st.dataframe(
            [
                {
                    "application_id": application_id,
                    "item_apply_status": item.get("apply_status"),
                }
                for item in items
                if (application_id := item.get("application_id")) is not None
            ],
            hide_index=True,
            use_container_width=True,
        )
    with st.expander("Audit / technical details", expanded=False):
        st.json(summary)
        st.caption("Selected application IDs, not the request_id")
        st.code(", ".join(str(application_id) for application_id in application_ids[:10]))


def normalize_application_display_row(application: dict) -> dict:
    candidate_id = application.get("candidate_id")
    job_id = application.get("job_id")
    recruiter = application.get("recruiter_name") or application.get("recruiter")
    office = application.get("office_name") or application.get("office")
    department = application.get("department_name") or application.get("department")
    row = {
        "application_id": application.get("application_id"),
        "candidate_id": candidate_id,
        "candidate_display": (
            application.get("candidate_full_name")
            or application.get("candidate_name")
            or (f"Candidate {candidate_id}" if candidate_id is not None else None)
        ),
        "job_id": job_id,
        "job_display": (
            application.get("job_title")
            or (f"Job {job_id}" if job_id is not None else None)
        ),
        "status": application.get("status"),
        "current_stage": application.get("current_stage"),
        "office": office,
        "department": department,
        "recruiter": recruiter,
        "updated_at": application.get("updated_at"),
    }

    if application.get("created_at") is not None:
        row["created_at"] = application.get("created_at")

    if application.get("applied_at") is not None:
        row["applied_at"] = application.get("applied_at")

    return {
        key: value
        for key, value in row.items()
        if value is not None and str(value).strip() != ""
    }


def render_hiring_candidate_table(applications: list[dict], items: list[dict] | None = None):
    st.write("Candidates selected for outcome")

    if not applications:
        st.info("No candidate/application details are available for this request.")
        return

    item_status_by_application_id = {
        int(item["application_id"]): item.get("apply_status")
        for item in items or []
        if item.get("application_id") is not None
    }
    rows = []

    for application in applications:
        row = normalize_application_display_row(application)
        application_id = row.get("application_id")

        if application_id is not None:
            row["item_apply_status"] = item_status_by_application_id.get(
                int(application_id)
            )

        rows.append(row)

    display_rows = [
        {
            "Candidate": row.get("candidate_display"),
            "Application ID": row.get("application_id"),
            "Candidate ID": row.get("candidate_id"),
            "Job": row.get("job_display"),
            "Stage": row.get("current_stage"),
            "Status": row.get("status"),
            "Office": row.get("office"),
            "Department": row.get("department"),
            "Recruiter": row.get("recruiter"),
            "Updated at": row.get("updated_at"),
            "Item status": row.get("item_apply_status"),
        }
        for row in rows
    ]

    st.dataframe(display_rows, hide_index=True, use_container_width=True)


def build_application_table_rows(
    applications: list[dict],
    *,
    target_stage: str | None = None,
    next_stage: str | None = None,
    item_status_by_application_id: dict[int, str | None] | None = None,
) -> list[dict[str, Any]]:
    rows = []

    for application in applications:
        row = normalize_application_display_row(application)
        application_id = row.get("application_id")
        display_row = {
            "Candidate": row.get("candidate_display"),
            "Application ID": application_id,
            "Candidate ID": row.get("candidate_id"),
            "Job": row.get("job_display"),
            "Current stage": row.get("current_stage"),
            "Stage": row.get("current_stage"),
            "Status": row.get("status"),
            "Office": row.get("office"),
            "Department": row.get("department"),
            "Recruiter": row.get("recruiter"),
            "Updated at": row.get("updated_at"),
        }

        if target_stage is not None:
            display_row["Target stage"] = target_stage

        if next_stage is not None:
            display_row["Next stage"] = next_stage

        if item_status_by_application_id and application_id is not None:
            display_row["Item status"] = item_status_by_application_id.get(
                int(application_id)
            )

        rows.append(
            {
                key: value
                for key, value in display_row.items()
                if value is not None and str(value).strip() != ""
            }
        )

    return rows


def render_application_business_table(
    title: str,
    applications: list[dict],
    *,
    target_stage: str | None = None,
    next_stage: str | None = None,
    item_status_by_application_id: dict[int, str | None] | None = None,
):
    st.write(title)

    if not applications:
        st.info("No matching candidates/applications found.")
        return

    st.dataframe(
        build_application_table_rows(
            applications,
            target_stage=target_stage,
            next_stage=next_stage,
            item_status_by_application_id=item_status_by_application_id,
        ),
        hide_index=True,
        use_container_width=True,
    )


def filter_eligible_hiring_applications(applications: list[dict]) -> list[dict]:
    eligible = [
        application
        for application in applications
        if application.get("status") == "active"
        and application.get("current_stage") in HIRING_OUTCOME_STAGES
    ]

    return sorted(
        eligible,
        key=lambda application: (
            application.get("updated_at") or "",
            application.get("application_id") or 0,
        ),
    )


def sort_hiring_demo_candidates(applications: list[dict]) -> list[dict]:
    stage_priority = {
        "Offer": 0,
        "Reference Check": 1,
        "Final Interview": 2,
        "Final (Executive) Interview": 3,
    }

    return sorted(
        applications,
        key=lambda application: (
            stage_priority.get(str(application.get("current_stage")), 99),
            application.get("updated_at") or "",
            application.get("application_id") or 0,
        ),
    )


def rejection_stage_priority(stage: str | None) -> int:
    return {
        "Offer": 4,
        "Reference Check": 3,
        "Final (Executive) Interview": 2,
        "Final Interview": 1,
    }.get(stage or "", 0)


def filter_eligible_rejection_applications(
    applications: list[dict],
    selection_mode: str,
) -> list[dict]:
    if selection_mode == "Early process rejection":
        eligible_stages = {"Application Review", "Recruiter Interview"}
    elif selection_mode == "Reference Check only":
        eligible_stages = {"Reference Check"}
    elif selection_mode == "Late-stage rejection":
        eligible_stages = {
            "Final Interview",
            "Final (Executive) Interview",
            "Reference Check",
            "Offer",
        }
    else:
        eligible_stages = REJECTION_OUTCOME_STAGES

    eligible = [
        application
        for application in applications
        if application.get("status") == "active"
        and application.get("current_stage") in eligible_stages
    ]

    if selection_mode == "Late-stage rejection":
        return sorted(
            eligible,
            key=lambda application: (
                -rejection_stage_priority(application.get("current_stage")),
                application.get("updated_at") or "",
                application.get("application_id") or 0,
            ),
        )

    return sorted(
        eligible,
        key=lambda application: (
            application.get("updated_at") or "",
            application.get("application_id") or 0,
        ),
    )


def filter_eligible_stage_change_applications(
    applications: list[dict],
    target_stage: str,
    next_stage: str,
) -> list[dict]:
    final_stage = next_stage if next_stage and next_stage != target_stage else target_stage

    eligible = [
        application
        for application in applications
        if application.get("status") == "active"
        and (application.get("current_stage") or "") != final_stage
    ]

    return sorted(
        eligible,
        key=lambda application: (
            application.get("updated_at") or "",
            application.get("application_id") or 0,
        ),
    )


def format_hiring_application_option(application: dict) -> str:
    display_row = normalize_application_display_row(application)
    candidate = display_row.get("candidate_display") or application.get("candidate_id")
    job = display_row.get("job_display") or application.get("job_id")

    return (
        f"{candidate} — {job} — {application.get('current_stage')} — "
        f"application {application.get('application_id')}"
    )


def application_matches_search(application: dict, search: str) -> bool:
    if not search.strip():
        return True

    display_row = normalize_application_display_row(application)
    haystack = " ".join(
        str(value).lower()
        for value in display_row.values()
        if value is not None
    )

    return search.strip().lower() in haystack


def get_application_exclusion_reason(
    application: dict,
    *,
    outcome: str,
    eligible_stages: set[str],
) -> str:
    status = application.get("status")
    current_stage = application.get("current_stage")
    reasons = []

    if status == "hired":
        reasons.append("already hired")
    elif status == "rejected":
        reasons.append("already rejected")
    elif status != "active":
        reasons.append("not active")

    if current_stage not in eligible_stages:
        reasons.append(f"current stage not eligible for {outcome}")

    return "; ".join(reasons) or "not eligible"


def render_ineligible_candidate_diagnostics(
    *,
    search: str,
    outcome: str,
    eligible_stages: set[str],
):
    if not search.strip():
        return

    try:
        all_applications = supabase_ops.list_applications(limit=5000)
    except RuntimeError as error:
        with st.expander("Candidate eligibility diagnostic error", expanded=False):
            st.code(str(error), language=None)
        return

    matching_applications = [
        application
        for application in all_applications
        if application_matches_search(application, search)
    ]

    if not matching_applications:
        return

    rows = []

    for application in matching_applications[:50]:
        row = normalize_application_display_row(application)
        rows.append(
            {
                "Candidate": row.get("candidate_display"),
                "Application ID": row.get("application_id"),
                "Status": row.get("status"),
                "Current stage": row.get("current_stage"),
                "Job": row.get("job_display"),
                "Exclusion reason": get_application_exclusion_reason(
                    application,
                    outcome=outcome,
                    eligible_stages=eligible_stages,
                ),
            }
        )

    st.warning("Candidate exists but is not eligible")
    st.dataframe(rows, hide_index=True, use_container_width=True)
    st.caption(
        "The dashboard tables are powered by BigQuery marts. Admin actions use "
        "Supabase operational data. A candidate shown in an analytics table may "
        "not be eligible for the selected operational workflow."
    )


def render_candidate_filter_summary(
    outcome: str,
    eligible_stages: set[str],
    search: str,
    selected_stages: list[str],
    selected_job: str,
    selected_offices: list[str] | None,
    selected_departments: list[str] | None,
    selected_recruiters: list[str] | None,
):
    optional_parts = []

    if selected_offices is not None:
        optional_parts.append(f"offices={', '.join(selected_offices) or 'all'}")

    if selected_departments is not None:
        optional_parts.append(
            f"departments={', '.join(selected_departments) or 'all'}"
        )

    if selected_recruiters is not None:
        optional_parts.append(f"recruiters={', '.join(selected_recruiters) or 'all'}")

    st.caption(
        f"Filter summary: outcome={outcome}; status=active; "
        f"stages={', '.join(selected_stages) or 'all eligible'}; "
        f"job={selected_job or 'all'}; search={search.strip() or '(none)'}"
        + (f"; {'; '.join(optional_parts)}" if optional_parts else "")
    )


def get_distinct_display_values(applications: list[dict], field: str) -> list[str]:
    return sorted(
        {
            str(value)
            for application in applications
            if (value := normalize_application_display_row(application).get(field))
        }
    )


def get_job_filter_options(applications: list[dict]) -> list[str]:
    return get_distinct_display_values(applications, "job_display")


def render_candidate_search_selection(
    *,
    outcome: str,
    eligible_applications: list[dict],
    eligible_stages: set[str],
    key_prefix: str,
    default_stages: list[str] | None = None,
) -> list[int]:
    st.write("Candidate search and selection")
    clear_requested = st.button(
        "Clear candidate filters",
        key=f"{key_prefix}_clear_filters",
    )

    if clear_requested:
        for suffix in [
            "candidate_search",
            "stage_filter",
            "job_filter",
            "office_filter",
            "department_filter",
            "recruiter_filter",
            "result_limit",
            "selected_application_ids",
        ]:
            st.session_state.pop(f"{key_prefix}_{suffix}", None)
        st.rerun()

    search = st.text_input(
        "Search candidate",
        key=f"{key_prefix}_candidate_search",
        placeholder="Search by candidate name, candidate ID, application ID, job, stage...",
    )
    stage_options = sorted(eligible_stages)
    stage_defaults = [
        stage for stage in (default_stages or stage_options) if stage in stage_options
    ] or stage_options
    selected_stages = st.multiselect(
        "Stage",
        stage_options,
        default=stage_defaults,
        key=f"{key_prefix}_stage_filter",
        help="Leave all eligible stages selected, or narrow to one or more stages.",
    )
    job_options = get_job_filter_options(eligible_applications)
    selected_job = st.selectbox(
        "Job",
        [""] + job_options,
        format_func=lambda value: value or "All jobs",
        key=f"{key_prefix}_job_filter",
    )
    office_options = get_distinct_display_values(eligible_applications, "office")
    department_options = get_distinct_display_values(
        eligible_applications,
        "department",
    )
    recruiter_options = get_distinct_display_values(eligible_applications, "recruiter")
    selected_offices = None
    selected_departments = None
    selected_recruiters = None

    if office_options:
        selected_offices = st.multiselect(
            "Office",
            office_options,
            default=office_options,
            key=f"{key_prefix}_office_filter",
        )

    if department_options:
        selected_departments = st.multiselect(
            "Department",
            department_options,
            default=department_options,
            key=f"{key_prefix}_department_filter",
        )

    if recruiter_options:
        selected_recruiters = st.multiselect(
            "Recruiter",
            recruiter_options,
            default=recruiter_options,
            key=f"{key_prefix}_recruiter_filter",
        )

    result_limit = st.number_input(
        "Result limit",
        min_value=10,
        max_value=200,
        value=50,
        step=10,
        key=f"{key_prefix}_result_limit",
        help="Limits the displayed candidates after filters are applied.",
    )

    render_candidate_filter_summary(
        outcome,
        eligible_stages,
        search,
        selected_stages,
        selected_job,
        selected_offices,
        selected_departments,
        selected_recruiters,
    )
    eligible_count = len(eligible_applications)
    filtered_applications = [
        application
        for application in eligible_applications
        if (
            not selected_stages
            or application.get("current_stage") in set(selected_stages)
        )
    ]
    after_stage_count = len(filtered_applications)
    filtered_applications = [
        application
        for application in filtered_applications
        if application_matches_search(application, search)
    ]
    after_search_count = len(filtered_applications)
    filtered_applications = [
        application
        for application in filtered_applications
        if (
            not selected_job
            or normalize_application_display_row(application).get("job_display")
            == selected_job
        )
        and (
            selected_offices is None
            or normalize_application_display_row(application).get("office")
            in selected_offices
        )
        and (
            selected_departments is None
            or normalize_application_display_row(application).get("department")
            in selected_departments
        )
        and (
            selected_recruiters is None
            or normalize_application_display_row(application).get("recruiter")
            in selected_recruiters
        )
    ]
    after_scope_count = len(filtered_applications)

    if not filtered_applications:
        st.info(
            "No candidates match the current filters. Clear filters or broaden the "
            "stage selection."
        )
        render_ineligible_candidate_diagnostics(
            search=search,
            outcome=outcome,
            eligible_stages=eligible_stages,
        )
        with st.expander("Candidate search debug", expanded=False):
            st.json(
                {
                    "eligible_before_search": eligible_count,
                    "after_stage_filter": after_stage_count,
                    "after_search": after_search_count,
                    "after_job_office_department_recruiter_filters": after_scope_count,
                    "final_returned_count": 0,
                    "safe_query_summary": {
                        "source": "Supabase public.applications",
                        "status": "active",
                        "eligible_stages": sorted(eligible_stages),
                        "search": search,
                        "result_limit": int(result_limit),
                    },
                }
            )
        return []

    st.caption(
        f"{len(filtered_applications)} matching candidate(s); showing first "
        f"{min(len(filtered_applications), int(result_limit))}."
    )
    limited_applications = filtered_applications[: int(result_limit)]
    with st.expander("Candidate search debug", expanded=False):
        st.json(
            {
                "eligible_before_search": eligible_count,
                "after_stage_filter": after_stage_count,
                "after_search": after_search_count,
                "after_job_office_department_recruiter_filters": after_scope_count,
                "final_returned_count": len(limited_applications),
                "safe_query_summary": {
                    "source": "Supabase public.applications",
                    "status": "active",
                    "eligible_stages": sorted(eligible_stages),
                    "search": search,
                    "result_limit": int(result_limit),
                },
            }
        )
    table_rows = [
        {
            "Candidate": row.get("candidate_display"),
            "Application ID": row.get("application_id"),
            "Candidate ID": row.get("candidate_id"),
            "Job": row.get("job_display"),
            "Stage": row.get("current_stage"),
            "Status": row.get("status"),
            "Office": row.get("office"),
            "Department": row.get("department"),
            "Recruiter": row.get("recruiter"),
            "Updated at": row.get("updated_at"),
        }
        for row in (
            normalize_application_display_row(application)
            for application in limited_applications
        )
    ]
    st.dataframe(table_rows, hide_index=True, use_container_width=True)

    application_by_id = {
        int(application["application_id"]): application
        for application in limited_applications
        if application.get("application_id") is not None
    }
    selected_application_ids = st.multiselect(
        "Select candidate(s)",
        list(application_by_id.keys()),
        format_func=lambda application_id: format_hiring_application_option(
            application_by_id[application_id]
        ),
        key=f"{key_prefix}_selected_application_ids",
    )

    if selected_application_ids:
        render_hiring_candidate_table(
            [
                application_by_id[application_id]
                for application_id in selected_application_ids
            ]
        )

    return selected_application_ids


def set_selected_application_ids(key_prefix: str, application_ids: list[int]):
    st.session_state[f"{key_prefix}_selected_application_ids"] = application_ids


def get_selected_application_details(
    applications: list[dict],
    selected_application_ids: list[int],
) -> list[dict]:
    application_by_id = {
        int(application["application_id"]): application
        for application in applications
        if application.get("application_id") is not None
    }

    return [
        application_by_id[application_id]
        for application_id in selected_application_ids
        if application_id in application_by_id
    ]


def render_candidate_helper_actions(
    *,
    show_label: str,
    select_label: str,
    table_title: str,
    key_prefix: str,
    applications: list[dict],
    demo_applications: list[dict] | None = None,
    target_stage: str | None = None,
    next_stage: str | None = None,
):
    col_show, col_select = st.columns(2)
    show_requested = col_show.button(show_label, key=f"{key_prefix}_show_eligible")
    select_requested = col_select.button(
        select_label,
        key=f"{key_prefix}_select_demo",
    )

    if show_requested:
        st.session_state[f"{key_prefix}_show_eligible_table"] = True

    demo_candidates = demo_applications if demo_applications is not None else applications

    if select_requested:
        if demo_candidates:
            application_id = int(demo_candidates[0]["application_id"])
            set_selected_application_ids(key_prefix, [application_id])
            st.session_state[f"{key_prefix}_show_eligible_table"] = True
            st.success("Demo candidate selected.")
            render_application_business_table(
                "Selected demo candidate/application",
                [demo_candidates[0]],
                target_stage=target_stage,
                next_stage=next_stage,
            )
        else:
            st.warning("No eligible demo candidate/application is available.")

    if st.session_state.get(f"{key_prefix}_show_eligible_table"):
        render_application_business_table(
            table_title,
            applications[:200],
            target_stage=target_stage,
            next_stage=next_stage,
        )
        st.caption(
            f"{len(applications)} eligible row(s) found in Supabase operational data; "
            f"showing up to 200."
        )


def render_request_id_copy_block(request_id: str, label: str):
    with st.expander("Audit / technical details", expanded=False):
        st.caption(label)
        st.code(request_id, language=None)
        st.caption("Copy this UUID into the approval field. Do not paste application IDs.")


def select_request_id(
    label: str,
    request_options: list[str],
    selected_state_key: str,
    selectbox_key: str,
) -> str:
    preferred_request_id = st.session_state.get(selected_state_key)
    selected_index = (
        request_options.index(preferred_request_id)
        if preferred_request_id in request_options
        else 0
    )
    if preferred_request_id in request_options:
        st.session_state[selectbox_key] = preferred_request_id

    selected_request_id = st.selectbox(
        label,
        request_options,
        index=selected_index,
        key=selectbox_key,
    )
    st.session_state[selected_state_key] = selected_request_id

    return selected_request_id


def render_latest_request_consistency(
    selected_request_id: str,
    last_created_request_id: str | None,
):
    if not last_created_request_id:
        return

    if selected_request_id == last_created_request_id:
        st.success("Latest dry-run is selected.")
    else:
        st.warning("The selected request is not the latest dry-run. Verify before approving.")


def looks_like_application_ids(value: str) -> bool:
    normalized_value = value.strip()

    return "," in normalized_value or normalized_value.startswith("6000000")


def render_supabase_hiring_outcome_workflow(role: str):
    st.subheader("4. Supabase hiring outcome")
    st.warning(
        "This workflow changes final application outcome to Hired. It is separate "
        "from recruitment stage changes."
    )

    if not can_dry_run(role):
        st.info("Your Supabase role can view the workflow but cannot create hiring dry-runs.")
    else:
        hiring_limit = st.number_input(
            "Hiring limit",
            min_value=1,
            max_value=100,
            value=10,
            step=1,
            key="supabase_hiring_limit",
            help="This is a maximum. The actual selected count depends on eligible applications.",
        )
        selection_mode = st.radio(
            "Hiring selection mode",
            [
                "Manual candidate selection",
                "Offer only",
                "Late-stage candidates",
            ],
            key="supabase_hiring_selection_mode",
        )
        manual_application_ids: list[int] | None = None
        eligible_applications: list[dict] = []
        key_prefix = "supabase_manual_hiring"

        try:
            eligible_applications = filter_eligible_hiring_applications(
                supabase_ops.list_active_applications_for_stages(
                    HIRING_OUTCOME_STAGES,
                    limit=5000,
                )
            )
        except RuntimeError as error:
            st.error(str(error))

        render_candidate_helper_actions(
            show_label="Show eligible hiring candidates",
            select_label="Select demo hiring candidate",
            table_title="Eligible hiring candidates",
            key_prefix=key_prefix,
            applications=eligible_applications,
            demo_applications=sort_hiring_demo_candidates(eligible_applications),
        )
        manual_application_ids = render_candidate_search_selection(
            outcome="hired",
            eligible_applications=eligible_applications,
            eligible_stages=HIRING_OUTCOME_STAGES,
            key_prefix=key_prefix,
            default_stages=["Offer"],
        )

        if manual_application_ids:
            selected_details = get_selected_application_details(
                eligible_applications,
                manual_application_ids,
            )
            render_application_business_table(
                "Business review: selected hiring candidate(s)",
                selected_details,
            )

        reason = st.text_area(
            "Reason for hiring outcome",
            key="supabase_hiring_reason",
            placeholder="Explain why these applications should be marked as hired.",
        )

        if st.button("Create hiring dry-run"):
            if not reason.strip():
                st.error("Reason for hiring outcome is required.")
                return

            effective_selection_mode = (
                "Manual candidate selection"
                if manual_application_ids
                else selection_mode
            )

            if effective_selection_mode == "Manual candidate selection":
                if not manual_application_ids:
                    st.error("Select at least one application for manual hiring outcome.")
                    return

            try:
                request_id = supabase_ops.create_hiring_outcome_dry_run(
                    selection_mode=effective_selection_mode,
                    requested_limit=len(manual_application_ids)
                    if effective_selection_mode == "Manual candidate selection"
                    else int(hiring_limit),
                    reason=reason.strip(),
                    application_ids=manual_application_ids
                    if effective_selection_mode == "Manual candidate selection"
                    else None,
                )
                st.session_state["selected_hiring_outcome_request_id"] = request_id
                st.session_state["last_created_hiring_request_id"] = request_id
                st.session_state["supabase_outcome_request_id"] = request_id
                st.success(f"New hiring dry-run created: {request_id}")
            except RuntimeError as error:
                st.error(str(error))

    try:
        recent_requests = supabase_ops.list_recent_outcome_change_requests(
            outcome="hired"
        )
    except RuntimeError as error:
        st.error(str(error))
        return

    request_options = [request["request_id"] for request in recent_requests]
    fallback_request_id = st.session_state.get("supabase_outcome_request_id")

    if (
        "selected_hiring_outcome_request_id" not in st.session_state
        and fallback_request_id
    ):
        st.session_state["selected_hiring_outcome_request_id"] = fallback_request_id

    if request_options:
        selected_request_id = select_request_id(
            "Select hiring request_id",
            request_options,
            "selected_hiring_outcome_request_id",
            "supabase_outcome_request_select",
        )
        st.session_state["supabase_outcome_request_id"] = selected_request_id
        render_latest_request_consistency(
            selected_request_id,
            st.session_state.get("last_created_hiring_request_id"),
        )
        render_request_id_copy_block(
            selected_request_id,
            "Selected hiring request_id to copy",
        )
    else:
        selected_request_id = st.session_state.get("selected_hiring_outcome_request_id")

    if not selected_request_id:
        return

    try:
        request = supabase_ops.get_outcome_change_request(selected_request_id)
        items = supabase_ops.list_outcome_request_items(selected_request_id)
    except RuntimeError as error:
        st.error(str(error))
        return

    if not request:
        st.info("No Supabase hiring outcome request selected.")
        return

    st.caption(f"Authoritative hiring outcome status from Supabase: {request.get('status')}")
    render_supabase_outcome_summary(request, items)

    if not can_approve(role):
        st.info("Your Supabase role cannot approve hiring outcome requests.")
    elif request.get("status") != "dry_run":
        st.info(f"Hiring approval is unavailable for status: {request.get('status')}.")
    else:
        st.write("Review hiring outcome summary before approval")
        render_supabase_outcome_summary(request, items)
        approved = st.checkbox(
            "I confirm that this hiring outcome has been reviewed and approved.",
            key="supabase_hiring_approval_checkbox",
        )
        typed_request_id = st.text_input(
            "Type the hiring request_id to approve",
            key="supabase_hiring_approval_request_id",
        )
        st.caption("Paste the selected UUID request_id. Do not paste application IDs.")

        if looks_like_application_ids(typed_request_id):
            st.error(
                "This looks like application IDs. Please paste the request_id UUID instead."
            )

        if st.button("Approve hiring outcome request"):
            if not approved:
                st.error("Approval checkbox is required.")
                return

            if looks_like_application_ids(typed_request_id):
                st.error(
                    "This looks like application IDs. Please paste the request_id UUID instead."
                )
                return

            if typed_request_id != selected_request_id:
                st.error("The typed request_id does not match.")
                return

            try:
                supabase_ops.approve_hiring_outcome_request(selected_request_id)
                authoritative_request = supabase_ops.get_outcome_change_request(
                    selected_request_id
                )

                if (
                    authoritative_request
                    and authoritative_request.get("status") == "approved"
                    and authoritative_request.get("approved_by_email")
                    and authoritative_request.get("approved_at")
                ):
                    request = authoritative_request
                    st.success("Supabase hiring outcome request approved.")
                    st.caption(
                        "Authoritative hiring outcome status from Supabase: "
                        f"{request.get('status')}"
                    )
                else:
                    st.error(
                        "Approval RPC returned, but the authoritative Supabase row "
                        "does not show a fully approved hiring outcome request."
                    )
            except RuntimeError as error:
                st.error(str(error))

    request_status = request.get("status")

    if request_status == "dry_run":
        st.info("Hiring apply is disabled until the Supabase request is approved.")
    elif request_status == "applied":
        st.info("This hiring outcome request has already been applied.")
    elif request_status == "partially_applied":
        st.info("This hiring outcome request was partially applied. Review audit details.")
    elif request_status == "failed":
        st.info("This hiring outcome request failed. Review audit details.")
    elif request_status == "cancelled":
        st.info("This hiring outcome request was cancelled.")
    elif request_status != "approved":
        st.info(f"Hiring apply is unavailable for status: {request_status}.")
    elif not get_flag("ALLOW_SUPABASE_PROD_APPLY"):
        st.info("Hiring apply is disabled unless ALLOW_SUPABASE_PROD_APPLY=true.")
    elif not can_apply(role):
        st.info("Your Supabase role cannot apply hiring outcome requests.")
    else:
        typed_request_id = st.text_input(
            "Type the hiring request_id to apply",
            key="supabase_hiring_apply_request_id",
        )

        if st.button("Apply hiring outcome"):
            if typed_request_id != selected_request_id:
                st.error("The typed request_id does not match.")
                return

            try:
                supabase_ops.apply_hiring_outcome_request(selected_request_id)
                st.success("Supabase hiring outcome applied.")
                st.rerun()
            except RuntimeError as error:
                st.error(str(error))


def render_supabase_rejection_outcome_workflow(role: str):
    st.subheader("5. Supabase rejection outcome")
    st.warning(
        "This workflow changes the terminal application outcome to Rejected. "
        "Rejected is intentionally not available in the recruitment stage dropdown."
    )

    if not can_dry_run(role):
        st.info("Your Supabase role can view the workflow but cannot create rejection dry-runs.")
    else:
        rejection_limit = st.number_input(
            "Rejection limit",
            min_value=1,
            max_value=100,
            value=1,
            step=1,
            key="supabase_rejection_limit",
            help="This is a maximum. The actual selected count depends on eligible applications.",
        )
        selection_mode = st.radio(
            "Rejection selection mode",
            [
                "Manual candidate selection",
                "Early process rejection",
                "Reference Check only",
                "Late-stage rejection",
            ],
            key="supabase_rejection_selection_mode",
        )
        reason_option = st.selectbox(
            "Rejection reason",
            REJECTION_REASON_OPTIONS,
            index=REJECTION_REASON_OPTIONS.index("Reference check inconclusive"),
            key="supabase_rejection_reason_option",
        )
        reason_details = st.text_area(
            "Rejection reason details",
            value="" if reason_option == "Other" else reason_option,
            key="supabase_rejection_reason_details",
            placeholder="Explain why these applications should be marked as rejected.",
        )
        rejection_reason = reason_details.strip()
        manual_application_ids: list[int] | None = None
        eligible_applications: list[dict] = []
        key_prefix = "supabase_manual_rejection"

        try:
            eligible_applications = filter_eligible_rejection_applications(
                supabase_ops.list_active_applications_for_stages(
                    REJECTION_OUTCOME_STAGES,
                    limit=5000,
                ),
                selection_mode,
            )
        except RuntimeError as error:
            st.error(str(error))

        mode_default_stages = {
            "Early process rejection": ["Application Review", "Recruiter Interview"],
            "Reference Check only": ["Reference Check"],
            "Late-stage rejection": [
                "Reference Check",
                "Final Interview",
                "Final (Executive) Interview",
                "Offer",
            ],
        }.get(selection_mode)
        rejection_filter_stages = set(mode_default_stages or REJECTION_OUTCOME_STAGES)
        render_candidate_helper_actions(
            show_label="Show eligible rejection candidates",
            select_label="Select demo rejection candidate",
            table_title="Eligible rejection candidates",
            key_prefix=key_prefix,
            applications=eligible_applications,
        )
        manual_application_ids = render_candidate_search_selection(
            outcome="rejected",
            eligible_applications=eligible_applications,
            eligible_stages=rejection_filter_stages,
            key_prefix=key_prefix,
            default_stages=mode_default_stages,
        )

        if manual_application_ids:
            selected_details = get_selected_application_details(
                eligible_applications,
                manual_application_ids,
            )
            render_application_business_table(
                "Business review: selected rejection candidate(s)",
                selected_details,
            )

        if st.button("Create rejection dry-run"):
            if not rejection_reason:
                st.error("Rejection reason is required.")
                return

            effective_selection_mode = (
                "Manual candidate selection"
                if manual_application_ids
                else selection_mode
            )

            if effective_selection_mode == "Manual candidate selection":
                if not manual_application_ids:
                    st.error("Select at least one application for manual rejection outcome.")
                    return

            try:
                request_id = supabase_ops.create_rejection_outcome_dry_run(
                    selection_mode=effective_selection_mode,
                    requested_limit=len(manual_application_ids)
                    if effective_selection_mode == "Manual candidate selection"
                    else int(rejection_limit),
                    reason=rejection_reason,
                    application_ids=manual_application_ids
                    if effective_selection_mode == "Manual candidate selection"
                    else None,
                )
                st.session_state["selected_rejection_outcome_request_id"] = request_id
                st.session_state["last_created_rejection_request_id"] = request_id
                st.success(f"New rejection dry-run created: {request_id}")
            except RuntimeError as error:
                st.error(str(error))

    try:
        recent_requests = supabase_ops.list_recent_outcome_change_requests(
            outcome="rejected"
        )
    except RuntimeError as error:
        st.error(str(error))
        return

    request_options = [request["request_id"] for request in recent_requests]

    if request_options:
        selected_request_id = select_request_id(
            "Select rejection request_id",
            request_options,
            "selected_rejection_outcome_request_id",
            "supabase_rejection_request_select",
        )
        render_latest_request_consistency(
            selected_request_id,
            st.session_state.get("last_created_rejection_request_id"),
        )
        render_request_id_copy_block(
            selected_request_id,
            "Selected rejection request_id to copy",
        )
    else:
        selected_request_id = st.session_state.get(
            "selected_rejection_outcome_request_id"
        )

    if not selected_request_id:
        return

    try:
        request = supabase_ops.get_outcome_change_request(selected_request_id)
        items = supabase_ops.list_outcome_request_items(selected_request_id)
    except RuntimeError as error:
        st.error(str(error))
        return

    if not request or request.get("outcome") != "rejected":
        st.info("No Supabase rejection outcome request selected.")
        return

    st.caption(f"Authoritative rejection outcome status from Supabase: {request.get('status')}")
    render_supabase_outcome_summary(request, items)

    if not can_approve(role):
        st.info("Your Supabase role cannot approve rejection outcome requests.")
    elif request.get("status") != "dry_run":
        st.info(f"Rejection approval is unavailable for status: {request.get('status')}.")
    else:
        st.write("Review rejection outcome summary before approval")
        render_supabase_outcome_summary(request, items)
        approved = st.checkbox(
            "I confirm that this rejection outcome has been reviewed and approved.",
            key="supabase_rejection_approval_checkbox",
        )
        typed_request_id = st.text_input(
            "Type the rejection request_id to approve",
            key="supabase_rejection_approval_request_id",
        )
        st.caption("Paste the selected UUID request_id. Do not paste application IDs.")

        if looks_like_application_ids(typed_request_id):
            st.error(
                "This looks like application IDs. Please paste the request_id UUID instead."
            )

        if st.button("Approve rejection outcome request"):
            if not approved:
                st.error("Approval checkbox is required.")
                return

            if looks_like_application_ids(typed_request_id):
                st.error(
                    "This looks like application IDs. Please paste the request_id UUID instead."
                )
                return

            if typed_request_id != selected_request_id:
                st.error("The typed request_id does not match.")
                return

            try:
                supabase_ops.approve_rejection_outcome_request(selected_request_id)
                authoritative_request = supabase_ops.get_outcome_change_request(
                    selected_request_id
                )

                if (
                    authoritative_request
                    and authoritative_request.get("status") == "approved"
                    and authoritative_request.get("approved_by_email")
                    and authoritative_request.get("approved_at")
                ):
                    request = authoritative_request
                    st.success("Supabase rejection outcome request approved.")
                    st.caption(
                        "Authoritative rejection outcome status from Supabase: "
                        f"{request.get('status')}"
                    )
                else:
                    st.error(
                        "Approval RPC returned, but the authoritative Supabase row "
                        "does not show a fully approved rejection outcome request."
                    )
            except RuntimeError as error:
                st.error(str(error))

    request_status = request.get("status")

    if request_status == "dry_run":
        st.info("Rejection apply is disabled until the Supabase request is approved.")
    elif request_status == "applied":
        st.info("This rejection outcome request has already been applied.")
    elif request_status == "partially_applied":
        st.info("This rejection outcome request was partially applied. Review audit details.")
    elif request_status == "failed":
        st.info("This rejection outcome request failed. Review audit details.")
    elif request_status == "cancelled":
        st.info("This rejection outcome request was cancelled.")
    elif request_status != "approved":
        st.info(f"Rejection apply is unavailable for status: {request_status}.")
    elif not get_flag("ALLOW_SUPABASE_PROD_APPLY"):
        st.info("Rejection apply is disabled unless ALLOW_SUPABASE_PROD_APPLY=true.")
    elif not can_apply(role):
        st.info("Your Supabase role cannot apply rejection outcome requests.")
    else:
        typed_request_id = st.text_input(
            "Type the rejection request_id to apply",
            key="supabase_rejection_apply_request_id",
        )

        if st.button("Apply rejection outcome"):
            if typed_request_id != selected_request_id:
                st.error("The typed request_id does not match.")
                return

            try:
                supabase_ops.apply_rejection_outcome_request(selected_request_id)
                st.success("Supabase rejection outcome applied.")
                st.rerun()
            except RuntimeError as error:
                st.error(str(error))


def render_supabase_pipeline_button():
    if not get_flag("ALLOW_SUPABASE_PIPELINE_TRIGGER"):
        return

    st.subheader("Supabase analytics refresh")
    st.warning(
        "This runs the Supabase-to-BigQuery analytics pipeline. BigQuery will be "
        "updated only after ingestion from Supabase."
    )

    if st.button("Run Supabase ingestion pipeline"):
        try:
            result = subprocess.run(
                ["./scripts/run_supabase_recruitment_pipeline.sh"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=900,
                check=False,
            )
            st.code(result.stdout or "(no stdout)", language="bash")

            if result.stderr:
                st.code(result.stderr, language="bash")

            if result.returncode == 0:
                st.success("Supabase ingestion pipeline completed successfully.")
            else:
                st.error(
                    f"Supabase ingestion pipeline failed with exit code {result.returncode}."
                )
        except subprocess.TimeoutExpired as error:
            st.error("Supabase ingestion pipeline timed out after 15 minutes.")
            if error.stdout:
                st.code(error.stdout, language="bash")
            if error.stderr:
                st.code(error.stderr, language="bash")


def render_airflow_analytics_refresh(user_email: str):
    if not get_flag("ENABLE_ADMIN_AIRFLOW_TRIGGER"):
        return

    st.subheader("6. Trigger analytics refresh")
    st.warning(
        "This button triggers Airflow through its REST API. In production, this "
        "should use a secured service account, token-based authentication, and "
        "environment-specific DAG permissions."
    )

    if not is_airflow_trigger_available():
        st.info(
            "Airflow trigger is disabled until USE_SUPABASE_OPERATIONAL_SOURCE=true, "
            "ENABLE_ADMIN_CHANGE_WORKFLOW=true, BQ_MARTS_DATASET=marts_recruitment_demo "
            f"and AIRFLOW_DAG_ID={DEMO_AIRFLOW_DAG_ID}."
        )
        return

    st.caption(f"Airflow DAG: {DEMO_AIRFLOW_DAG_ID}")
    st.json(DEMO_DATASETS)

    if st.button("Trigger Airflow analytics refresh"):
        try:
            response = trigger_airflow_demo_dag(user_email)
            dag_run_id = response.get("dag_run_id")
            triggered_at = datetime.now(timezone.utc).replace(microsecond=0)

            if dag_run_id:
                st.session_state["airflow_last_dag_run_id"] = dag_run_id
                st.session_state["airflow_demo_dag_run_id"] = dag_run_id
                st.session_state["airflow_started_at"] = triggered_at.isoformat()
                st.session_state["airflow_monitoring_enabled"] = True
                st.session_state["airflow_last_checked_at"] = triggered_at.isoformat()
                st.session_state["airflow_last_response"] = response
                st.session_state["airflow_last_state"] = str(
                    response.get("state") or "queued"
                )

            st.success("Airflow DAG run was triggered successfully.")
            st.json(
                {
                    "dag_run_id": dag_run_id,
                    "logical_date": response.get("logical_date"),
                    "state": response.get("state"),
                }
            )
        except RuntimeError as error:
            st.error(f"Airflow DAG trigger failed: {error}")

    dag_run_id = st.session_state.get("airflow_last_dag_run_id") or st.session_state.get(
        "airflow_demo_dag_run_id"
    )

    if not dag_run_id:
        return

    monitoring_enabled = bool(st.session_state.get("airflow_monitoring_enabled"))
    current_state = st.session_state.get("airflow_last_state")

    if (
        hasattr(st, "fragment")
        and monitoring_enabled
        and current_state not in AIRFLOW_TERMINAL_STATES
    ):
        render_airflow_auto_monitor_fragment()
    else:
        render_airflow_status_panel()

    render_airflow_manual_status_check()
    render_airflow_api_debug()


def render_supabase_operational_workflow():
    st.warning(
        "Supabase is the operational source of truth for this SaaS-like demo. "
        "BigQuery will be updated only after ingestion."
    )

    if not get_flag("ENABLE_SUPABASE_AUTH"):
        st.info("ENABLE_SUPABASE_AUTH must be true to use the Supabase workflow.")
        return

    user = render_supabase_auth_panel()

    if not user:
        return

    user_email = user.get("email", "")

    try:
        role = get_supabase_role(user_email)
    except RuntimeError as error:
        st.error(str(error))
        return

    st.caption(f"Supabase role: {role}")

    st.subheader("1. Supabase dry-run")
    st.warning(
        "This workflow changes recruitment stages only. Hired and Rejected outcomes "
        "are intentionally excluded from this demo."
    )

    if not can_dry_run(role):
        st.info("Your Supabase role can view the workflow but cannot create dry-runs.")
    else:
        target_stage = st.selectbox(
            "Target stage",
            ALLOWED_RECRUITMENT_STAGES,
            index=ALLOWED_RECRUITMENT_STAGES.index(DEFAULT_TARGET_STAGE),
            key="supabase_target_stage",
        )
        next_stage = st.selectbox(
            "Optional next stage",
            ALLOWED_RECRUITMENT_STAGES,
            index=ALLOWED_RECRUITMENT_STAGES.index(DEFAULT_NEXT_STAGE),
            key="supabase_next_stage",
        )
        invalid_stage_transition = target_stage == next_stage

        if invalid_stage_transition:
            st.error("Target stage and next stage must be different.")

        selection_mode = st.radio(
            "Selection mode",
            [FOCUSED_GROUP_MODE, GLOBAL_IMPACT_MODE, "Manual application selection"],
            key="supabase_selection_mode",
        )
        requested_limit = st.number_input(
            "Application limit",
            min_value=10,
            max_value=500,
            value=100,
            step=10,
            key="supabase_application_limit",
            help="This is a maximum. The actual selected count depends on eligible applications.",
        )
        manual_application_ids: list[int] | None = None
        stage_eligible_applications: list[dict] = []
        stage_key_prefix = "supabase_stage_change_manual"

        try:
            stage_eligible_applications = filter_eligible_stage_change_applications(
                supabase_ops.list_active_applications(limit=5000),
                target_stage,
                next_stage,
            )
        except RuntimeError as error:
            st.error(str(error))

        render_candidate_helper_actions(
            show_label="Show eligible stage-change applications",
            select_label="Select demo stage-change application",
            table_title="Eligible stage-change applications",
            key_prefix=stage_key_prefix,
            applications=stage_eligible_applications,
            target_stage=target_stage,
            next_stage=next_stage,
        )

        current_stage_options = {
            str(application.get("current_stage"))
            for application in stage_eligible_applications
            if application.get("current_stage")
        }
        manual_application_ids = render_candidate_search_selection(
            outcome="stage change",
            eligible_applications=stage_eligible_applications,
            eligible_stages=current_stage_options,
            key_prefix=stage_key_prefix,
        )

        if manual_application_ids:
            selected_details = get_selected_application_details(
                stage_eligible_applications,
                manual_application_ids,
            )
            render_application_business_table(
                "Business review: selected stage-change application(s)",
                selected_details,
                target_stage=target_stage,
                next_stage=next_stage,
            )

        reason = st.text_area(
            "Reason for change",
            key="supabase_change_reason",
            placeholder="Explain why this operational change is required.",
        )

        if st.button("Create Supabase dry-run", disabled=invalid_stage_transition):
            if not reason.strip():
                st.error("Reason for change is required.")
                return

            if invalid_stage_transition:
                st.error("Target stage and next stage must be different.")
                return

            effective_selection_mode = (
                "Manual application selection"
                if manual_application_ids
                else selection_mode
            )

            if effective_selection_mode == "Manual application selection":
                if not manual_application_ids:
                    st.error("Select at least one application for manual stage change.")
                    return

            try:
                request_id = supabase_ops.create_stage_change_dry_run(
                    target_stage=target_stage,
                    next_stage=next_stage,
                    selection_mode=effective_selection_mode,
                    requested_limit=int(requested_limit),
                    reason=reason.strip(),
                    application_ids=manual_application_ids
                    if effective_selection_mode == "Manual application selection"
                    else None,
                )
                st.session_state["selected_stage_change_request_id"] = request_id
                st.session_state["last_created_stage_change_request_id"] = request_id
                st.session_state["supabase_change_request_id"] = request_id
                st.success(f"Supabase dry-run created: {request_id}")
            except RuntimeError as error:
                st.error(str(error))

    recent_requests = []

    try:
        recent_requests = supabase_ops.list_recent_stage_change_requests()
    except RuntimeError as error:
        st.error(str(error))

    request_options = [request["request_id"] for request in recent_requests]
    fallback_request_id = st.session_state.get("supabase_change_request_id")

    if (
        "selected_stage_change_request_id" not in st.session_state
        and fallback_request_id
    ):
        st.session_state["selected_stage_change_request_id"] = fallback_request_id

    if request_options:
        selected_request_id = select_request_id(
            "Stage change request",
            request_options,
            "selected_stage_change_request_id",
            "supabase_change_request_select",
        )
        st.session_state["supabase_change_request_id"] = selected_request_id
        render_latest_request_consistency(
            selected_request_id,
            st.session_state.get("last_created_stage_change_request_id"),
        )
        render_request_id_copy_block(
            selected_request_id,
            "Copy stage-change request_id",
        )
    else:
        selected_request_id = st.session_state.get("selected_stage_change_request_id")

    if not selected_request_id:
        render_supabase_pipeline_button()
        return

    try:
        request = supabase_ops.get_stage_change_request(selected_request_id)
        items = supabase_ops.list_request_items(selected_request_id)
    except RuntimeError as error:
        st.error(str(error))
        render_supabase_pipeline_button()
        return

    if not request:
        st.info("No Supabase change request selected.")
        render_supabase_pipeline_button()
        return

    st.caption(f"Authoritative request status from Supabase: {request.get('status')}")
    render_supabase_request_summary(request, items)

    st.subheader("2. Supabase approve")

    if not can_approve(role):
        st.info("Your Supabase role cannot approve requests.")
    elif request.get("status") != "dry_run":
        st.info(f"Approval is unavailable for status: {request.get('status')}.")
    else:
        st.write("Review summary before approval")
        render_supabase_request_summary(request, items)

        approved = st.checkbox(
            "I confirm that this Supabase change has been reviewed and approved.",
            key="supabase_approval_checkbox",
        )
        typed_request_id = st.text_input(
            "Type the request_id to approve",
            key="supabase_approval_request_id",
        )

        if st.button("Approve Supabase request"):
            if not approved:
                st.error("Approval checkbox is required.")
                return

            if typed_request_id != selected_request_id:
                st.error("The typed request_id does not match.")
                return

            try:
                supabase_ops.approve_stage_change_request(selected_request_id)
                authoritative_request = supabase_ops.get_stage_change_request(
                    selected_request_id
                )

                if authoritative_request:
                    request = authoritative_request

                if (
                    authoritative_request
                    and authoritative_request.get("status") == "approved"
                    and authoritative_request.get("approved_by_email")
                    and authoritative_request.get("approved_at")
                ):
                    st.success("Supabase request approved.")
                    st.caption(
                        "Authoritative request status from Supabase: "
                        f"{authoritative_request.get('status')}"
                    )
                else:
                    st.error(
                        "Approval RPC returned, but the authoritative Supabase row "
                        "does not show a fully approved request."
                    )
            except RuntimeError as error:
                st.error(str(error))

    st.subheader("3. Supabase apply")
    st.caption(
        "Rollback for operational state changes is a compensating action. Supabase "
        "stage events keep previous stages for authorized compensation if required."
    )

    request_status = request.get("status")

    if request_status == "dry_run":
        st.info("Apply is disabled until the Supabase request is approved.")
    elif request_status == "applied":
        st.info("This request has already been applied.")
    elif request_status == "partially_applied":
        st.info("This request was partially applied. Review audit details.")
    elif request_status == "failed":
        st.info("This request failed. Review audit details.")
    elif request_status == "cancelled":
        st.info("This request was cancelled.")
    elif request_status != "approved":
        st.info(f"Apply is unavailable for status: {request_status}.")
    elif not get_flag("ALLOW_SUPABASE_PROD_APPLY"):
        st.info("Apply is disabled unless ALLOW_SUPABASE_PROD_APPLY=true.")
    elif not can_apply(role):
        st.info("Your Supabase role cannot apply requests.")
    else:
        typed_request_id = st.text_input(
            "Type the request_id to apply",
            key="supabase_apply_request_id",
        )

        if st.button("Apply Supabase source changes"):
            if typed_request_id != selected_request_id:
                st.error("The typed request_id does not match.")
                return

            try:
                supabase_ops.apply_stage_change_request(selected_request_id)
                st.success("Supabase source changes applied.")
                st.rerun()
            except RuntimeError as error:
                st.error(str(error))

    render_supabase_hiring_outcome_workflow(role)
    render_supabase_rejection_outcome_workflow(role)
    render_airflow_analytics_refresh(user_email)
    render_supabase_pipeline_button()


def render_admin_change_workflow():
    if not get_flag("ENABLE_ADMIN_CHANGE_WORKFLOW"):
        return

    with st.sidebar.expander("Admin production change workflow", expanded=False):
        st.warning(
            "Admin workflow hidden by default. Operational changes are applied only "
            "to the configured source API, never directly to BigQuery."
        )
        operational_source = st.radio(
            "Operational source",
            ["Mock API", "Supabase operational source"],
            index=1 if get_flag("USE_SUPABASE_OPERATIONAL_SOURCE") else 0,
        )

        if operational_source == "Supabase operational source":
            if not get_flag("USE_SUPABASE_OPERATIONAL_SOURCE"):
                st.info(
                    "Set USE_SUPABASE_OPERATIONAL_SOURCE=true to enable the Supabase path."
                )
                return

            render_supabase_operational_workflow()
            return

        if not render_authentication_panel():
            return

        api_base_url = get_source_api_base_url()

        if api_base_url is None:
            return

        st.caption(f"Source API: {api_base_url}")

        email = st.session_state["admin_email"]
        role = st.session_state["admin_role"]

        render_dry_run(api_base_url, email, role)

        report_path_value = st.session_state.get("admin_report_path")

        if report_path_value:
            report_path = Path(report_path_value)

            if report_path.exists():
                report = load_report(report_path)
                render_approval(report, report_path, email, role)
                report = load_report(report_path)
                render_apply(api_base_url, report, report_path, email, role)
            else:
                st.error("Saved admin report path no longer exists.")

        render_production_pipeline_button()
