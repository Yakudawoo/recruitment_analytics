# Recruitment Analytics Dashboard

Production-like recruitment analytics solution built for a Data Engineer exercise.

The objective is to provide HR managers with a custom analytics layer on top of Greenhouse-like recruitment data, with a focus on office, department and recruiter-level visibility.

## Live dashboard

Hugging Face Space:

https://huggingface.co/spaces/OK-Fintech/recruitment-analytics-dashboard

The public dashboard reads live BigQuery mart tables through a dedicated read-only service account.

## Business scope

The dashboard helps answer questions such as:

- How many applications are active, rejected or hired?
- Where are candidates in the recruitment funnel?
- Which offices and departments generate the most workload?
- Which recruiters are overloaded?
- Which recruiter-owned stages breach the 3-day SLA?
- Which applications are responsible for SLA breaches?

## Dashboard capabilities

The dashboard includes:

1. Application status distribution by office and department.
2. Recruitment funnel analysis by stage.
3. Executive overview of jobs, applications, offers and hires.
4. Recruiter workload monitoring.
5. Recruiter SLA compliance on recruiter-owned stages.
6. Recruiter SLA breach detection at application level.
7. Average recruiter response time by stage.
8. Office, department and recruiter scoped filtering.

## Architecture

Target production architecture:

```text
Greenhouse API / Webhooks
    ↓
Workato recipes
    ↓
BigQuery RAW
    ↓
Airflow orchestration
    ↓
dbt STAGING / CORE / MARTS
    ↓
Looker dashboard
Implemented demo architecture:

Mock Greenhouse API
    ↓
Workato API Sync Simulator
    ↓
BigQuery RAW
    ↓
Airflow DAG
    ↓
dbt STAGING
    ↓
dbt CORE
    ↓
dbt MARTS
    ↓
Streamlit Dashboard on Hugging Face
Important note

The provided Excel and JSON files are only used to seed the Mock Greenhouse API.

The dashboard does not read Excel directly. The downstream pipeline consumes API-like endpoints and event-like payloads, loads BigQuery RAW tables, transforms the data with dbt, and serves dashboard-ready marts.

BigQuery data model

The model is organized into four layers:

RAW

Source-aligned Greenhouse-like tables with ingestion metadata.

STAGING

Technical cleaning layer:

column renaming;
type casting;
timestamp normalization;
one staging model per source table.
CORE

Analytical business model:

dim_job
dim_candidate
dim_recruiter
dim_office
dim_department
fact_application
fact_offer
fact_stage_transition
MARTS

Dashboard-ready tables:

mart_hr_executive_overview
mart_hr_executive_overview_by_office_department
mart_application_status_by_office_department
mart_recruitment_funnel
mart_recruitment_funnel_by_office_department
mart_recruiter_workload
mart_recruiter_performance
mart_sla_breaches
Recruiter SLA logic

Recruiter-owned stages:

Application Review
Recruiter Interview

SLA target:

maximum 3 days per recruiter-owned stage

Method:

use application stage transition events;
calculate duration between stage entry and next transition;
flag whether SLA is met or breached;
expose application-level SLA breach details in the dashboard.
Data quality

dbt tests validate:

non-null business keys;
uniqueness of dimensions;
fact table identifiers;
source constraints;
dashboard mart readiness.

Final result:

PASS=71
WARN=0
ERROR=0
TOTAL=71
Orchestration

Airflow orchestrates:

Mock Greenhouse API health check.
API-to-BigQuery RAW ingestion.
dbt staging models.
dbt core models.
dbt marts.
dbt tests.
Local run instructions
1. Create environment
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
2. Configure environment variables

Create a local .env file. Do not commit it.

Required variables:

GCP_PROJECT_ID=<your-gcp-project-id>
BQ_LOCATION=EU
BQ_RAW_DATASET=raw_greenhouse
BQ_STAGING_DATASET=stg_greenhouse
BQ_CORE_DATASET=core_greenhouse
BQ_MARTS_DATASET=marts_recruitment
MOCK_GREENHOUSE_BASE_URL=http://127.0.0.1:8000
BQ_MAXIMUM_BYTES_BILLED=100000000
3. Start Mock Greenhouse API
uvicorn mock_greenhouse.app:app --reload --port 8000
4. Run the full pipeline
./scripts/run_recruitment_pipeline.sh
5. Run Streamlit locally
streamlit run streamlit_app/dashboard.py
Security and cost controls

Implemented controls:

dedicated Hugging Face service account;
BigQuery Job User at project level;
BigQuery Data Viewer limited to the dashboard mart dataset;
no RAW/STAGING/CORE read access for the public dashboard service account;
maximum bytes billed set per dashboard query;
Streamlit cache enabled;
BigQuery query quota reduced;
budget alert configured;
no secret committed to Git.
Repository note

Secrets, local environment files, Airflow runtime files and dbt generated artifacts are intentionally excluded from the public repository.
