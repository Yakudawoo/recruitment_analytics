---
title: Recruitment Analytics Dashboard
emoji: 📊
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# Recruitment Analytics Dashboard

Streamlit demo dashboard for recruitment analytics built on BigQuery/dbt marts.

Live dashboard:
https://ok-fintech-recruitment-analytics-dashboard.hf.space

GitHub repository:
https://github.com/Yakudawoo/recruitment_analytics

## Demo Architecture

```text
Generated Greenhouse-like dataset
    -> Mock Greenhouse API
    -> Supabase operational source of truth
    -> Airflow orchestration
    -> BigQuery RAW / STG / CORE / MARTS
    -> dbt transformations
    -> Streamlit dashboard on Hugging Face
```

The production target equivalent is:

```text
Greenhouse API / Webhooks
    -> Workato recipes
    -> BigQuery
    -> Airflow / dbt
    -> Looker or BI layer
```

Workato and Looker are production target equivalents aligned with the intended stack. They are not implemented directly in this demo. Streamlit is used for the demo UI.

## Operational Workflows

The project includes optional Supabase-backed admin workflows:

- stage-change dry-run / approve / apply;
- hiring outcome dry-run / approve / apply;
- rejection outcome dry-run / approve / apply;
- candidate search, eligibility logic, and audit details.

Supabase simulates a SaaS-like operational source of truth. BigQuery remains analytics-only, and operational changes are never written directly to BigQuery from Streamlit.

## Hugging Face Deployment Checklist

1. Set secrets in Hugging Face Space settings.
2. Do not commit `.env`.
3. Do not commit service account JSON files.
4. Ensure `BQ_LOCATION=EU`.
5. Ensure the dashboard points to the intended marts dataset.
6. Keep admin mutation flags disabled by default unless deliberately testing.
7. If Airflow trigger is enabled, the Airflow API must be reachable and secured.
8. Use `SUPABASE_SERVICE_ROLE_KEY` only server-side where needed and never display it.

## Safety Notes

- Public demo mode should remain read-only by default.
- Admin workflows require explicit environment flags and Supabase authentication.
- Demo mutation workflows should use `*_demo` BigQuery datasets unless explicitly configured otherwise.
- Production deployment would require stronger authentication, service accounts, monitoring, and environment-specific permissions.
