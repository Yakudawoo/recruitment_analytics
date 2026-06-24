# Recruitment Analytics Dashboard — Final Solution Summary

## 1. Business objective

The goal is to provide HR managers with a custom recruitment analytics dashboard on top of Greenhouse-like recruitment data.

The dashboard allows HR users to analyze recruitment activity in the context of selected offices, departments and recruiters.

## 2. Dashboard capabilities

The dashboard provides the following capabilities:

1. Application status distribution by office and department.
2. Recruitment funnel analysis by stage.
3. Executive overview of jobs, applications, offers and hires.
4. Recruiter workload monitoring.
5. Recruiter SLA compliance on recruiter-owned stages.
6. Recruiter SLA breach detection at application level.
7. Average recruiter response time by stage.
8. Office, department and recruiter scoped filtering.

## 3. Target architecture

```text
Greenhouse API / Webhooks
    ↓
Workato recipes
    ↓
BigQuery RAW
    ↓
Airflow orchestration
    ↓
dbt STAGING
    ↓
dbt CORE
    ↓
dbt MARTS
    ↓
Looker / Dashboarding
4. Implemented demo architecture
Mock Greenhouse API
    ↓
Workato API Sync Simulator
    ↓
BigQuery RAW
    ↓
Airflow orchestration
    ↓
dbt STAGING
    ↓
dbt CORE
    ↓
dbt MARTS
    ↓
Streamlit Dashboard on Hugging Face
5. Important implementation note

The provided Excel and JSON files are not used directly by the dashboard.

They are used only as seed data to emulate Greenhouse API and webhook payloads. The downstream pipeline consumes API-like endpoints, loads BigQuery RAW tables, and transforms the data with dbt.

6. BigQuery layers
RAW

Stores source-aligned Greenhouse-like data with ingestion metadata.

STAGING

Cleans and standardizes raw data:

type casting;
column renaming;
timestamp normalization;
one staging model per source table.
CORE

Builds the business model:

job dimension;
candidate dimension;
recruiter dimension;
office dimension;
department dimension;
application fact;
offer fact;
stage transition fact.
MARTS

Provides dashboard-ready tables:

executive overview;
application status by office and department;
recruitment funnel;
recruitment funnel by office and department;
recruiter workload;
recruiter SLA performance;
SLA breaches.
7. Data quality

dbt tests validate:

non-null business keys;
uniqueness of dimensions;
fact table identifiers;
source constraints;
mart readiness.

Final dbt test result:

PASS=71
WARN=0
ERROR=0
TOTAL=71
8. Orchestration

Airflow orchestrates:

Mock Greenhouse API health check.
API-to-BigQuery RAW ingestion.
dbt staging models.
dbt core models.
dbt marts.
dbt tests.
9. Deployment

The public demo is deployed as a Hugging Face Docker Space running Streamlit.

The dashboard connects live to BigQuery marts using a dedicated read-only service account.

10. Cost and security controls

The following controls are implemented:

dedicated Hugging Face service account;
BigQuery Job User at project level;
BigQuery Data Viewer limited to marts_recruitment;
no access to RAW/STAGING/CORE datasets;
maximum_bytes_billed = 100 MB per dashboard query;
Streamlit cache set to 30 minutes;
BigQuery daily query quota reduced;
Google Cloud budget alert configured;
no GCP key or secret committed to Git.
