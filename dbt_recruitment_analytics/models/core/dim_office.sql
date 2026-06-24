select distinct
    office_id,
    office_name

from {{ ref('stg_greenhouse_jobs') }}

where office_id is not null
