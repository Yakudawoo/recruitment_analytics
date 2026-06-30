# Recruitment Analytics Solution Outline

## 1. Problem Statement

Recruitment teams need a reliable way to monitor funnel health, recruiter workload, SLA compliance, and hiring outcomes across offices and departments.

The key challenge is to separate operational actions from analytics: source-of-truth changes should happen in the operational system, while BigQuery should remain the analytical warehouse consumed by reporting marts.

## 2. Proposed Solution

I implemented a production-like workflow aligned with Teads' stack.

The demo provides:

- a Greenhouse-like generated recruitment dataset;
- a Mock Greenhouse API;
- a Supabase operational source-of-truth layer;
- Supabase Auth and app roles;
- controlled admin workflows with dry-run, approve, apply, and auditability;
- Airflow orchestration;
- BigQuery analytics layers;
- dbt staging/core/marts transformations;
- a Streamlit dashboard deployed on Hugging Face.

## 3. Data Architecture

Implemented demo architecture:

```text
Generated dataset / Mock Greenhouse API
    -> Supabase operational source of truth
    -> Airflow orchestration
    -> BigQuery RAW
    -> dbt STAGING
    -> dbt CORE
    -> dbt MARTS
    -> Streamlit dashboard
```

Target production mapping:

```text
Greenhouse API / Webhooks
    -> Workato recipes
    -> BigQuery
    -> Airflow / dbt
    -> Looker or BI layer
```

I did not use real Workato recipes; I simulated the ingestion/orchestration pattern. I did not implement Looker; Streamlit is the demo BI layer.

## 4. Analytics Layer

BigQuery is treated as the analytics warehouse, not as an operational source.

Data is organized into:

- RAW: source-aligned ingested data.
- STAGING: cleaning, renaming, typing, timestamp normalization.
- CORE: analytical entities and facts.
- MARTS: dashboard-ready business tables.

Main marts:

- `mart_hr_executive_overview`
- `mart_hr_executive_overview_by_office_department`
- `mart_application_status_by_office_department`
- `mart_recruitment_funnel`
- `mart_recruitment_funnel_by_office_department`
- `mart_recruiter_workload`
- `mart_recruiter_performance`
- `mart_sla_breaches`
- `mart_time_to_hire_diagnostics` when present

BigQuery location is kept in the EU with `BQ_LOCATION=EU`.

## 5. Operational Workflow Extension

Supabase is used to demonstrate controlled operational changes with authentication, roles, dry-runs, approvals, and auditability.

Implemented workflows:

1. Stage-change workflow
   - Changes recruitment stages only.
   - Excludes `Hired` and `Rejected` from stages.
   - Supports candidate/application search and manual selection.
   - Follows dry-run -> approve -> apply.

2. Hiring outcome workflow
   - Marks eligible active applications as `hired`.
   - Treats `Hired` as a terminal outcome/status.
   - After analytics refresh, Hired increases and Active decreases.

3. Rejection outcome workflow
   - Marks eligible active applications as `rejected`.
   - Treats `Rejected` as a terminal outcome/status.
   - Supports business reasons such as reference check inconclusive or process stopped.
   - After analytics refresh, Rejected increases and Active decreases.

The admin UI exposes business-readable candidate rows. Technical identifiers remain available in audit sections.

## 6. Dashboard Capabilities

The Streamlit dashboard includes:

- executive overview;
- application status distribution;
- recruitment funnel;
- recruiter workload;
- recruiter responsiveness and performance;
- SLA compliance;
- SLA breach details;
- time-to-hire analysis;
- office and department filtering;
- candidate-level drilldowns where available.

## 7. SLA Logic

Recruiter-owned stages include:

- `Application Review`
- `Recruiter Interview`

SLA target:

- maximum 3 days per recruiter-owned stage.

The model uses stage transition events to calculate time spent in each SLA-tracked stage, flag breaches, and aggregate compliance by recruiter, office, and department.

Rejections are not forced to change SLA metrics artificially. SLA metrics change only if the rejected application closes or affects an SLA-tracked stage.

## 8. Recruiter Workload and Performance Logic

Recruiter workload focuses on active recruitment activity and recruiter-owned responsibilities. Outcome changes such as hired or rejected candidates can reduce active workload after Supabase changes are ingested and dbt marts are rebuilt.

Recruiter performance and responsiveness are derived from stage movement and timing data. The dashboard supports filtering by organizational scope to identify workload concentration and bottlenecks.

## 9. Productionization Path

To productionize this pattern:

1. Replace the Mock Greenhouse API with real Greenhouse API/webhooks.
2. Replace the custom demo sync with Workato recipes.
3. Keep BigQuery as the analytical warehouse.
4. Keep Airflow/dbt for orchestration and transformations.
5. Move the BI layer to Looker or another governed BI tool if required.
6. Harden authentication, service accounts, secrets management, monitoring, and alerting.

## 10. Security and Governance

The demo includes:

- Supabase Auth;
- app roles;
- guarded admin workflows;
- dry-run before mutation;
- explicit approval before apply;
- audit logs and request IDs;
- environment-variable gates for admin actions and Airflow triggers.

Security principles:

- Do not commit `.env` files or service account JSON files.
- Do not expose `SUPABASE_SERVICE_ROLE_KEY` in Streamlit.
- Do not write operational mutations directly to BigQuery.
- Use temporary roles for external reviewers and revoke them after testing.

## 11. Demo Scenario

Recommended hiring scenario:

1. Open the dashboard and show current KPIs.
2. Open the Supabase hiring outcome workflow.
3. Show eligible hiring candidates.
4. Select a demo candidate or manually search/select one.
5. Enter a reason.
6. Create dry-run.
7. Approve.
8. Apply.
9. Trigger Airflow analytics refresh from Streamlit.
10. Wait for Airflow success.
11. Click `Refresh BigQuery data`.
12. Confirm Hired increased and Active decreased.

Optional scenarios:

- rejection outcome workflow;
- stage-change workflow;
- recruiter workload/SLA impact after refresh.

## 12. Implemented vs Production Target

Implemented:

- generated Greenhouse-like dataset;
- Mock Greenhouse API;
- Supabase operational source-of-truth simulation;
- Supabase Auth and role model;
- controlled stage-change, hiring, and rejection workflows;
- candidate search and eligibility logic;
- Airflow DAG trigger through REST API from Streamlit;
- Supabase to BigQuery ingestion;
- dbt layers and dashboard marts;
- Streamlit dashboard on Hugging Face.

Production target equivalent:

- Greenhouse API/webhooks instead of Mock Greenhouse API;
- Workato recipes instead of demo ingestion/sync patterns;
- Looker or another BI layer instead of Streamlit if required;
- managed secrets, service accounts, monitoring, audit controls, and environment-specific deployment permissions.
