with applications as (

    select * from {{ ref('fact_application') }}

),

jobs as (

    select * from {{ ref('dim_job') }}

),

offers as (

    select * from {{ ref('fact_offer') }}

),

stage_transitions as (

    select * from {{ ref('fact_stage_transition') }}

),

application_metrics as (

    select
        count(*) as total_applications,
        countif(is_active) as active_applications,
        countif(is_rejected) as rejected_applications,
        countif(is_hired) as hired_applications,
        countif(is_hired and time_to_hire_days is not null) as hired_applications_with_valid_time_to_hire,
        countif(
            is_hired
            and application_source = 'supabase_operational_source'
            and time_to_hire_days is not null
        ) as supabase_outcome_hired_applications_with_valid_time_to_hire,
        countif(
            is_hired
            and coalesce(application_source, '') != 'supabase_operational_source'
            and time_to_hire_days is not null
        ) as historical_hired_applications_with_valid_time_to_hire,

        avg(case when is_hired then time_to_hire_days end) as avg_time_to_hire_days

    from applications

),

job_metrics as (

    select
        countif(job_status = 'open') as open_jobs,
        countif(job_status = 'closed') as closed_jobs,
        count(*) as total_jobs

    from jobs

),

offer_metrics as (

    select
        count(*) as total_offers,
        countif(is_accepted) as accepted_offers

    from offers

),

sla_metrics as (

    select
        countif(is_recruiter_owned_stage) as recruiter_owned_stage_cases,
        countif(is_recruiter_owned_stage and sla_met) as recruiter_sla_met_cases,
        countif(is_recruiter_owned_stage and sla_met = false) as recruiter_sla_breached_cases,
        safe_divide(
            countif(is_recruiter_owned_stage and sla_met),
            countif(is_recruiter_owned_stage)
        ) as recruiter_sla_compliance_rate

    from stage_transitions

)

select
    current_timestamp() as generated_at,

    job_metrics.total_jobs,
    job_metrics.open_jobs,
    job_metrics.closed_jobs,

    application_metrics.total_applications,
    application_metrics.active_applications,
    application_metrics.rejected_applications,
    application_metrics.hired_applications,
    application_metrics.hired_applications_with_valid_time_to_hire,
    application_metrics.historical_hired_applications_with_valid_time_to_hire,
    application_metrics.supabase_outcome_hired_applications_with_valid_time_to_hire,
    application_metrics.avg_time_to_hire_days,

    offer_metrics.total_offers,
    offer_metrics.accepted_offers,

    sla_metrics.recruiter_owned_stage_cases,
    sla_metrics.recruiter_sla_met_cases,
    sla_metrics.recruiter_sla_breached_cases,
    sla_metrics.recruiter_sla_compliance_rate

from application_metrics
cross join job_metrics
cross join offer_metrics
cross join sla_metrics
