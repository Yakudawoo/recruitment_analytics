import pandas as pd


def safe_rate(numerator, denominator):
    if denominator == 0:
        return 0

    return numerator / denominator


def calculate_global_metrics(model):
    jobs = model["jobs"]
    applications = model["applications_enriched"]
    offers = model["offers"]
    recruiter_sla = model["recruiter_sla"]

    open_jobs = jobs[jobs["ghjb_job_status"] == "open"].shape[0]
    total_applications = applications.shape[0]
    hired_applications = applications[applications["ghap_status"] == "hired"].shape[0]
    rejected_applications = applications[applications["ghap_status"] == "rejected"].shape[0]
    active_applications = applications[applications["ghap_status"] == "active"].shape[0]

    accepted_offers = offers[offers["ghof_status"] == "accepted"].shape[0]

    recruiter_sla_valid = recruiter_sla[recruiter_sla["sla_met"].notna()]
    sla_met_count = recruiter_sla_valid[recruiter_sla_valid["sla_met"] == True].shape[0]
    sla_total_count = recruiter_sla_valid.shape[0]

    sla_compliance_rate = safe_rate(sla_met_count, sla_total_count)

    return {
        "open_jobs": open_jobs,
        "total_applications": total_applications,
        "active_applications": active_applications,
        "rejected_applications": rejected_applications,
        "hired_applications": hired_applications,
        "accepted_offers": accepted_offers,
        "recruiter_sla_compliance_rate": sla_compliance_rate,
        "recruiter_sla_total_cases": sla_total_count,
    }


def applications_by_status(model):
    applications = model["applications_enriched"]

    return (
        applications.groupby("ghap_status", dropna=False)
        .size()
        .reset_index(name="applications")
        .sort_values("applications", ascending=False)
    )


def applications_by_stage(model):
    applications = model["applications_enriched"]

    return (
        applications.groupby("ghap_application_current_stage", dropna=False)
        .size()
        .reset_index(name="applications")
        .sort_values("applications", ascending=False)
    )


def applications_by_office(model):
    applications = model["applications_enriched"]

    return (
        applications.groupby("ghjb_gh_office_name", dropna=False)
        .size()
        .reset_index(name="applications")
        .sort_values("applications", ascending=False)
    )


def applications_by_department(model):
    applications = model["applications_enriched"]

    return (
        applications.groupby("ghjb_gh_department_name", dropna=False)
        .size()
        .reset_index(name="applications")
        .sort_values("applications", ascending=False)
    )


def recruiter_sla_summary(model):
    recruiter_sla = model["recruiter_sla"].copy()

    valid = recruiter_sla[recruiter_sla["sla_met"].notna()].copy()

    if valid.empty:
        return pd.DataFrame(
            columns=[
                "recruiter_name",
                "stage_name",
                "cases",
                "avg_duration_days",
                "sla_compliance_rate",
            ]
        )

    summary = (
        valid.groupby(["recruiter_name", "stage_name"], dropna=False)
        .agg(
            cases=("application_id", "count"),
            avg_duration_days=("duration_days", "mean"),
            sla_compliance_rate=("sla_met", "mean"),
        )
        .reset_index()
    )

    summary["avg_duration_days"] = summary["avg_duration_days"].round(2)
    summary["sla_compliance_rate"] = (
        summary["sla_compliance_rate"] * 100
    ).round(1)

    return summary.sort_values(
        by=["sla_compliance_rate", "avg_duration_days"],
        ascending=[True, False],
    )


def delayed_recruiter_cases(model):
    recruiter_sla = model["recruiter_sla"].copy()

    delayed = recruiter_sla[
        (recruiter_sla["sla_met"] == False)
        & (recruiter_sla["duration_days"].notna())
    ].copy()

    columns = [
        "application_id",
        "candidate_full_name",
        "ghjb_job_name",
        "ghjb_gh_department_name",
        "ghjb_gh_office_name",
        "recruiter_name",
        "stage_name",
        "duration_days",
        "sla_target_days",
    ]

    delayed = delayed[columns]
    delayed["duration_days"] = delayed["duration_days"].round(2)

    return delayed.sort_values("duration_days", ascending=False)