with source_departments as (

    select
        department_id,
        department_name

    from {{ ref('stg_greenhouse_jobs') }}

    where department_id is not null

),

deduplicated as (

    select
        department_id,

        array_agg(
            department_name ignore nulls
            order by department_name
            limit 1
        )[safe_offset(0)] as department_name

    from source_departments

    group by department_id

)

select
    department_id,
    department_name

from deduplicated
