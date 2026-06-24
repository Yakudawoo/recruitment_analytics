select
    safe_cast(ghca_candidate_id as int64) as candidate_id,
    ghca_first_name as first_name,
    ghca_last_name as last_name,
    concat(coalesce(ghca_first_name, ''), ' ', coalesce(ghca_last_name, '')) as candidate_full_name,

    safe_cast(ghca_recruiter_id as int64) as recruiter_id,
    ghca_recruiter_name as recruiter_name,

    safe_cast(ghca_created_at as timestamp) as created_at,
    safe_cast(ghca_updated_at as timestamp) as updated_at,

    _ingestion_batch_id,
    safe_cast(_ingested_at as timestamp) as ingested_at,
    _source_system,
    _source_object,
    _loaded_by

from {{ source('greenhouse_raw', 'raw_greenhouse_candidates') }}
