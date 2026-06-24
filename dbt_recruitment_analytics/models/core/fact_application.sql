select
    applications.application_id,
    applications.candidate_id,
    applications.job_id,

    coalesce(jobs.recruiter_id, candidates.recruiter_id) as recruiter_id,

    jobs.department_id,
    jobs.office_id,

    applications.application_status,
    applications.current_stage,
    applications.application_source,
    applications.rejection_reason,

    applications.applied_at,
    applications.rejected_at,
    applications.last_activity_at,

    applications.jobs_count,

    case
        when applications.application_status = 'active' then true
        else false
    end as is_active,

    case
        when applications.application_status = 'rejected' then true
        else false
    end as is_rejected,

    case
        when applications.application_status = 'hired' then true
        else false
    end as is_hired

from {{ ref('stg_greenhouse_applications') }} as applications

left join {{ ref('stg_greenhouse_jobs') }} as jobs
    on applications.job_id = jobs.job_id

left join {{ ref('stg_greenhouse_candidates') }} as candidates
    on applications.candidate_id = candidates.candidate_id

where applications.application_id is not null
