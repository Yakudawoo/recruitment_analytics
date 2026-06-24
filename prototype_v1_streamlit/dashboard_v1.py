import streamlit as st
import plotly.express as px

from src.load_data import load_all_data
from src.transform import build_analytics_model
from src.metrics import (
    applications_by_status,
    applications_by_stage,
    applications_by_office,
    applications_by_department,
    calculate_global_metrics,
    recruiter_sla_summary,
    delayed_recruiter_cases,
)


st.set_page_config(
    page_title="Recruitment Analytics Dashboard",
    layout="wide",
)


@st.cache_data
def load_model():
    data = load_all_data()
    return build_analytics_model(data)


model = load_model()

st.title("Recruitment Analytics Dashboard")
st.caption("Mockup based on Greenhouse API and webhook data")

applications = model["applications_enriched"]
recruiter_sla = model["recruiter_sla"]

st.sidebar.header("Filters")

offices = sorted(applications["ghjb_gh_office_name"].dropna().unique())
departments = sorted(applications["ghjb_gh_department_name"].dropna().unique())
recruiters = sorted(applications["recruiter_name"].dropna().unique())

selected_offices = st.sidebar.multiselect("Office", offices, default=offices)
selected_departments = st.sidebar.multiselect("Department", departments, default=departments)
selected_recruiters = st.sidebar.multiselect("Recruiter", recruiters, default=recruiters)

filtered_applications = applications[
    applications["ghjb_gh_office_name"].isin(selected_offices)
    & applications["ghjb_gh_department_name"].isin(selected_departments)
    & applications["recruiter_name"].isin(selected_recruiters)
]

filtered_recruiter_sla = recruiter_sla[
    recruiter_sla["ghjb_gh_office_name"].isin(selected_offices)
    & recruiter_sla["ghjb_gh_department_name"].isin(selected_departments)
    & recruiter_sla["recruiter_name"].isin(selected_recruiters)
]

filtered_model = model.copy()
filtered_model["applications_enriched"] = filtered_applications
filtered_model["recruiter_sla"] = filtered_recruiter_sla

metrics = calculate_global_metrics(filtered_model)

col1, col2, col3, col4 = st.columns(4)

col1.metric("Open Jobs", metrics["open_jobs"])
col2.metric("Applications", metrics["total_applications"])
col3.metric("Hired", metrics["hired_applications"])
col4.metric(
    "Recruiter SLA Compliance",
    f"{metrics['recruiter_sla_compliance_rate'] * 100:.1f}%",
)

st.divider()

left, right = st.columns(2)

with left:
    status_df = applications_by_status(filtered_model)
    fig = px.pie(
        status_df,
        names="ghap_status",
        values="applications",
        title="Applications by Status",
    )
    st.plotly_chart(fig, use_container_width=True)

with right:
    stage_df = applications_by_stage(filtered_model)
    fig = px.bar(
        stage_df,
        x="applications",
        y="ghap_application_current_stage",
        orientation="h",
        title="Applications by Current Stage",
    )
    st.plotly_chart(fig, use_container_width=True)

left, right = st.columns(2)

with left:
    office_df = applications_by_office(filtered_model)
    fig = px.bar(
        office_df,
        x="ghjb_gh_office_name",
        y="applications",
        title="Applications by Office",
    )
    st.plotly_chart(fig, use_container_width=True)

with right:
    department_df = applications_by_department(filtered_model)
    fig = px.bar(
        department_df,
        x="ghjb_gh_department_name",
        y="applications",
        title="Applications by Department",
    )
    st.plotly_chart(fig, use_container_width=True)

st.divider()

st.subheader("Recruiter Performance and Responsiveness")

sla_summary = recruiter_sla_summary(filtered_model)

if not sla_summary.empty:
    fig = px.bar(
        sla_summary,
        x="recruiter_name",
        y="sla_compliance_rate",
        color="stage_name",
        title="SLA Compliance Rate by Recruiter and Stage",
        labels={
            "sla_compliance_rate": "SLA Compliance Rate (%)",
            "recruiter_name": "Recruiter",
            "stage_name": "Stage",
        },
    )
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(sla_summary, use_container_width=True)
else:
    st.info("No SLA data available for the selected filters.")

st.subheader("Delayed Recruiter-Owned Cases")

delayed_cases = delayed_recruiter_cases(filtered_model)

if not delayed_cases.empty:
    st.dataframe(delayed_cases, use_container_width=True)
else:
    st.success("No delayed recruiter-owned cases for the selected filters.")

st.divider()

st.subheader("Raw Application Data")
st.dataframe(filtered_applications, use_container_width=True)