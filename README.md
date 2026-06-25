
## Larger synthetic dataset

A larger synthetic Greenhouse-like dataset was added to make the HR-facing dashboard more representative.

The generator is available here:

```text
scripts/generate_large_mock_dataset.py
It generates:

jobs;
candidates;
applications;
openings;
offers;
application stage events.

Generated files are written to:

data/generated/hiring_data_large.xlsx
data/generated/webhook_application_events_large.json

To run the Mock Greenhouse API with the larger dataset:

export MOCK_DATASET_PROFILE=large
uvicorn mock_greenhouse.app:app --reload --port 8000

To use the original provided dataset:

export MOCK_DATASET_PROFILE=original
uvicorn mock_greenhouse.app:app --reload --port 8000

The larger dataset preserves referential consistency between jobs, candidates, applications, offers and stage events.
