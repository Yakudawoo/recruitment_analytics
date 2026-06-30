import json
import os

import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv
from google.cloud import bigquery
from google.oauth2 import service_account

try:
    from streamlit_app.admin_change_workflow import render_admin_change_workflow
    from streamlit_app.demo_controls import render_demo_controls
except ModuleNotFoundError:
    from admin_change_workflow import render_admin_change_workflow
    from demo_controls import render_demo_controls


load_dotenv()

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
MARTS_DATASET = os.getenv("BQ_MARTS_DATASET", "marts_recruitment")
MAXIMUM_BYTES_BILLED = int(os.getenv("BQ_MAXIMUM_BYTES_BILLED", "100000000"))
OPERATIONAL_SOURCE = (
    "Supabase"
    if os.getenv("USE_SUPABASE_OPERATIONAL_SOURCE", "false").strip().lower() == "true"
    else "Mock API"
)


st.set_page_config(
    page_title="Recruitment Analytics Dashboard",
    layout="wide",
)


@st.cache_resource
def get_bigquery_client():
    service_account_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")

    if service_account_json:
        credentials = service_account.Credentials.from_service_account_info(
            json.loads(service_account_json)
        )

        return bigquery.Client(
            project=PROJECT_ID,
            credentials=credentials,
        )

    return bigquery.Client(project=PROJECT_ID)


@st.cache_data(ttl=1800)
def run_query(query: str) -> pd.DataFrame:
    client = get_bigquery_client()
    job_config = bigquery.QueryJobConfig(maximum_bytes_billed=100_000_000)

    query_job = client.query(query, job_config=job_config)

    return query_job.to_dataframe(create_bqstorage_client=False)


def table_ref(table_name):
    return f"`{PROJECT_ID}.{MARTS_DATASET}.{table_name}`"


def load_table(table_name):
    query = f"""
        select *
        from {table_ref(table_name)}
    """
    return run_query(query)


def format_number(value):
    if pd.isna(value):
        return "0"

    return f"{int(value):,}".replace(",", " ")


def format_decimal(value, digits=1):
    if pd.isna(value):
        return "0"

    return f"{value:.{digits}f}"


def format_days(value):
    if value is None or pd.isna(value):
        return "N/A"

    return f"{value:.1f} days"


def format_percentage(value):
    if pd.isna(value):
        return "N/A"

    return f"{value * 100:.1f}%"


def safe_sum(dataframe, column_name):
    if dataframe.empty or column_name not in dataframe.columns:
        return 0

    return dataframe[column_name].fillna(0).sum()


def weighted_average(dataframe, value_column, weight_column):
    if dataframe.empty:
        return None

    if value_column not in dataframe.columns or weight_column not in dataframe.columns:
        return None

    valid_rows = dataframe[
        dataframe[value_column].notna()
        & dataframe[weight_column].notna()
        & (dataframe[weight_column] > 0)
    ]

    if valid_rows.empty:
        return None

    numerator = (valid_rows[value_column] * valid_rows[weight_column]).sum()
    denominator = valid_rows[weight_column].sum()

    if denominator == 0:
        return None

    return numerator / denominator


def apply_scope_filters(dataframe, selected_offices, selected_departments):
    if dataframe.empty:
        return dataframe

    filtered = dataframe.copy()

    if "office_name" in filtered.columns:
        filtered = filtered[filtered["office_name"].isin(selected_offices)]

    if "department_name" in filtered.columns:
        filtered = filtered[filtered["department_name"].isin(selected_departments)]

    return filtered


def apply_recruiter_filter(dataframe, selected_recruiters):
    if dataframe.empty:
        return dataframe

    if "recruiter_name" not in dataframe.columns:
        return dataframe

    return dataframe[dataframe["recruiter_name"].isin(selected_recruiters)]


