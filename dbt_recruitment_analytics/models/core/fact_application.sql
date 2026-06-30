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
    case
        when applications.application_status = 'hired'
        then coalesce(applications.hired_at, applications.last_activity_at)
    end as hired_at,

    case
        when applications.application_status = 'hired'
            and applications.applied_at is not null
            and coalesce(applications.hired_at, applications.last_activity_at) is not null
            and timestamp_diff(
                coalesce(applications.hired_at, applications.last_activity_at),
                applications.applied_at,
                day
            ) >= 0
        then timestamp_diff(
            coalesce(applications.hired_at, applications.last_activity_at),
            applications.applied_at,
            day
        )
    end as time_to_hire_days,

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
