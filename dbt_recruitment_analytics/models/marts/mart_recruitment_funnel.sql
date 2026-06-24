with events as (

    select * from {{ ref('stg_greenhouse_application_events') }}

),

stage_counts as (

    select
        current_stage as stage_name,
        count(distinct application_id) as applications_reached

    from events

    where current_stage is not null

    group by current_stage

),

ordered as (

    select
        stage_name,
        applications_reached,

        case stage_name
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
        end as stage_order

    from stage_counts

)

select
    stage_order,
    stage_name,
    applications_reached

from ordered

order by stage_order
