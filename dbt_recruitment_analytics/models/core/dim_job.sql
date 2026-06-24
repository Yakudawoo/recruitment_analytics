select distinct
    job_id,
    job_name,
    requisition_id,
    job_status,

    department_id,
    department_name,

    office_id,
    office_name,

    hiring_manager_id,
    hiring_manager_name,

    recruiter_id,
    recruiter_name,

    employment_type,
    budget_owner,
    executive,
    fte,
    job_type,

    created_at,
    opened_at,
    closed_at

from {{ ref('stg_greenhouse_jobs') }}

where job_id is not null
