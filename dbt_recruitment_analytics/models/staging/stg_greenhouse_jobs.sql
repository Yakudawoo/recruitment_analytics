select
    safe_cast(ghjb_job_id as int64) as job_id,
    ghjb_job_name as job_name,
    safe_cast(ghjb_requisition_id as int64) as requisition_id,
    ghjb_job_status as job_status,

    safe_cast(ghjb_created_at as timestamp) as created_at,
    safe_cast(ghjb_opened_at as timestamp) as opened_at,
    safe_cast(ghjb_closed_at as timestamp) as closed_at,

    safe_cast(ghjb_gh_department_id as int64) as department_id,
    ghjb_gh_department_name as department_name,

    safe_cast(ghjb_gh_office_id as int64) as office_id,
    ghjb_gh_office_name as office_name,

    safe_cast(ghjb_hiring_manager_id as int64) as hiring_manager_id,
    ghjb_hiring_manager_name as hiring_manager_name,

    safe_cast(ghjb_recruiter_id as int64) as recruiter_id,
    ghjb_recruiter_name as recruiter_name,

    ghjb_employment_type as employment_type,
    ghjb_budget_owner as budget_owner,
    ghjb_executive as executive,
    safe_cast(ghjb_fte as float64) as fte,
    ghjb_job_type as job_type,

    _ingestion_batch_id,
    safe_cast(_ingested_at as timestamp) as ingested_at,
    _source_system,
    _source_object,
    _loaded_by

from {{ source('greenhouse_raw', 'raw_greenhouse_jobs') }}
