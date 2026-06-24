with ordered_events as (

    select
        application_id,
        action,

        previous_status,
        current_status,

        previous_stage,
        current_stage,

        event_at,

        lag(event_at) over (
            partition by application_id
            order by event_at
        ) as previous_event_at,

        ingested_at

    from {{ ref('stg_greenhouse_application_events') }}

),

stage_durations as (

    select
        application_id,
        action,

        previous_status,
        current_status,

        previous_stage as stage_name,
        previous_stage,
        current_stage,

        previous_event_at as stage_started_at,
        event_at as stage_ended_at,

        timestamp_diff(event_at, previous_event_at, hour) as duration_hours,
        timestamp_diff(event_at, previous_event_at, hour) / 24.0 as duration_days,

        case
            when previous_stage in ('Application Review', 'Recruiter Interview') then true
            else false
        end as is_recruiter_owned_stage,

        case
            when previous_stage in ('Application Review', 'Recruiter Interview') then 3
            else null
        end as sla_target_days,

        ingested_at

    from ordered_events

    where previous_event_at is not null
      and previous_stage is not null

),

final as (

    select
        stage_durations.*,

        applications.candidate_id,
        applications.job_id,
        applications.recruiter_id,
        applications.department_id,
        applications.office_id,

        case
            when sla_target_days is null then null
            when duration_days <= sla_target_days then true
            else false
        end as sla_met

    from stage_durations

    left join {{ ref('fact_application') }} as applications
        on stage_durations.application_id = applications.application_id

)

select * from final
