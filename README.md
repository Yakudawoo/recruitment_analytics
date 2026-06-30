# Recruitment Analytics Dashboard

Production-like recruitment analytics project inspired by Greenhouse data.

The project helps HR and business users analyze recruitment performance, recruiter workload, SLA compliance, time to hire, and funnel health across offices and departments. It also demonstrates controlled operational workflows through Supabase before analytics are refreshed in BigQuery/dbt.

## Live Dashboard

- Live Hugging Face dashboard: https://ok-fintech-recruitment-analytics-dashboard.hf.space
- GitHub repository: https://github.com/Yakudawoo/recruitment_analytics

The public dashboard is a Streamlit demo UI connected to BigQuery marts. Admin mutation controls are guarded by environment variables and authentication.

## Main Capabilities

- Executive overview of recruitment KPIs.
- Applications by status and recruitment stage.
- Recruitment funnel analysis.
- Recruiter workload monitoring.
- Recruiter performance and responsiveness.
- SLA breaches and SLA compliance.
- Time-to-hire analysis.
- Office and department filtering.
- Candidate-level drilldowns where data is available.

## Operational Admin Workflows

Supabase is used to simulate a SaaS-like operational source of truth. BigQuery remains analytics-only: operational changes are never written directly to BigQuery from Streamlit.

### Stage-Change Workflow

- Changes recruitment stages only.
- `Hired` and `Rejected` are intentionally excluded from stage selection.
- Supports dry-run -> approve -> apply.
- Supports candidate/application search and manual selection.
- Creates auditable request IDs and request items.

### Hiring Outcome Workflow

- Marks eligible active applications as `hired`.
- `Hired` is a terminal outcome/status, not a recruitment stage.
- Supports candidate search and manual selection.
- Supports dry-run -> approve -> apply.
- After Airflow/dbt refresh, Hired Applications should increase and Active Applications should decrease.

### Rejection Outcome Workflow

- Marks eligible active applications as `rejected`.
- `Rejected` is a terminal outcome/status, not a recruitment stage.
- Supports business reasons such as `Reference check inconclusive` and `Process stopped by hiring team`.
- Supports dry-run -> approve -> apply.
- After Airflow/dbt refresh, Rejected Applications should increase and Active Applications should decrease.
- Average Time to Hire excludes rejected applications.

## Candidate Selection UX

Admin users can search and select candidates by business-friendly attributes where available:

- candidate name;
- candidate ID;
- application ID;
- job;
- stage;
- office;
- department;
- recruiter.

The UI displays readable candidate/application rows. Raw request IDs and application IDs remain available in audit/technical sections for traceability, but they are not the main user-facing object.

## Architecture

Implemented demo architecture:

```text
Generated Greenhouse-like dataset
    -> Mock Greenhouse API
    -> Supabase operational source of truth
    -> Airflow orchestration
    -> BigQuery RAW / STG / CORE / MARTS
    -> dbt transformations
    -> Streamlit dashboard on Hugging Face
```

Target production mapping aligned with the Teads stack:

```text
Greenhouse API / Webhooks
    -> Workato recipes
    -> BigQuery
    -> Airflow / dbt
    -> Looker or BI layer
```

Important clarification:

- Workato and Looker are target production equivalents, not implemented directly in this demo.
- Streamlit is used as the demo BI and admin UI.
- Supabase simulates a SaaS-like operational source of truth with auth, roles, dry-runs, approvals, and auditability.
- BigQuery is treated as the analytics warehouse, not as an operational source.

## Data Layers

Production-style datasets:

- `raw_greenhouse`
- `stg_greenhouse`
- `core_greenhouse`
- `marts_recruitment`

Local demo datasets:

- `raw_greenhouse_demo`
- `stg_greenhouse_demo`
- `core_greenhouse_demo`
- `marts_recruitment_demo`

BigQuery location:

```bash
BQ_LOCATION=EU
```

## Main Marts

Key dashboard marts include:

- `mart_hr_executive_overview`
- `mart_hr_executive_overview_by_office_department`
- `mart_application_status_by_office_department`
- `mart_recruitment_funnel`
- `mart_recruitment_funnel_by_office_department`
- `mart_recruiter_workload`
- `mart_recruiter_performance`
- `mart_sla_breaches`
- `mart_time_to_hire_diagnostics` when enabled/present

