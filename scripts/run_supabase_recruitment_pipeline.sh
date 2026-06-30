#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$PROJECT_ROOT"

OVERRIDE_BQ_RAW_DATASET="${BQ_RAW_DATASET:-}"
OVERRIDE_BQ_STG_DATASET="${BQ_STG_DATASET:-}"
OVERRIDE_BQ_CORE_DATASET="${BQ_CORE_DATASET:-}"
OVERRIDE_BQ_MARTS_DATASET="${BQ_MARTS_DATASET:-}"
OVERRIDE_BQ_LOCATION="${BQ_LOCATION:-}"
OVERRIDE_USE_SUPABASE_OPERATIONAL_SOURCE="${USE_SUPABASE_OPERATIONAL_SOURCE:-}"

if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

export BQ_RAW_DATASET="${OVERRIDE_BQ_RAW_DATASET:-${BQ_RAW_DATASET:-raw_greenhouse}}"
export BQ_STG_DATASET="${OVERRIDE_BQ_STG_DATASET:-${BQ_STG_DATASET:-stg_greenhouse}}"
export BQ_CORE_DATASET="${OVERRIDE_BQ_CORE_DATASET:-${BQ_CORE_DATASET:-core_greenhouse}}"
export BQ_MARTS_DATASET="${OVERRIDE_BQ_MARTS_DATASET:-${BQ_MARTS_DATASET:-marts_recruitment}}"
export BQ_LOCATION="${OVERRIDE_BQ_LOCATION:-${BQ_LOCATION:-EU}}"
export USE_SUPABASE_OPERATIONAL_SOURCE="${OVERRIDE_USE_SUPABASE_OPERATIONAL_SOURCE:-${USE_SUPABASE_OPERATIONAL_SOURCE:-false}}"

if [ "$USE_SUPABASE_OPERATIONAL_SOURCE" != "true" ]; then
  echo "Refusing to run: USE_SUPABASE_OPERATIONAL_SOURCE must be true."
  exit 1
fi

echo "Using Supabase operational source"
echo "Using BigQuery datasets:"
echo "  RAW:   $BQ_RAW_DATASET"
echo "  STG:   $BQ_STG_DATASET"
echo "  CORE:  $BQ_CORE_DATASET"
echo "  MARTS: $BQ_MARTS_DATASET"
echo "  LOCATION: $BQ_LOCATION"

echo "Loading Supabase operational tables to BigQuery RAW..."
.venv/bin/python -m ingestion.load_supabase_operational_to_bigquery

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

echo "Supabase recruitment analytics pipeline completed successfully."
