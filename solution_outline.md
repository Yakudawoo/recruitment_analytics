# Recruitment Analytics Solution Outline

## 1. Objective

The objective is to provide HR managers with a custom recruitment analytics solution on top of Greenhouse-like recruitment data.

The solution focuses on:

- recruitment funnel visibility;
- application status distribution;
- office and department-level analysis;
- recruiter workload;
- recruiter responsiveness;
- SLA breach detection.

## 2. Dashboard capabilities

The dashboard provides the following capabilities:

1. Application status distribution by office and department.
2. Recruitment funnel by stage.
3. Executive overview of jobs, applications, offers and hires.
4. Recruiter workload monitoring.
5. Recruiter SLA compliance on recruiter-owned stages.
6. Recruiter SLA breach detection at application level.
7. Average recruiter response time by stage.
8. Office, department and recruiter filtering.

## 3. Target architecture

Greenhouse API / Webhooks  
→ Workato recipes  
→ BigQuery RAW  
→ Airflow orchestration  
→ dbt STAGING / CORE / MARTS  
→ Looker dashboard  

## 4. Implemented demo architecture

Mock Greenhouse API  
→ Workato API Sync Simulator  
→ BigQuery RAW  
→ Airflow orchestration  
→ dbt STAGING  
→ dbt CORE  
→ dbt MARTS  
→ Streamlit Dashboard on Hugging Face  

The provided Excel and JSON files are only used to seed the Mock Greenhouse API.

The dashboard does not read Excel directly. The downstream pipeline consumes API-like endpoints and event-like payloads, loads BigQuery RAW tables, transforms the data with dbt, and serves dashboard-ready marts.

## 5. Component ownership

| Component | Main owner | Comment |
|---|---|---|
| Greenhouse source system | HR / Business Apps | Source system and business workflow |
| Workato recipes | Integration Team | Production API/webhook integration |
| BigQuery RAW | Data Engineer | Landing layer and ingestion metadata |
| dbt staging/core/marts | Data Engineer | Data modeling and transformation |
| Airflow DAG | Data Engineer / Data Platform | Pipeline orchestration |
| KPI definitions | HR + Data Engineer | Business validation and technical implementation |
| Looker dashboard | BI / Analytics Team | Production visualization layer |
| Streamlit mockup | Data Engineer | Exercise dashboard demo |

## 6. BigQuery data model

The model is organized into RAW, STAGING, CORE and MARTS layers.

### RAW

Source-aligned Greenhouse-like tables with ingestion metadata.

### STAGING

Technical cleaning layer:

- column renaming;
- type casting;
- timestamp normalization;
- one staging model per source table.

### CORE

Analytical business model:

- `dim_job`
- `dim_candidate`
- `dim_recruiter`
- `dim_office`
- `dim_department`
- `fact_application`
- `fact_offer`
- `fact_stage_transition`

### MARTS

Dashboard-ready tables:

- `mart_hr_executive_overview`
- `mart_hr_executive_overview_by_office_department`
- `mart_application_status_by_office_department`
- `mart_recruitment_funnel`
- `mart_recruitment_funnel_by_office_department`
- `mart_recruiter_workload`
- `mart_recruiter_performance`
- `mart_sla_breaches`

## 7. Main table relationships

The main analytical relationships are:

```text
fact_application
    → dim_candidate
    → dim_job
    → dim_recruiter
    → dim_office
    → dim_department

fact_stage_transition
    → fact_application
    → recruiter / office / department context

fact_offer
    → fact_application
These relationships allow the dashboard to analyze applications, offers, stage movements and recruiter responsiveness by office, department and recruiter.

8. Recruiter SLA logic

Recruiter-owned stages:

Application Review
Recruiter Interview

SLA target:

maximum 3 days per recruiter-owned stage.

Method:

calculate the time spent in each recruiter-owned stage using stage transition events;
flag each case as SLA met or breached;
expose SLA breaches at application level;
aggregate recruiter responsiveness by recruiter, office and department.
9. Data quality and orchestration

The pipeline includes:

Airflow orchestration;
dbt transformations;
dbt data quality tests;
BigQuery mart tables consumed by the dashboard.

Final dbt test result:

PASS=71
WARN=0
ERROR=0
TOTAL=71

Airflow orchestrates:

Mock Greenhouse API health check.
API-to-BigQuery RAW ingestion.
dbt staging models.
dbt core models.
dbt marts.
dbt tests.
10. Demo links

Live dashboard:

https://huggingface.co/spaces/OK-Fintech/recruitment-analytics-dashboard

GitHub repository:

https://github.com/Yakudawoo/recruitment_analytics.git

11. Limitations and next steps

Next production steps:

replace Mock Greenhouse API with real Greenhouse API and webhooks;
replace Workato simulator with production Workato recipes;
move the dashboard layer to Looker if required;
make SLA targets configurable in BigQuery;
add incremental loading and operational monitoring.

## 12. Larger synthetic dataset update

Following initial feedback, the dashboard was updated with a larger synthetic Greenhouse-like dataset to make the HR-facing demo more representative.

The larger dataset includes:

- 120 jobs;
- 1,800 candidates;
- 2,500 applications;
- several thousand application stage events;
- offers, recruiters, offices and departments linked consistently.

This dataset preserves the same structure as the original exercise data and keeps the same ingestion and transformation logic:

Mock Greenhouse API  
→ Workato API Sync Simulator  
→ BigQuery RAW  
→ dbt STAGING  
→ dbt CORE  
→ dbt MARTS  
→ Streamlit Dashboard  

The original files provided for the exercise are still preserved. The larger dataset is generated separately and can be selected through the mock API dataset profile.

## 13. Local API simulation demo

A local-only API simulation was added to demonstrate that the dashboard is not based on a static Excel extract.

The simulation triggers controlled stage-change events through the Mock Greenhouse API. The ingestion script then reloads the updated API data into BigQuery RAW, dbt rebuilds the analytical layers, and the dashboard reflects the updated mart tables after refresh.

The demo uses completed stage transitions:

```text
Reference Check
    ↓
Offer
This makes the Reference Check stage visible in the recruitment funnel while avoiding artificial hires or rejections.

The simulation controls are hidden by default and are not enabled on the public Hugging Face dashboard. The public dashboard remains read-only, except for the Refresh BigQuery data button which only clears Streamlit cache and reloads BigQuery mart tables.
