# Mock Greenhouse API

This service simulates a small subset of the Greenhouse API for the recruitment analytics exercise.

The provided Excel and JSON files are used only as seed data.  
They are not part of the target production architecture.

In production, this layer would be replaced by the real Greenhouse REST API and Greenhouse webhook events.

## Run

From the repository root:

uvicorn mock_greenhouse.app:app --reload --port 8000

## Main endpoints

GET /health
GET /jobs
GET /openings
GET /candidates
GET /applications
GET /offers
GET /application-events

## Event simulation

POST /applications/{application_id}/stage-change
POST /applications/{application_id}/reject
POST /applications/{application_id}/hire
POST /webhooks/register
