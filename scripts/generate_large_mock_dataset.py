from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
GENERATED_DIR = DATA_DIR / "generated"

ORGANIZATION_ID = 8020479101
ORGANIZATION_NAME = "Teads"

NULL_VALUE = "(null)"

STAGES = [
    "Application Review",
    "AI Recommendation Review",
    "Recruiter Interview",
    "Hiring Manager Review",
    "Hiring Manager Interview",
    "Take Home Test",
    "Face to Face",
    "HR Interview",
    "Final Interview",
    "Final (Executive) Interview",
    "Reference Check",
    "Offer",
]

RECRUITER_OWNED_STAGES = {
    "Application Review",
    "Recruiter Interview",
}

APPLICATION_SOURCES = [
    "LinkedIn",
    "LinkedIn (Prospecting)",
    "Referral",
    "Indeed",
    "Greenhouse",
    "Company Website",
    "Agency",
    "Internal Mobility",
]

REJECTION_REASONS = [
    "Not enough experience",
    "Candidate withdrew",
    "Accepted offer at another company",
    "Role closed",
    "Salary expectations",
    "Skills mismatch",
]

DEPARTMENTS = [
    ("4041061101", "Department of Science and Technology Policy"),
    ("4041067101", "Department of Homeland Security"),
    ("4041072101", "Department of Transportation"),
    ("4041078101", "Department of Veterans Affairs"),
    ("4041083101", "Office of Personnel Management"),
    ("4041089101", "Department of Finance"),
    ("4041094101", "Department of Product"),
    ("4041099101", "Department of Engineering"),
    ("4041104101", "Department of Marketing"),
    ("4041109101", "Department of Sales"),
    ("4041114101", "Department of Data"),
    ("4041119101", "Department of Operations"),
]

OFFICES = [
    ("4002351101", "Columbus"),
    ("4019996101", "Detroit"),
    ("4020001101", "Austin"),
    ("4020006101", "Boston"),
    ("4020011101", "Houston"),
    ("4020016101", "Jacksonville"),
    ("4020021101", "Las Vegas"),
    ("4020026101", "New York"),
    ("4020031101", "Paris"),
    ("4020036101", "London"),
]

RECRUITERS = [
    ("4057126101", "Dylan Thomas"),
    ("4058073101", "Saul Bellow"),
    ("4058079101", "Aldous Huxley"),
    ("4058085101", "Anton Chekhov"),
    ("4058091101", "C.S. Lewis"),
    ("4058097101", "Etgar Keret"),
    ("4058103101", "George Orwell"),
    ("4058109101", "Virginia Woolf"),
    ("4058115101", "James Baldwin"),
    ("4058121101", "Toni Morrison"),
    ("4058127101", "Mary Shelley"),
    ("4058133101", "Octavia Butler"),
    ("4058139101", "Margaret Atwood"),
    ("4058145101", "Chinua Achebe"),
    ("4058151101", "Haruki Murakami"),
    ("4058157101", "Jorge Luis Borges"),
    ("4058163101", "Ursula Le Guin"),
    ("4058169101", "Maya Angelou"),
]

HIRING_MANAGERS = [
    ("4432863101", "George Bernard Shaw"),
    ("4038786101", "Gustave Flaubert"),
    ("4038792101", "Claire Keegan"),
    ("4038798101", "Honore de Balzac"),
    ("4038804101", "Jo Nesbo"),
    ("4038810101", "Jane Austen"),
    ("4038816101", "Franz Kafka"),
    ("4038822101", "Agatha Christie"),
]


FIRST_NAMES = [
    "Alex", "Morgan", "Taylor", "Jordan", "Casey", "Robin", "Jamie", "Avery",
    "Riley", "Quinn", "Sam", "Charlie", "Dana", "Cameron", "Nina", "Leo",
    "Maya", "Noah", "Emma", "Liam", "Olivia", "Ethan", "Sophia", "Lucas",
]

LAST_NAMES = [
    "Martin", "Bernard", "Dubois", "Thomas", "Robert", "Richard", "Petit",
    "Durand", "Leroy", "Moreau", "Simon", "Laurent", "Lefebvre", "Michel",
    "Garcia", "David", "Bertrand", "Roux", "Vincent", "Fournier",
]

JOB_TITLES = [
    "Data Engineer",
    "Analytics Engineer",
    "Software Engineer",
    "Backend Engineer",
    "Product Manager",
    "Sales Manager",
    "Customer Success Manager",
    "Data Analyst",
    "Machine Learning Engineer",
    "Marketing Operations Manager",
    "Finance Analyst",
    "Recruitment Coordinator",
    "Business Operations Analyst",
    "Platform Engineer",
    "Solutions Engineer",
    "Technical Account Manager",
]


