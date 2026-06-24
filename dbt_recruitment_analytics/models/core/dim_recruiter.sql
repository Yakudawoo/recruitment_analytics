with recruiters_from_jobs as (

    select distinct
        recruiter_id,
        recruiter_name

    from {{ ref('stg_greenhouse_jobs') }}

    where recruiter_id is not null

),

recruiters_from_candidates as (

    select distinct
        recruiter_id,
        recruiter_name

    from {{ ref('stg_greenhouse_candidates') }}

    where recruiter_id is not null

),

unioned as (

    select * from recruiters_from_jobs

    union distinct

    select * from recruiters_from_candidates

)

select distinct
    recruiter_id,
    recruiter_name

from unioned

where recruiter_id is not null
