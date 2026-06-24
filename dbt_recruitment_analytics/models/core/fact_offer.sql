select
    offers.offer_id,
    offers.application_id,

    applications.candidate_id,
    applications.job_id,
    applications.recruiter_id,
    applications.department_id,
    applications.office_id,

    offers.offer_status,
    offers.created_at,
    offers.updated_at,
    offers.resolved_at,
    offers.starts_at,

    case
        when offers.offer_status = 'accepted' then true
        else false
    end as is_accepted

from {{ ref('stg_greenhouse_offers') }} as offers

left join {{ ref('fact_application') }} as applications
    on offers.application_id = applications.application_id

where offers.offer_id is not null