def build_overview_metrics(filtered_overview):
    total_jobs = safe_sum(filtered_overview, "total_jobs")
    open_jobs = safe_sum(filtered_overview, "open_jobs")
    closed_jobs = safe_sum(filtered_overview, "closed_jobs")

    total_applications = safe_sum(filtered_overview, "total_applications")
    active_applications = safe_sum(filtered_overview, "active_applications")
    rejected_applications = safe_sum(filtered_overview, "rejected_applications")
    hired_applications = safe_sum(filtered_overview, "hired_applications")

    total_offers = safe_sum(filtered_overview, "total_offers")
    accepted_offers = safe_sum(filtered_overview, "accepted_offers")

    recruiter_owned_stage_cases = safe_sum(
        filtered_overview,
        "recruiter_owned_stage_cases",
    )
    recruiter_sla_met_cases = safe_sum(
        filtered_overview,
        "recruiter_sla_met_cases",
    )
    recruiter_sla_breached_cases = safe_sum(
        filtered_overview,
        "recruiter_sla_breached_cases",
    )

    if recruiter_owned_stage_cases == 0:
        recruiter_sla_compliance_rate = None
    else:
        recruiter_sla_compliance_rate = (
            recruiter_sla_met_cases / recruiter_owned_stage_cases
        )

    avg_time_to_hire_days = weighted_average(
        filtered_overview,
        "avg_time_to_hire_days",
        "hired_applications_with_valid_time_to_hire"
        if "hired_applications_with_valid_time_to_hire" in filtered_overview.columns
        else "hired_applications",
    )

    return {
        "total_jobs": total_jobs,
        "open_jobs": open_jobs,
        "closed_jobs": closed_jobs,
        "total_applications": total_applications,
        "active_applications": active_applications,
        "rejected_applications": rejected_applications,
        "hired_applications": hired_applications,
        "total_offers": total_offers,
        "accepted_offers": accepted_offers,
        "recruiter_owned_stage_cases": recruiter_owned_stage_cases,
        "recruiter_sla_met_cases": recruiter_sla_met_cases,
        "recruiter_sla_breached_cases": recruiter_sla_breached_cases,
        "recruiter_sla_compliance_rate": recruiter_sla_compliance_rate,
        "avg_time_to_hire_days": avg_time_to_hire_days,
    }


st.title("Recruitment Analytics Dashboard")

if OPERATIONAL_SOURCE == "Supabase":
    st.caption(
        "Production-like dashboard consuming BigQuery marts generated by dbt "
        "from Supabase operational data and orchestrated with Airflow."
    )
else:
    st.caption(
        "Production-like dashboard consuming BigQuery marts generated by dbt "
        "from Mock Greenhouse API data and orchestrated with Airflow."
    )
st.caption(f"Operational source: {OPERATIONAL_SOURCE} | Analytics marts: {MARTS_DATASET}")

if not PROJECT_ID:
    st.error("Missing GCP_PROJECT_ID environment variable.")
    st.stop()


with st.spinner("Loading BigQuery marts..."):
    executive_overview = load_table("mart_hr_executive_overview_by_office_department")
    application_status = load_table("mart_application_status_by_office_department")
    recruitment_funnel = load_table("mart_recruitment_funnel_by_office_department")
    recruiter_workload = load_table("mart_recruiter_workload")
    recruiter_performance = load_table("mart_recruiter_performance")
    sla_breaches = load_table("mart_sla_breaches")


st.sidebar.header("Global filters")

if st.sidebar.button("Refresh BigQuery data"):
    st.cache_data.clear()
    st.rerun()

render_demo_controls()
render_admin_change_workflow()

office_options = sorted(executive_overview["office_name"].dropna().unique().tolist())

department_options = sorted(
    executive_overview["department_name"].dropna().unique().tolist()
)

recruiter_options = sorted(
    recruiter_workload["recruiter_name"].dropna().unique().tolist()
)

selected_offices = st.sidebar.multiselect(
    "Office",
    office_options,
    default=office_options,
)

selected_departments = st.sidebar.multiselect(
    "Department",
    department_options,
    default=department_options,
)

selected_recruiters = st.sidebar.multiselect(
    "Recruiter",
    recruiter_options,
    default=recruiter_options,
)

if not selected_offices or not selected_departments:
    st.warning("Select at least one office and one department.")
    st.stop()

if not selected_recruiters:
    st.warning("Select at least one recruiter.")
    st.stop()


filtered_overview = apply_scope_filters(
    executive_overview,
    selected_offices,
    selected_departments,
)

filtered_application_status = apply_scope_filters(
    application_status,
    selected_offices,
    selected_departments,
)

filtered_recruitment_funnel = apply_scope_filters(
    recruitment_funnel,
    selected_offices,
    selected_departments,
)

