with stage_transitions as (

    select * from {{ ref('fact_stage_transition') }}

),

recruiters as (

    select * from {{ ref('dim_recruiter') }}

),

jobs as (

    select * from {{ ref('dim_job') }}

),

final as (

    select
        stage_transitions.recruiter_id,
        recruiters.recruiter_name,

        stage_transitions.department_id,
        jobs.department_name,

        stage_transitions.office_id,
        jobs.office_name,

        stage_transitions.stage_name,
        stage_transitions.sla_target_days,

        count(*) as total_cases,
        avg(stage_transitions.duration_days) as avg_duration_days,

        countif(stage_transitions.sla_met) as sla_met_cases,
        countif(stage_transitions.sla_met = false) as sla_breached_cases,

        safe_divide(
            countif(stage_transitions.sla_met),
            count(*)
        ) as sla_compliance_rate

    from stage_transitions

    left join recruiters
        on stage_transitions.recruiter_id = recruiters.recruiter_id

    left join jobs
        on stage_transitions.job_id = jobs.job_id

    where stage_transitions.is_recruiter_owned_stage

    group by
        stage_transitions.recruiter_id,
        recruiters.recruiter_name,
        stage_transitions.department_id,
        jobs.department_name,
        stage_transitions.office_id,
        jobs.office_name,
        stage_transitions.stage_name,
        stage_transitions.sla_target_days

)

select
    *

from final

order by sla_compliance_rate asc, avg_duration_days desc
