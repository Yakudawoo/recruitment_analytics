with events as (

    select * from {{ ref('stg_greenhouse_application_events') }}

),

applications as (

    select * from {{ ref('fact_application') }}

),

jobs as (

    select * from {{ ref('dim_job') }}

),

classified_events as (

    select
        applications.office_id,
        coalesce(jobs.office_name, 'Unknown office') as office_name,

        applications.department_id,
        coalesce(jobs.department_name, 'Unknown department') as department_name,

        events.current_stage as stage_name,

        case events.current_stage
            when 'Application Review' then 1
            when 'AI Recommendation Review' then 2
            when 'Recruiter Interview' then 3
            when 'Hiring Manager Review' then 4
            when 'Hiring Manager Interview' then 5
            when 'Take Home Test' then 6
            when 'Face to Face' then 7
            when 'HR Interview' then 8
            when 'Final Interview' then 9
            when 'Final (Executive) Interview' then 10
            when 'Reference Check' then 11
            when 'Offer' then 12
            else 99
        end as stage_order,

        events.application_id

    from events

    inner join applications
        on events.application_id = applications.application_id

    left join jobs
        on applications.job_id = jobs.job_id

    where events.current_stage is not null

)

select
    office_id,
    office_name,
    department_id,
    department_name,
    stage_order,
    stage_name,
    count(distinct application_id) as applications_reached

from classified_events

group by
    office_id,
    office_name,
    department_id,
    department_name,
    stage_order,
    stage_name

order by
    office_name,
    department_name,
    stage_order
