#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$PROJECT_ROOT"

export USE_SUPABASE_OPERATIONAL_SOURCE=true
export BQ_RAW_DATASET=raw_greenhouse_demo
export BQ_STG_DATASET=stg_greenhouse_demo
export BQ_CORE_DATASET=core_greenhouse_demo
export BQ_MARTS_DATASET=marts_recruitment_demo
export BQ_LOCATION=EU

./scripts/run_supabase_recruitment_pipeline.sh
