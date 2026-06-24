select
    safe_cast(ghop_id as int64) as opening_row_id,
    safe_cast(ghop_opening_id as int64) as opening_id,
    safe_cast(ghop_job_id as int64) as job_id,
    safe_cast(ghop_application_id as int64) as application_id,

    ghop_status as opening_status,
    ghop_close_reason_name as close_reason_name,
    ghop_priority as priority,
    ghop_additional_hire_replacement as additional_hire_replacement,

    safe_cast(ghop_opened_at as timestamp) as opened_at,
    safe_cast(ghop_closed_at as timestamp) as closed_at,

    _ingestion_batch_id,
    safe_cast(_ingested_at as timestamp) as ingested_at,
    _source_system,
    _source_object,
    _loaded_by

from {{ source('greenhouse_raw', 'raw_greenhouse_openings') }}
