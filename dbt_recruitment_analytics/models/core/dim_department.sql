select distinct
    department_id,
    department_name

from {{ ref('stg_greenhouse_jobs') }}

where department_id is not null
