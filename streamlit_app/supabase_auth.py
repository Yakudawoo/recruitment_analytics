import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

import streamlit as st


def get_supabase_config() -> tuple[str | None, str | None]:
    return os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_ANON_KEY")


def is_supabase_auth_enabled() -> bool:
    return os.getenv("ENABLE_SUPABASE_AUTH", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
        "on",
    }


def _auth_request(
    endpoint: str,
    payload: dict[str, Any],
    access_token: str | None = None,
) -> dict[str, Any]:
    supabase_url, anon_key = get_supabase_config()

    if not supabase_url or not anon_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_ANON_KEY are required.")

    headers = {
        "apikey": anon_key,
        "Authorization": f"Bearer {access_token or anon_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    request = urllib.request.Request(
        f"{supabase_url.rstrip('/')}/auth/v1/{endpoint.lstrip('/')}",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8")
        raise RuntimeError(f"Supabase Auth request failed: {error.code} {detail}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Supabase Auth request failed: {error.reason}") from error


def sign_in_with_password(email: str, password: str) -> dict[str, Any]:
    return _auth_request(
        "token?grant_type=password",
        {
            "email": email,
            "password": password,
        },
    )


def send_magic_link(email: str) -> dict[str, Any]:
    redirect_to = os.getenv("SUPABASE_REDIRECT_URL") or None
    payload: dict[str, Any] = {
        "email": email,
        "should_create_user": False,
    }

    if redirect_to:
        payload["options"] = {"email_redirect_to": redirect_to}

    return _auth_request("otp", payload)


def build_google_oauth_url() -> str | None:
    supabase_url, anon_key = get_supabase_config()

    if not supabase_url or not anon_key:
        return None

    redirect_to = os.getenv("SUPABASE_REDIRECT_URL", "")
    query = urllib.parse.urlencode(
        {
            "provider": os.getenv("SUPABASE_AUTH_PROVIDER", "google"),
            "redirect_to": redirect_to,
        }
    )

    # TODO: complete OAuth callback parsing for Streamlit once the deployment URL is stable.
    return f"{supabase_url.rstrip('/')}/auth/v1/authorize?{query}"


def get_current_supabase_user() -> dict[str, Any] | None:
    return st.session_state.get("supabase_user")


def get_current_supabase_access_token() -> str | None:
    return st.session_state.get("supabase_access_token")


def clear_supabase_session():
    for key in [
        "supabase_user",
        "supabase_access_token",
        "supabase_refresh_token",
    ]:
        st.session_state.pop(key, None)


def render_supabase_auth_panel() -> dict[str, Any] | None:
    if not is_supabase_auth_enabled():
        return None

    st.info(
        "SaaS-like Supabase Auth layer. Google OAuth can be configured in Supabase; "
        "this Streamlit pass supports email/password and magic link first."
    )

    existing_user = get_current_supabase_user()

    if existing_user:
        email = existing_user.get("email", "authenticated user")
        st.success(f"Signed in with Supabase as {email}.")

        if st.button("Sign out Supabase"):
            clear_supabase_session()
            st.rerun()

        return existing_user

    oauth_url = build_google_oauth_url()

    if oauth_url:
        st.link_button("Open Google sign-in", oauth_url)
        st.caption("TODO: handle the Google OAuth callback directly in Streamlit.")

    auth_mode = st.radio(
        "Supabase sign-in method",
        ["Email/password", "Magic link"],
        horizontal=True,
    )
    email = st.text_input("Supabase email", key="supabase_auth_email")

    if auth_mode == "Email/password":
        password = st.text_input(
            "Supabase password",
            type="password",
            key="supabase_auth_password",
        )

        if st.button("Sign in with Supabase"):
            try:
                payload = sign_in_with_password(email, password)
                user = payload.get("user") or {}
                st.session_state["supabase_user"] = user
                st.session_state["supabase_access_token"] = payload.get("access_token")
                st.session_state["supabase_refresh_token"] = payload.get("refresh_token")
                st.success("Supabase sign-in successful.")
                st.rerun()
            except RuntimeError as error:
                st.error(str(error))
    else:
        if st.button("Send magic link"):
            try:
                send_magic_link(email)
                st.success("Magic link requested. Check the configured email inbox.")
            except RuntimeError as error:
                st.error(str(error))

    return None
