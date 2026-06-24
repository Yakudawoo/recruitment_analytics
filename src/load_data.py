import json
from pathlib import Path

import pandas as pd


DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def clean_null_values(df):
    return df.replace("(null)", pd.NA)


def load_excel_data():
    excel_path = DATA_DIR / "hiring_data.xlsx"

    sheets = pd.read_excel(
        excel_path,
        sheet_name=None
    )

    cleaned_sheets = {}

    for sheet_name, df in sheets.items():
        cleaned_sheets[sheet_name] = clean_null_values(df)

    return cleaned_sheets


def load_webhook_events():
    json_path = DATA_DIR / "webhook_application_events.json"

    with open(json_path, "r", encoding="utf-8") as file:
        events = json.load(file)

    df = pd.DataFrame(events)
    df = clean_null_values(df)

    if "last_activity_at" in df.columns:
        df["last_activity_at"] = pd.to_datetime(df["last_activity_at"], errors="coerce")

    return df


def load_all_data():
    excel_data = load_excel_data()
    webhook_events = load_webhook_events()

    return {
        "jobs": excel_data["ghjb_jobs"],
        "openings": excel_data["ghop_openings"],
        "candidates": excel_data["ghca_candidates"],
        "applications": excel_data["ghap_applications"],
        "offers": excel_data["ghof_offers"],
        "events": webhook_events,
    }


if __name__ == "__main__":
    data = load_all_data()

    for name, df in data.items():
        print(f"\n{name.upper()}")
        print(df.shape)
        print(df.head())