filtered_recruiter_workload = apply_scope_filters(
    recruiter_workload,
    selected_offices,
    selected_departments,
)
filtered_recruiter_workload = apply_recruiter_filter(
    filtered_recruiter_workload,
    selected_recruiters,
)

filtered_recruiter_performance = apply_scope_filters(
    recruiter_performance,
    selected_offices,
    selected_departments,
)
filtered_recruiter_performance = apply_recruiter_filter(
    filtered_recruiter_performance,
    selected_recruiters,
)

filtered_sla_breaches = apply_scope_filters(
    sla_breaches,
    selected_offices,
    selected_departments,
)
filtered_sla_breaches = apply_recruiter_filter(
    filtered_sla_breaches,
    selected_recruiters,
)


overview_metrics = build_overview_metrics(filtered_overview)

st.subheader("Executive Overview")

metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)

metric_col1.metric(
    "Open Jobs",
    format_number(overview_metrics["open_jobs"]),
)

metric_col2.metric(
    "Applications",
    format_number(overview_metrics["total_applications"]),
)

metric_col3.metric(
    "Hired",
    format_number(overview_metrics["hired_applications"]),
)

metric_col4.metric(
    "Recruiter SLA Compliance",
    format_percentage(overview_metrics["recruiter_sla_compliance_rate"]),
)

metric_col5, metric_col6, metric_col7, metric_col8 = st.columns(4)

metric_col5.metric(
    "Active Applications",
    format_number(overview_metrics["active_applications"]),
)

metric_col6.metric(
    "Rejected Applications",
    format_number(overview_metrics["rejected_applications"]),
)

metric_col7.metric(
    "SLA Breaches",
    format_number(overview_metrics["recruiter_sla_breached_cases"]),
)

metric_col8.metric(
    "Avg Time to Hire",
    format_days(overview_metrics["avg_time_to_hire_days"]),
)

st.divider()

st.subheader("Application Status Distribution")

if filtered_application_status.empty:
    st.info("No application status data for the selected scope.")
else:
    status_chart_data = (
        filtered_application_status.groupby("application_status", as_index=False)[
            "applications_count"
        ]
        .sum()
        .sort_values("applications_count", ascending=False)
    )

    status_fig = px.bar(
        status_chart_data,
        x="application_status",
        y="applications_count",
        title="Applications by Status",
        labels={
            "application_status": "Application Status",
            "applications_count": "Applications",
        },
    )

    st.plotly_chart(status_fig, use_container_width=True)

    status_table = filtered_application_status.copy()
    status_table["status_share"] = (status_table["status_share"] * 100).round(1)

    st.dataframe(
        status_table[
            [
                "office_name",
                "department_name",
                "application_status",
                "applications_count",
                "status_share",
            ]
        ],
        use_container_width=True,
    )

st.divider()

st.subheader("Recruitment Funnel")

if filtered_recruitment_funnel.empty:
    st.info("No recruitment funnel data for the selected scope.")
else:
    funnel_chart_data = (
        filtered_recruitment_funnel.groupby(
            ["stage_order", "stage_name"], as_index=False
        )["applications_reached"]
        .sum()
        .sort_values("stage_order")
    )

    funnel_fig = px.bar(
        funnel_chart_data,
        x="stage_name",
        y="applications_reached",
        title="Applications Reached by Recruitment Stage",
        labels={
            "stage_name": "Recruitment Stage",
            "applications_reached": "Applications Reached",
        },
    )

    st.plotly_chart(funnel_fig, use_container_width=True)

    st.dataframe(
        filtered_recruitment_funnel[
            [
                "office_name",
                "department_name",
                "stage_order",
                "stage_name",
                "applications_reached",
            ]
        ].sort_values(["office_name", "department_name", "stage_order"]),
        use_container_width=True,
    )

st.divider()

st.subheader("Recruiter Workload")

if filtered_recruiter_workload.empty:
    st.info("No recruiter workload data for the selected scope.")