## Environment Variables

Do not commit `.env` files or service account JSON files.

Core analytics:

```bash
GCP_PROJECT_ID=
GOOGLE_APPLICATION_CREDENTIALS=
BQ_LOCATION=EU
BQ_RAW_DATASET=
BQ_STG_DATASET=
BQ_CORE_DATASET=
BQ_MARTS_DATASET=
BQ_MAXIMUM_BYTES_BILLED=
```

Supabase operational source:

```bash
USE_SUPABASE_OPERATIONAL_SOURCE=
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
ENABLE_SUPABASE_AUTH=
ENABLE_ADMIN_CHANGE_WORKFLOW=
ALLOW_SUPABASE_PROD_APPLY=
```

`SUPABASE_SERVICE_ROLE_KEY` is server-side only for ingestion/scripts. It must never be exposed in the Streamlit UI.

Airflow trigger from Streamlit:

```bash
ENABLE_ADMIN_AIRFLOW_TRIGGER=
AIRFLOW_API_BASE_URL=
AIRFLOW_DAG_ID=
AIRFLOW_USERNAME=
AIRFLOW_PASSWORD=
AIRFLOW_BEARER_TOKEN=
```

Security note: keep `.env`, service account JSON files, API tokens, private keys, and passwords out of Git.

## Local Demo Flow

Recommended live demo sequence:

1. Open the executive dashboard.
2. Use Supabase hiring outcome workflow.
3. Select an eligible candidate.
4. Enter a business reason.
5. Create dry-run.
6. Approve.
7. Apply.
8. Trigger Airflow analytics refresh from Streamlit.
9. Wait for Airflow success.
10. Click `Refresh BigQuery data`.
11. Verify Hired Applications increases and Active Applications decreases.
12. Optionally demonstrate the rejection outcome workflow.
13. Optionally demonstrate the stage-change workflow.

## Supabase Seed and Display Enrichment

The project includes scripts to initialize or enrich the Supabase operational tables from the Mock Greenhouse API.

Use full seed only when resetting the operational demo state. To safely enrich candidate/job display fields without resetting operational status or stages:

```bash
python3 scripts/seed_supabase_operational_from_mock_api.py --display-fields-only
```

## Airflow Refresh

The production-like demo path is:

```text
Streamlit admin action
    -> Supabase operational state
    -> Airflow REST API trigger
    -> Supabase ingestion
    -> BigQuery RAW
    -> dbt staging/core/marts
    -> Streamlit dashboard refresh
```

The Streamlit admin UI can trigger the demo Airflow DAG through the Airflow REST API when explicitly enabled. If supported by the installed Streamlit version, the UI automatically monitors the DAG run status.

## Production Safety

- BigQuery is analytics-only.
- Operational changes happen in Supabase for this demo, and would happen in Greenhouse or a controlled backend in production.
- Dry-run and approval steps prevent direct uncontrolled mutations.
- Audit logs, request IDs, and request items provide traceability.
- Admin workflows are guarded by environment variables and roles.
- For external reviewers, privileged roles should be temporary and revoked after testing.
- Demo pipelines should write to `*_demo` datasets unless explicitly configured otherwise.

## Hugging Face Deployment Checklist

1. Set secrets in Hugging Face Space settings.
2. Do not commit `.env`.
3. Do not commit service account JSON files.
4. Ensure `BQ_LOCATION=EU`.
5. Ensure the dashboard points to the intended marts dataset.
6. Keep admin mutation flags disabled by default unless deliberately testing.
7. If Airflow trigger is enabled, the Airflow API must be reachable and secured.
8. Use `SUPABASE_SERVICE_ROLE_KEY` only server-side where needed and never display it.

## Known Limitations

- The dataset is generated/mock data.
- Workato recipes are not implemented directly; the ingestion/orchestration pattern is simulated.
- Looker is not implemented; Streamlit is the demo BI layer.
- Hugging Face is used as the public demo deployment target.
- Airflow trigger from deployed Hugging Face requires a reachable and secured Airflow API if enabled.
- Production deployment would require stronger authentication, secrets management, monitoring, service accounts, and environment-specific permissions.

## Local Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn mock_greenhouse.app:app --reload --port 8000
./scripts/run_recruitment_pipeline.sh
streamlit run streamlit_app/dashboard.py
```
