with applications as (

    select * from {{ ref('fact_application') }}

)

select
    current_timestamp() as generated_at,
    countif(is_hired) as total_hired_applications,
    countif(is_hired and time_to_hire_days is not null) as hired_applications_with_valid_time_to_hire,
    avg(case when is_hired then time_to_hire_days end) as avg_time_to_hire_days,
    countif(
        is_hired
        and coalesce(application_source, '') != 'supabase_operational_source'
        and time_to_hire_days is not null
    ) as historical_hired_applications_included,
    countif(
        is_hired
        and application_source = 'supabase_operational_source'
        and time_to_hire_days is not null
    ) as supabase_outcome_hired_applications_included,
    countif(is_hired and time_to_hire_days is null) as hired_applications_excluded_from_avg

from applications
