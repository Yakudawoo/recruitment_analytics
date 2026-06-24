#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$PROJECT_ROOT"

set -a
source .env
set +a

echo "Checking Mock Greenhouse API health..."
curl -sf "$MOCK_GREENHOUSE_BASE_URL/health" > /dev/null

echo "Loading Greenhouse API data to BigQuery RAW..."
.venv/bin/python -m ingestion.load_greenhouse_api_to_bigquery

echo "Running dbt staging models..."
.venv/bin/dbt run \
  --select path:models/staging \
  --project-dir dbt_recruitment_analytics \
  --profiles-dir dbt_recruitment_analytics

echo "Running dbt core models..."
.venv/bin/dbt run \
  --select path:models/core \
  --project-dir dbt_recruitment_analytics \
  --profiles-dir dbt_recruitment_analytics

echo "Running dbt marts models..."
.venv/bin/dbt run \
  --select path:models/marts \
  --project-dir dbt_recruitment_analytics \
  --profiles-dir dbt_recruitment_analytics

echo "Running dbt tests..."
.venv/bin/dbt test \
  --project-dir dbt_recruitment_analytics \
  --profiles-dir dbt_recruitment_analytics

echo "Recruitment analytics pipeline completed successfully."