def as_datetime_string(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S")


def as_event_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def random_datetime(start: datetime, end: datetime) -> datetime:
    delta_seconds = int((end - start).total_seconds())
    return start + timedelta(seconds=random.randint(0, delta_seconds))


def choose_stage_path(application_status: str) -> list[str]:
    if application_status == "hired":
        min_len = 8
        max_len = len(STAGES)
        return STAGES[: random.randint(min_len, max_len)]

    if application_status == "rejected":
        max_len = random.randint(2, min(9, len(STAGES)))
        return STAGES[:max_len]

    max_len = random.randint(1, min(8, len(STAGES)))
    return STAGES[:max_len]


def generate_jobs(number_of_jobs: int, base_date: datetime) -> pd.DataFrame:
    rows = []

    for index in range(number_of_jobs):
        job_id = 4_410_000_000 + index + 101
        requisition_id = 10_000 + index

        department_id, department_name = random.choice(DEPARTMENTS)
        office_id, office_name = random.choice(OFFICES)
        recruiter_id, recruiter_name = random.choice(RECRUITERS)
        hiring_manager_id, hiring_manager_name = random.choice(HIRING_MANAGERS)

        created_at = random_datetime(base_date, base_date + timedelta(days=80))
        opened_at = created_at + timedelta(hours=random.randint(1, 72))

        job_status = random.choices(
            ["open", "closed"],
            weights=[0.72, 0.28],
            k=1,
        )[0]

        closed_at = NULL_VALUE
        if job_status == "closed":
            closed_at = as_datetime_string(opened_at + timedelta(days=random.randint(15, 90)))

        rows.append(
            {
                "ghjb_job_id": job_id,
                "ghjb_job_name": random.choice(JOB_TITLES),
                "ghjb_requisition_id": requisition_id,
                "ghjb_job_status": job_status,
                "ghjb_created_at": as_datetime_string(created_at),
                "ghjb_opened_at": as_datetime_string(opened_at),
                "ghjb_closed_at": closed_at,
                "ghjb_gh_department_id": department_id,
                "ghjb_gh_department_name": department_name,
                "ghjb_gh_office_id": office_id,
                "ghjb_gh_office_name": office_name,
                "ghjb_hiring_manager_id": hiring_manager_id,
                "ghjb_hiring_manager_name": hiring_manager_name,
                "ghjb_recruiter_id": recruiter_id,
                "ghjb_recruiter_name": recruiter_name,
                "ghjb_employment_type": random.choice(["Full-time", "Intern", "Apprenticeship", "Contract"]),
                "ghjb_budget_owner": random.choice([name for _, name in HIRING_MANAGERS]),
                "ghjb_executive": random.choice([name for _, name in HIRING_MANAGERS]),
                "ghjb_fte": random.choice([0.3, 0.5, 0.8, 1.0]),
                "ghjb_job_type": "Standard",
            }
        )

    return pd.DataFrame(rows)


def generate_candidates(number_of_candidates: int, base_date: datetime) -> pd.DataFrame:
    rows = []

    for index in range(number_of_candidates):
        candidate_id = 55_000_000_000 + index + 101
        first_name = random.choice(FIRST_NAMES)
        last_name = random.choice(LAST_NAMES)

        created_at = random_datetime(base_date, base_date + timedelta(days=120))
        updated_at = created_at + timedelta(days=random.randint(0, 100))

        recruiter_id, recruiter_name = random.choice(RECRUITERS)

        rows.append(
            {
                "ghca_candidate_id": candidate_id,
                "ghca_first_name": first_name,
                "ghca_last_name": last_name,
                "ghca_created_at": as_datetime_string(created_at),
                "ghca_updated_at": as_datetime_string(updated_at),
                "ghca_status": NULL_VALUE,
                "ghca_recruiter_id": recruiter_id,
                "ghca_recruiter_name": recruiter_name,
                "ghca_application_id": NULL_VALUE,
            }
        )

    return pd.DataFrame(rows)


def generate_applications_and_events(
    number_of_applications: int,
    jobs: pd.DataFrame,
    candidates: pd.DataFrame,
    base_date: datetime,
) -> tuple[pd.DataFrame, list[dict]]:
    application_rows = []
    event_rows = []

    job_records = jobs.to_dict("records")
    candidate_records = candidates.to_dict("records")

    for index in range(number_of_applications):
        application_id = 60_000_000_000 + index + 101

        job = random.choice(job_records)
        candidate = random.choice(candidate_records)

        candidate_id = int(candidate["ghca_candidate_id"])
        job_id = int(job["ghjb_job_id"])

        applied_at = random_datetime(base_date + timedelta(days=5), base_date + timedelta(days=170))

        status = random.choices(
            ["active", "rejected", "hired"],
            weights=[0.68, 0.23, 0.09],
            k=1,
        )[0]

        stage_path = choose_stage_path(status)
        current_stage = stage_path[-1]

        event_time = applied_at + timedelta(hours=random.randint(1, 12))
        previous_stage = None
        previous_status = None
        current_status = "active"

        for stage_index, stage in enumerate(stage_path):
            if stage_index == 0:
                event_time = applied_at + timedelta(hours=random.randint(1, 12))
            else:
                previous = stage_path[stage_index - 1]
                if previous in RECRUITER_OWNED_STAGES:
                    days_to_add = random.choice([1, 2, 3, 4, 5, 6, 7])
                else:
                    days_to_add = random.choice([1, 2, 3, 4, 5])

                event_time = event_time + timedelta(
                    days=days_to_add,
                    hours=random.randint(1, 8),
                )

            event_rows.append(
                {
                    "organization_id": ORGANIZATION_ID,
                    "organization_name": ORGANIZATION_NAME,
                    "action": "candidate_stage_change",
                    "application_id": application_id,
                    "previous_status": previous_status,
                    "current_status": current_status,
                    "last_activity_at": as_event_timestamp(event_time),
                    "rejected_at": None,
                    "rejection_reason": None,
                    "rejection_details": None,
                    "previous_stage": previous_stage,
                    "current__stage": stage,
                }
            )

            previous_stage = stage
            previous_status = current_status

        rejected_at = NULL_VALUE
        rejection_reason = NULL_VALUE

        if status == "rejected":
            rejected_time = event_time + timedelta(days=random.randint(0, 3), hours=random.randint(1, 8))
            rejected_at = as_datetime_string(rejected_time)
            rejection_reason = random.choice(REJECTION_REASONS)

            event_rows.append(
                {
                    "organization_id": ORGANIZATION_ID,
                    "organization_name": ORGANIZATION_NAME,
                    "action": "candidate_rejected",
                    "application_id": application_id,
                    "previous_status": "active",
                    "current_status": "rejected",
                    "last_activity_at": as_event_timestamp(rejected_time),
                    "rejected_at": as_event_timestamp(rejected_time),
                    "rejection_reason": rejection_reason,
                    "rejection_details": rejection_reason,
                    "previous_stage": current_stage,
                    "current__stage": current_stage,
                }
            )

            last_activity_at = rejected_time

        elif status == "hired":
            hired_time = event_time + timedelta(days=random.randint(1, 5), hours=random.randint(1, 8))

            if current_stage != "Offer":
                event_rows.append(
                    {
                        "organization_id": ORGANIZATION_ID,
                        "organization_name": ORGANIZATION_NAME,
                        "action": "candidate_stage_change",
                        "application_id": application_id,
                        "previous_status": "active",
                        "current_status": "active",
                        "last_activity_at": as_event_timestamp(hired_time),
                        "rejected_at": None,
                        "rejection_reason": None,
                        "rejection_details": None,
                        "previous_stage": current_stage,
                        "current__stage": "Offer",
                    }
                )
                current_stage = "Offer"

            event_rows.append(
                {
                    "organization_id": ORGANIZATION_ID,
                    "organization_name": ORGANIZATION_NAME,
                    "action": "candidate_hired",
                    "application_id": application_id,
                    "previous_status": "active",
                    "current_status": "hired",
                    "last_activity_at": as_event_timestamp(hired_time + timedelta(hours=2)),
                    "rejected_at": None,
                    "rejection_reason": None,
                    "rejection_details": None,
                    "previous_stage": current_stage,
                    "current__stage": current_stage,
                }
            )

            last_activity_at = hired_time + timedelta(hours=2)

        else:
            last_activity_at = event_time

        application_rows.append(
            {
                "ghap_application_id": application_id,
                "ghap_candidate_id": candidate_id,
                "ghap_applied_at": as_datetime_string(applied_at),
                "ghap_rejected_at": rejected_at,
                "ghap_last_activity_at": as_datetime_string(last_activity_at),
                "ghap_source": random.choice(APPLICATION_SOURCES),
                "ghap_rejection_reason": rejection_reason,
                "ghap_job_id": job_id,
                "ghap_status": status,
                "ghap_application_current_stage": current_stage,
                "ghap_jobs_count": 1,
            }
        )

    applications = pd.DataFrame(application_rows)

    first_application_by_candidate = (
        applications.sort_values("ghap_applied_at")
        .drop_duplicates("ghap_candidate_id")
        .set_index("ghap_candidate_id")["ghap_application_id"]
        .to_dict()
    )

    candidates["ghca_application_id"] = candidates["ghca_candidate_id"].map(first_application_by_candidate).fillna(NULL_VALUE)

    return applications, event_rows


def generate_openings(jobs: pd.DataFrame, applications: pd.DataFrame) -> pd.DataFrame:
    rows = []
    opening_index = 0

    hired_applications = applications[applications["ghap_status"] == "hired"].to_dict("records")

    hired_by_job = {}
    for app in hired_applications:
        hired_by_job.setdefault(int(app["ghap_job_id"]), []).append(app)

    for _, job in jobs.iterrows():
        job_id = int(job["ghjb_job_id"])
        number_of_openings = random.choice([1, 1, 1, 2, 2, 3])

        for local_index in range(number_of_openings):
            opening_index += 1
            opening_row_id = 49_000_000_000 + opening_index + 101
            opening_id = f"{job['ghjb_requisition_id']}-{local_index + 1}"

            linked_application = NULL_VALUE
            status = "open"
            closed_at = NULL_VALUE
            close_reason = NULL_VALUE

            hired_for_job = hired_by_job.get(job_id, [])
            if hired_for_job and local_index == 0:
                selected_application = hired_for_job[0]
                linked_application = int(selected_application["ghap_application_id"])
                status = "closed"
                closed_at = selected_application["ghap_last_activity_at"]
                close_reason = "Hire - Backfill"
            elif job["ghjb_job_status"] == "closed":
                status = "closed"
                closed_at = job["ghjb_closed_at"]
                close_reason = "Role closed"

            rows.append(
                {
                    "ghop_id": opening_row_id,
                    "ghop_opening_id": opening_id,
                    "ghop_status": status,
                    "ghop_opened_at": job["ghjb_opened_at"],
                    "ghop_closed_at": closed_at,
                    "ghop_application_id": linked_application,
                    "ghop_close_reason_name": close_reason,
                    "ghop_priority": random.choice(["1- Immediate", "2- High", "3- Normal"]),
                    "ghop_additional_hire_replacement": random.choice(["Additional Hire", "Replacement"]),
                    "ghop_job_id": job_id,
                }
            )

    return pd.DataFrame(rows)


def generate_offers(applications: pd.DataFrame, openings: pd.DataFrame) -> pd.DataFrame:
    rows = []

    hired_or_offer_stage = applications[
        (applications["ghap_status"] == "hired")
        | (applications["ghap_application_current_stage"] == "Offer")
    ].copy()

    if hired_or_offer_stage.empty:
        return pd.DataFrame(
            columns=[
                "ghof_offer_id",
                "ghof_offer_version",
                "ghof_application_id",
                "ghof_created_at",
                "ghof_updated_at",
                "ghof_sent_at",
                "ghof_resolved_at",
                "ghof_starts_at",
                "ghof_status",
                "ghof_job_id",
                "ghof_candidate_id",
                "ghof_opening_row_id",
                "ghof_opening_id",
            ]
        )

    openings_by_application = {}
    for _, opening in openings.iterrows():
        application_id = opening["ghop_application_id"]
        if application_id != NULL_VALUE:
            openings_by_application[int(application_id)] = opening

    for index, (_, app) in enumerate(hired_or_offer_stage.iterrows()):
        application_id = int(app["ghap_application_id"])
        job_id = int(app["ghap_job_id"])
        candidate_id = int(app["ghap_candidate_id"])

        created_at = pd.to_datetime(app["ghap_last_activity_at"]).to_pydatetime()
        updated_at = created_at + timedelta(hours=random.randint(1, 48))

        offer_status = "accepted" if app["ghap_status"] == "hired" else random.choice(["sent", "rejected"])

        resolved_at = NULL_VALUE
        if offer_status in {"accepted", "rejected"}:
            resolved_at = as_datetime_string(updated_at)

        opening = openings_by_application.get(application_id)

        rows.append(
            {
                "ghof_offer_id": 4_530_000_000 + index + 101,
                "ghof_offer_version": 1,
                "ghof_application_id": application_id,
                "ghof_created_at": as_datetime_string(created_at),
                "ghof_updated_at": as_datetime_string(updated_at),
                "ghof_sent_at": NULL_VALUE,
                "ghof_resolved_at": resolved_at,
                "ghof_starts_at": as_datetime_string(updated_at + timedelta(days=random.randint(10, 45))),
                "ghof_status": offer_status,
                "ghof_job_id": job_id,
                "ghof_candidate_id": candidate_id,
                "ghof_opening_row_id": int(opening["ghop_id"]) if opening is not None else NULL_VALUE,
                "ghof_opening_id": opening["ghop_opening_id"] if opening is not None else NULL_VALUE,
            }
        )

    return pd.DataFrame(rows)


def validate_dataset(
    jobs: pd.DataFrame,
    openings: pd.DataFrame,
    candidates: pd.DataFrame,
    applications: pd.DataFrame,
    offers: pd.DataFrame,
    events: list[dict],
) -> None:
    assert jobs["ghjb_job_id"].is_unique, "Duplicate job IDs"
    assert candidates["ghca_candidate_id"].is_unique, "Duplicate candidate IDs"
    assert applications["ghap_application_id"].is_unique, "Duplicate application IDs"

    job_ids = set(jobs["ghjb_job_id"].astype(int))
    candidate_ids = set(candidates["ghca_candidate_id"].astype(int))
    application_ids = set(applications["ghap_application_id"].astype(int))

    assert set(applications["ghap_job_id"].astype(int)).issubset(job_ids), "Application linked to missing job"
    assert set(applications["ghap_candidate_id"].astype(int)).issubset(candidate_ids), "Application linked to missing candidate"

    if not offers.empty:
        assert set(offers["ghof_application_id"].astype(int)).issubset(application_ids), "Offer linked to missing application"
        assert set(offers["ghof_job_id"].astype(int)).issubset(job_ids), "Offer linked to missing job"
        assert set(offers["ghof_candidate_id"].astype(int)).issubset(candidate_ids), "Offer linked to missing candidate"

    event_application_ids = {int(event["application_id"]) for event in events}
    assert event_application_ids.issubset(application_ids), "Event linked to missing application"

    allowed_stages = set(STAGES)
    for event in events:
        assert event["current__stage"] in allowed_stages, f"Invalid current stage: {event['current__stage']}"
        if event["previous_stage"] is not None:
            assert event["previous_stage"] in allowed_stages, f"Invalid previous stage: {event['previous_stage']}"
        datetime.strptime(event["last_activity_at"], "%Y-%m-%dT%H:%M:%SZ")

    for column in ["ghap_applied_at", "ghap_last_activity_at"]:
        pd.to_datetime(applications[column], errors="raise")


def write_outputs(
    jobs: pd.DataFrame,
    openings: pd.DataFrame,
    candidates: pd.DataFrame,
    applications: pd.DataFrame,
    offers: pd.DataFrame,
    events: list[dict],
) -> None:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    excel_path = GENERATED_DIR / "hiring_data_large.xlsx"
    json_path = GENERATED_DIR / "webhook_application_events_large.json"

    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        jobs.to_excel(writer, sheet_name="ghjb_jobs", index=False)
        openings.to_excel(writer, sheet_name="ghop_openings", index=False)
        candidates.to_excel(writer, sheet_name="ghca_candidates", index=False)
        applications.to_excel(writer, sheet_name="ghap_applications", index=False)
        offers.to_excel(writer, sheet_name="ghof_offers", index=False)

    with json_path.open("w", encoding="utf-8") as file:
        json.dump(events, file, indent=2, ensure_ascii=False)

    print("Generated larger synthetic dataset:")
    print(f"- {excel_path}")
    print(f"- {json_path}")
    print()
    print("Counts:")
    print(f"- jobs: {len(jobs)}")
    print(f"- openings: {len(openings)}")
    print(f"- candidates: {len(candidates)}")
    print(f"- applications: {len(applications)}")
    print(f"- offers: {len(offers)}")
    print(f"- application_events: {len(events)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a larger Greenhouse-like synthetic dataset.")
    parser.add_argument("--jobs", type=int, default=120)
    parser.add_argument("--candidates", type=int, default=1800)
    parser.add_argument("--applications", type=int, default=2500)
    parser.add_argument("--seed", type=int, default=42)

    args = parser.parse_args()

    random.seed(args.seed)

    base_date = datetime(2026, 1, 1, 8, 0, 0)

    jobs = generate_jobs(args.jobs, base_date)
    candidates = generate_candidates(args.candidates, base_date)
    applications, events = generate_applications_and_events(
        args.applications,
        jobs,
        candidates,
        base_date,
    )
    openings = generate_openings(jobs, applications)
    offers = generate_offers(applications, openings)

    validate_dataset(
        jobs=jobs,
        openings=openings,
        candidates=candidates,
        applications=applications,
        offers=offers,
        events=events,
    )

    write_outputs(
        jobs=jobs,
        openings=openings,
        candidates=candidates,
        applications=applications,
        offers=offers,
        events=events,
    )


if __name__ == "__main__":
    main()
