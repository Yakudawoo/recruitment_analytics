import pandas as pd


RECRUITER_OWNED_STAGES = {
    "Application Review": 3,
    "Recruiter Interview": 3,
}


def parse_datetime_columns(df, columns):
    df = df.copy()

    for column in columns:
        if column in df.columns:
            df[column] = pd.to_datetime(df[column], errors="coerce")

    return df


def build_core_model(data):
    jobs = data["jobs"].copy()
    candidates = data["candidates"].copy()
    applications = data["applications"].copy()
    offers = data["offers"].copy()
    events = data["events"].copy()

    jobs = parse_datetime_columns(
        jobs,
        ["ghjb_created_at", "ghjb_opened_at", "ghjb_closed_at"],
    )

    applications = parse_datetime_columns(
        applications,
        ["ghap_applied_at", "ghap_rejected_at", "ghap_last_activity_at"],
    )

    candidates = parse_datetime_columns(
        candidates,
        ["ghca_created_at", "ghca_updated_at"],
    )

    offers = parse_datetime_columns(
        offers,
        ["ghof_created_at", "ghof_updated_at", "ghof_resolved_at", "ghof_starts_at"],
    )

    events = parse_datetime_columns(
        events,
        ["last_activity_at"],
    )

    applications_enriched = applications.merge(
        jobs[
            [
                "ghjb_job_id",
                "ghjb_job_name",
                "ghjb_job_status",
                "ghjb_gh_department_id",
                "ghjb_gh_department_name",
                "ghjb_gh_office_id",
                "ghjb_gh_office_name",
                "ghjb_hiring_manager_id",
                "ghjb_hiring_manager_name",
                "ghjb_recruiter_id",
                "ghjb_recruiter_name",
            ]
        ],
        left_on="ghap_job_id",
        right_on="ghjb_job_id",
        how="left",
    )

    applications_enriched = applications_enriched.merge(
        candidates[
            [
                "ghca_candidate_id",
                "ghca_first_name",
                "ghca_last_name",
                "ghca_recruiter_id",
                "ghca_recruiter_name",
            ]
        ],
        left_on="ghap_candidate_id",
        right_on="ghca_candidate_id",
        how="left",
    )

    applications_enriched["candidate_full_name"] = (
        applications_enriched["ghca_first_name"].fillna("")
        + " "
        + applications_enriched["ghca_last_name"].fillna("")
    ).str.strip()

    applications_enriched["recruiter_name"] = applications_enriched[
        "ghjb_recruiter_name"
    ].fillna(applications_enriched["ghca_recruiter_name"])

    return {
        "jobs": jobs,
        "candidates": candidates,
        "applications": applications,
        "offers": offers,
        "events": events,
        "applications_enriched": applications_enriched,
    }


def build_stage_transitions(events):
    transitions = events.copy()

    transitions = transitions.sort_values(
        by=["application_id", "last_activity_at"]
    )

    transitions = transitions.drop_duplicates(
        subset=[
            "application_id",
            "action",
            "previous_status",
            "current_status",
            "previous_stage",
            "current__stage",
            "last_activity_at",
        ]
    )

    transitions["stage_name"] = transitions["previous_stage"].fillna(
        transitions["current__stage"]
    )

    transitions["entered_stage_at"] = transitions.groupby("application_id")[
        "last_activity_at"
    ].shift(1)

    transitions["left_stage_at"] = transitions["last_activity_at"]

    transitions["duration_hours"] = (
        transitions["left_stage_at"] - transitions["entered_stage_at"]
    ).dt.total_seconds() / 3600

    transitions["duration_days"] = transitions["duration_hours"] / 24

    transitions["sla_target_days"] = transitions["stage_name"].map(RECRUITER_OWNED_STAGES)

    transitions["is_recruiter_owned_stage"] = transitions["stage_name"].isin(
        RECRUITER_OWNED_STAGES.keys()
    )

    transitions["sla_met"] = transitions.apply(
        lambda row: (
            row["duration_days"] <= row["sla_target_days"]
            if pd.notna(row["sla_target_days"]) and pd.notna(row["duration_days"])
            else pd.NA
        ),
        axis=1,
    )

    return transitions


def build_recruiter_sla_table(stage_transitions, applications_enriched):
    recruiter_stages = stage_transitions[
        stage_transitions["is_recruiter_owned_stage"] == True
    ].copy()

    recruiter_stages = recruiter_stages.merge(
        applications_enriched[
            [
                "ghap_application_id",
                "candidate_full_name",
                "ghjb_job_name",
                "ghjb_gh_department_name",
                "ghjb_gh_office_name",
                "recruiter_name",
                "ghap_status",
            ]
        ],
        left_on="application_id",
        right_on="ghap_application_id",
        how="left",
    )

    return recruiter_stages


def build_analytics_model(data):
    core = build_core_model(data)

    stage_transitions = build_stage_transitions(core["events"])

    recruiter_sla = build_recruiter_sla_table(
        stage_transitions,
        core["applications_enriched"],
    )

    core["stage_transitions"] = stage_transitions
    core["recruiter_sla"] = recruiter_sla

    return core