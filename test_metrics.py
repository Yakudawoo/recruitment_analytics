from src.load_data import load_all_data
from src.transform import build_analytics_model
from src.metrics import (
    applications_by_stage,
    applications_by_status,
    calculate_global_metrics,
    delayed_recruiter_cases,
    recruiter_sla_summary,
)


data = load_all_data()
model = build_analytics_model(data)

print("GLOBAL METRICS")
print(calculate_global_metrics(model))

print("\nAPPLICATIONS BY STATUS")
print(applications_by_status(model))

print("\nAPPLICATIONS BY STAGE")
print(applications_by_stage(model))

print("\nRECRUITER SLA SUMMARY")
print(recruiter_sla_summary(model))

print("\nDELAYED CASES")
print(delayed_recruiter_cases(model))