with applications as (

    select * from {{ ref('fact_application') }}

),

stage_transitions as (

    select * from {{ ref('fact_stage_transition') }}

),

offers as (

    select * from {{ ref('fact_offer') }}

),

recruiters as (

    select * from {{ ref('dim_recruiter') }}

),

offices as (

    select * from {{ ref('dim_office') }}

),

departments as (

    select * from {{ ref('dim_department') }}

),

application_metrics as (

    select
        recruiter_id,
        office_id,
        department_id,

        count(distinct application_id) as total_applications,
        count(distinct case when is_active then application_id end) as active_applications,
        count(distinct case when is_rejected then application_id end) as rejected_applications,
        count(distinct case when is_hired then application_id end) as hired_applications,
        count(distinct job_id) as jobs_touched

    from applications

    group by
        recruiter_id,
        office_id,
        department_id

),

stage_metrics as (

    select
        recruiter_id,
        office_id,
        department_id,

        count(*) as recruiter_owned_stage_cases,
        countif(sla_met) as sla_met_cases,
        countif(sla_met = false) as sla_breached_cases,

        avg(duration_days) as avg_recruiter_stage_duration_days,

        safe_divide(
            countif(sla_met),
            count(*)
        ) as sla_compliance_rate

    from stage_transitions

    where is_recruiter_owned_stage

    group by
        recruiter_id,
        office_id,
        department_id

),

offer_metrics as (

    select
        recruiter_id,
        office_id,
        department_id,

        count(distinct offer_id) as total_offers,
        count(distinct case when is_accepted then offer_id end) as accepted_offers

    from offers

    group by
        recruiter_id,
        office_id,
        department_id

)

select
    application_metrics.recruiter_id,
    coalesce(recruiters.recruiter_name, 'Unknown recruiter') as recruiter_name,

    application_metrics.office_id,
    coalesce(offices.office_name, 'Unknown office') as office_name,

    application_metrics.department_id,
    coalesce(departments.department_name, 'Unknown department') as department_name,

    application_metrics.total_applications,
    application_metrics.active_applications,
    application_metrics.rejected_applications,
    application_metrics.hired_applications,
    application_metrics.jobs_touched,

    coalesce(stage_metrics.recruiter_owned_stage_cases, 0) as recruiter_owned_stage_cases,
    coalesce(stage_metrics.sla_met_cases, 0) as sla_met_cases,
    coalesce(stage_metrics.sla_breached_cases, 0) as sla_breached_cases,
    stage_metrics.avg_recruiter_stage_duration_days,
    stage_metrics.sla_compliance_rate,

    coalesce(offer_metrics.total_offers, 0) as total_offers,
    coalesce(offer_metrics.accepted_offers, 0) as accepted_offers

from application_metrics

left join stage_metrics
    on application_metrics.recruiter_id = stage_metrics.recruiter_id
    and application_metrics.office_id = stage_metrics.office_id
    and application_metrics.department_id = stage_metrics.department_id

left join offer_metrics
    on application_metrics.recruiter_id = offer_metrics.recruiter_id
    and application_metrics.office_id = offer_metrics.office_id
    and application_metrics.department_id = offer_metrics.department_id

left join recruiters
    on application_metrics.recruiter_id = recruiters.recruiter_id

left join offices
    on application_metrics.office_id = offices.office_id

left join departments
    on application_metrics.department_id = departments.department_id

order by
    active_applications desc,
    sla_breached_cases desc,
    recruiter_name
