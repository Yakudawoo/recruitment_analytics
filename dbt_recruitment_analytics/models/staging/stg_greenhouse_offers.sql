select
    safe_cast(ghof_offer_id as int64) as offer_id,
    safe_cast(ghof_application_id as int64) as application_id,

    ghof_status as offer_status,

    safe_cast(ghof_created_at as timestamp) as created_at,
    safe_cast(ghof_updated_at as timestamp) as updated_at,
    safe_cast(ghof_resolved_at as timestamp) as resolved_at,
    safe_cast(ghof_starts_at as timestamp) as starts_at,

    _ingestion_batch_id,
    safe_cast(_ingested_at as timestamp) as ingested_at,
    _source_system,
    _source_object,
    _loaded_by

from {{ source('greenhouse_raw', 'raw_greenhouse_offers') }}