else:
    workload_chart_data = (
        filtered_recruiter_workload.groupby("recruiter_name", as_index=False)[
            [
                "total_applications",
                "active_applications",
                "sla_breached_cases",
            ]
        ]
        .sum()
        .sort_values("active_applications", ascending=False)
    )

    workload_fig = px.bar(
        workload_chart_data,
        x="recruiter_name",
        y="active_applications",
        title="Active Applications by Recruiter",
        labels={
            "recruiter_name": "Recruiter",
            "active_applications": "Active Applications",
        },
    )

    st.plotly_chart(workload_fig, use_container_width=True)

    workload_table = filtered_recruiter_workload.copy()
    workload_table["sla_compliance_rate"] = (
        workload_table["sla_compliance_rate"] * 100
    ).round(1)
    workload_table["avg_recruiter_stage_duration_days"] = workload_table[
        "avg_recruiter_stage_duration_days"
    ].round(2)

    st.dataframe(
        workload_table[
            [
                "recruiter_name",
                "office_name",
                "department_name",
                "total_applications",
                "active_applications",
                "jobs_touched",
                "recruiter_owned_stage_cases",
                "sla_met_cases",
                "sla_breached_cases",
                "sla_compliance_rate",
                "avg_recruiter_stage_duration_days",
                "total_offers",
                "accepted_offers",
            ]
        ],
        use_container_width=True,
    )

st.divider()

st.subheader("Recruiter SLA Performance")

if filtered_recruiter_performance.empty:
    st.info("No recruiter SLA performance data for the selected scope.")
else:
    performance_chart_data = filtered_recruiter_performance.copy()

    performance_fig = px.bar(
        performance_chart_data,
        x="recruiter_name",
        y="sla_compliance_rate",
        color="stage_name",
        title="SLA Compliance by Recruiter and Recruiter-Owned Stage",
        labels={
            "recruiter_name": "Recruiter",
            "sla_compliance_rate": "SLA Compliance Rate",
            "stage_name": "Stage",
        },
    )

    performance_fig.update_yaxes(tickformat=".0%")

    st.plotly_chart(performance_fig, use_container_width=True)

    performance_table = filtered_recruiter_performance.copy()
    performance_table["sla_compliance_rate"] = (
        performance_table["sla_compliance_rate"] * 100
    ).round(1)
    performance_table["avg_duration_days"] = performance_table[
        "avg_duration_days"
    ].round(2)

    st.dataframe(
        performance_table[
            [
                "recruiter_name",
                "office_name",
                "department_name",
                "stage_name",
                "total_cases",
                "sla_met_cases",
                "sla_breached_cases",
                "sla_compliance_rate",
                "avg_duration_days",
            ]
        ],
        use_container_width=True,
    )

st.divider()

st.subheader("SLA Breaches")
st.caption(
    "active means the application is still open in the recruitment process. "
    "It has not reached a terminal outcome such as hired or rejected."
)

if filtered_sla_breaches.empty:
    st.success("No SLA breaches for the selected scope.")
else:
    breach_table = filtered_sla_breaches.copy()
    breach_table["duration_days"] = breach_table["duration_days"].round(2)

    st.dataframe(
        breach_table[
            [
                "application_id",
                "candidate_full_name",
                "job_name",
                "recruiter_name",
                "department_name",
                "office_name",
                "stage_name",
                "duration_days",
                "sla_target_days",
                "application_status",
                "current_stage",
            ]
        ],
        use_container_width=True,
    )

st.divider()

st.subheader("Dashboard Capabilities")

st.markdown("""
This dashboard covers the following HR analytics capabilities:

1. Application status distribution by office and department.
2. Recruitment funnel analysis by stage.
3. Executive overview of jobs, applications, offers and hires.
4. Recruiter workload monitoring.
5. Recruiter SLA compliance on recruiter-owned stages.
6. Recruiter SLA breach detection at application level.
7. Average recruiter response time by stage.
8. Office and department scoped filtering.
""")

st.divider()

st.subheader("Technical Lineage")

st.markdown("""
This dashboard consumes **BigQuery mart tables** produced by dbt.

Pipeline:

```text
Mock Greenhouse API
    ↓
Workato API Sync Simulator
    ↓
BigQuery RAW
    ↓
dbt STAGING
    ↓
dbt CORE
    ↓
dbt MARTS
    ↓
Streamlit Dashboard
Airflow orchestrates the end-to-end pipeline:
API health check, API-to-BigQuery ingestion, dbt transformations and dbt tests.

The provided Excel and JSON files are used only to seed the Mock Greenhouse API.
The dashboard does not read those files directly.

A maximum bytes billed limit is applied to BigQuery dashboard queries to reduce cost exposure.
""")
