select
    safe_cast(ghap_application_id as int64) as application_id,
    safe_cast(ghap_candidate_id as int64) as candidate_id,
    safe_cast(ghap_job_id as int64) as job_id,

    safe_cast(ghap_applied_at as timestamp) as applied_at,
    safe_cast(ghap_rejected_at as timestamp) as rejected_at,
    safe_cast(ghap_last_activity_at as timestamp) as last_activity_at,
    safe_cast(ghap_hired_at as timestamp) as hired_at,

    ghap_source as application_source,
    ghap_rejection_reason as rejection_reason,
    ghap_status as application_status,
    ghap_application_current_stage as current_stage,
    safe_cast(ghap_jobs_count as int64) as jobs_count,

    _ingestion_batch_id,
    safe_cast(_ingested_at as timestamp) as ingested_at,
    _source_system,
    _source_object,
    _loaded_by

from {{ source('greenhouse_raw', 'raw_greenhouse_applications') }}
