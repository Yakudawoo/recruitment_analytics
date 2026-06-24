select distinct
    candidate_id,
    first_name,
    last_name,
    candidate_full_name,
    recruiter_id,
    recruiter_name,
    created_at,
    updated_at

from {{ ref('stg_greenhouse_candidates') }}

where candidate_id is not null
