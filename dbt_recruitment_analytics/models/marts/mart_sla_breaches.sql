with stage_transitions as (

    select * from {{ ref('fact_stage_transition') }}

),

applications as (

    select * from {{ ref('fact_application') }}

),

candidates as (

    select * from {{ ref('dim_candidate') }}

),

jobs as (

    select * from {{ ref('dim_job') }}

),

recruiters as (

    select * from {{ ref('dim_recruiter') }}

)

select
    stage_transitions.application_id,
    applications.candidate_id,
    candidates.candidate_full_name,

    applications.job_id,
    jobs.job_name,

    stage_transitions.recruiter_id,
    recruiters.recruiter_name,

    stage_transitions.department_id,
    jobs.department_name,

    stage_transitions.office_id,
    jobs.office_name,

    stage_transitions.stage_name,
    stage_transitions.stage_started_at,
    stage_transitions.stage_ended_at,
    stage_transitions.duration_days,
    stage_transitions.sla_target_days,

    applications.application_status,
    applications.current_stage

from stage_transitions

left join applications
    on stage_transitions.application_id = applications.application_id

left join candidates
    on applications.candidate_id = candidates.candidate_id

left join jobs
    on applications.job_id = jobs.job_id

left join recruiters
    on stage_transitions.recruiter_id = recruiters.recruiter_id

where stage_transitions.is_recruiter_owned_stage
  and stage_transitions.sla_met = false

order by stage_transitions.duration_days desc
