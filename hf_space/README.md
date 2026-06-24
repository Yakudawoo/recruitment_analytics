---
title: Recruitment Analytics Dashboard
emoji: 📊
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# Recruitment Analytics Dashboard

Production-like Streamlit dashboard connected to BigQuery marts.

Pipeline behind the dashboard:

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
Airflow orchestrates the local end-to-end pipeline:
API health check, API-to-BigQuery ingestion, dbt transformations, and dbt tests.

The public dashboard consumes BigQuery mart tables directly.
