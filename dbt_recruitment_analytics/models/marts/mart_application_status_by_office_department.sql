with applications as (

    select * from {{ ref('fact_application') }}

),

jobs as (

    select * from {{ ref('dim_job') }}

),

status_counts as (

    select
        applications.office_id,
        coalesce(jobs.office_name, 'Unknown office') as office_name,

        applications.department_id,
        coalesce(jobs.department_name, 'Unknown department') as department_name,

        applications.application_status,

        count(distinct applications.application_id) as applications_count

    from applications

    left join jobs
        on applications.job_id = jobs.job_id

    group by
        applications.office_id,
        office_name,
        applications.department_id,
        department_name,
        applications.application_status

)

select
    office_id,
    office_name,
    department_id,
    department_name,
    application_status,
    applications_count,

    safe_divide(
        applications_count,
        sum(applications_count) over (
            partition by office_id, department_id
        )
    ) as status_share

from status_counts

order by
    office_name,
    department_name,
    application_status
