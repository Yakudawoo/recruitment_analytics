with source_events as (

    select
        organization_id,
        organization_name,
        action,
        safe_cast(application_id as int64) as application_id,

        previous_status,
        current_status,

        previous_stage,
        current_stage,

        safe_cast(last_activity_at as timestamp) as event_at,
        safe_cast(rejected_at as timestamp) as rejected_at,

        rejection_reason,
        rejection_details,

        _ingestion_batch_id,
        safe_cast(_ingested_at as timestamp) as ingested_at,
        _source_system,
        _source_object,
        _loaded_by

    from {{ source('greenhouse_raw', 'raw_greenhouse_application_events') }}

),

deduplicated as (

    select
        *,
        row_number() over (
            partition by
                application_id,
                action,
                previous_status,
                current_status,
                previous_stage,
                current_stage,
                event_at
            order by ingested_at desc
        ) as row_number

    from source_events

)

select
    organization_id,
    organization_name,
    action,
    application_id,
    previous_status,
    current_status,
    previous_stage,
    current_stage,
    event_at,
    rejected_at,
    rejection_reason,
    rejection_details,
    _ingestion_batch_id,
    ingested_at,
    _source_system,
    _source_object,
    _loaded_by

from deduplicated

where row_number = 1
