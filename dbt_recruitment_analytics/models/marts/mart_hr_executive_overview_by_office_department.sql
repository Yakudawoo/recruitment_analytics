with jobs as (

    select * from {{ ref('dim_job') }}

),

applications as (

    select * from {{ ref('fact_application') }}

),

offers as (

    select * from {{ ref('fact_offer') }}

),

stage_transitions as (

    select * from {{ ref('fact_stage_transition') }}

),

office_department_scope as (

    select distinct
        office_id,
        office_name,
        department_id,
        department_name

    from jobs

    where office_id is not null
      and department_id is not null

),

job_metrics as (

    select
        office_id,
        department_id,
        count(*) as total_jobs,
        countif(job_status = 'open') as open_jobs,
        countif(job_status = 'closed') as closed_jobs

    from jobs

    group by
        office_id,
        department_id

),

application_metrics as (

    select
        office_id,
        department_id,
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

    group by
        office_id,
        department_id

),

offer_metrics as (

    select
        office_id,
        department_id,
        count(*) as total_offers,
        countif(is_accepted) as accepted_offers

    from offers

    group by
        office_id,
        department_id

),

sla_metrics as (

    select
        office_id,
        department_id,
        countif(is_recruiter_owned_stage) as recruiter_owned_stage_cases,
        countif(is_recruiter_owned_stage and sla_met) as recruiter_sla_met_cases,
        countif(is_recruiter_owned_stage and sla_met = false) as recruiter_sla_breached_cases,

        safe_divide(
            countif(is_recruiter_owned_stage and sla_met),
            countif(is_recruiter_owned_stage)
        ) as recruiter_sla_compliance_rate

    from stage_transitions

    group by
        office_id,
        department_id

)

select
    current_timestamp() as generated_at,

    scope.office_id,
    coalesce(scope.office_name, 'Unknown office') as office_name,

    scope.department_id,
    coalesce(scope.department_name, 'Unknown department') as department_name,

    coalesce(job_metrics.total_jobs, 0) as total_jobs,
    coalesce(job_metrics.open_jobs, 0) as open_jobs,
    coalesce(job_metrics.closed_jobs, 0) as closed_jobs,

    coalesce(application_metrics.total_applications, 0) as total_applications,
    coalesce(application_metrics.active_applications, 0) as active_applications,
    coalesce(application_metrics.rejected_applications, 0) as rejected_applications,
    coalesce(application_metrics.hired_applications, 0) as hired_applications,
    coalesce(application_metrics.hired_applications_with_valid_time_to_hire, 0) as hired_applications_with_valid_time_to_hire,
    coalesce(application_metrics.historical_hired_applications_with_valid_time_to_hire, 0) as historical_hired_applications_with_valid_time_to_hire,
    coalesce(application_metrics.supabase_outcome_hired_applications_with_valid_time_to_hire, 0) as supabase_outcome_hired_applications_with_valid_time_to_hire,
    application_metrics.avg_time_to_hire_days,

    coalesce(offer_metrics.total_offers, 0) as total_offers,
    coalesce(offer_metrics.accepted_offers, 0) as accepted_offers,

    coalesce(sla_metrics.recruiter_owned_stage_cases, 0) as recruiter_owned_stage_cases,
    coalesce(sla_metrics.recruiter_sla_met_cases, 0) as recruiter_sla_met_cases,
    coalesce(sla_metrics.recruiter_sla_breached_cases, 0) as recruiter_sla_breached_cases,
    sla_metrics.recruiter_sla_compliance_rate

from office_department_scope as scope

left join job_metrics
    on scope.office_id = job_metrics.office_id
    and scope.department_id = job_metrics.department_id

left join application_metrics
    on scope.office_id = application_metrics.office_id
    and scope.department_id = application_metrics.department_id

left join offer_metrics
    on scope.office_id = offer_metrics.office_id
    and scope.department_id = offer_metrics.department_id

left join sla_metrics
    on scope.office_id = sla_metrics.office_id
    and scope.department_id = sla_metrics.department_id
