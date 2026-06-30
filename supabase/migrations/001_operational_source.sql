create extension if not exists pgcrypto;

create table if not exists public.profiles (
    id uuid primary key references auth.users(id) on delete cascade,
    email text unique not null,
    full_name text,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

create table if not exists public.app_user_roles (
    user_id uuid references auth.users(id) on delete cascade,
    email text not null,
    role text not null check (
        role in (
            'super_admin',
            'dev_admin',
            'hr_manager',
            'business_manager',
            'analyst_readonly'
        )
    ),
    is_active boolean default true,
    created_at timestamptz default now(),
    primary key (user_id, role)
);

create table if not exists public.applications (
    application_id bigint primary key,
    candidate_id bigint,
    job_id bigint,
    candidate_full_name text,
    candidate_name text,
    job_title text,
    current_stage text,
    status text,
    recruiter text,
    recruiter_name text,
    recruiter_email text,
    office_name text,
    department_name text,
    office text,
    department text,
    applied_at timestamptz,
    created_at timestamptz,
    hired_at timestamptz,
    updated_at timestamptz default now()
);

alter table public.applications
add column if not exists applied_at timestamptz,
add column if not exists created_at timestamptz,
add column if not exists hired_at timestamptz,
add column if not exists candidate_full_name text,
add column if not exists candidate_name text,
add column if not exists job_title text,
add column if not exists recruiter_name text,
add column if not exists recruiter_email text,
add column if not exists office_name text,
add column if not exists department_name text;

create table if not exists public.application_stage_events (
    event_id uuid primary key default gen_random_uuid(),
    application_id bigint references public.applications(application_id),
    previous_stage text,
    new_stage text not null,
    changed_by uuid references auth.users(id),
    changed_by_email text,
    changed_at timestamptz default now(),
    source text default 'supabase_admin_workflow',
    request_id uuid,
    metadata jsonb default '{}'::jsonb
);

create table if not exists public.stage_change_requests (
    request_id uuid primary key default gen_random_uuid(),
    requested_by uuid references auth.users(id),
    requested_by_email text,
    requested_at timestamptz default now(),
    target_stage text not null,
    next_stage text,
    selection_mode text,
    requested_limit integer,
    eligible_count integer,
    selected_count integer,
    reason text not null,
    status text not null default 'draft' check (
        status in (
            'draft',
            'dry_run',
            'approved',
            'applied',
            'partially_applied',
            'failed',
            'cancelled'
        )
    ),
    approved_by uuid references auth.users(id),
    approved_by_email text,
    approved_at timestamptz,
    applied_by uuid references auth.users(id),
    applied_by_email text,
    applied_at timestamptz,
    metadata jsonb default '{}'::jsonb
);

create table if not exists public.stage_change_request_items (
    request_id uuid references public.stage_change_requests(request_id) on delete cascade,
    application_id bigint references public.applications(application_id),
    previous_stage text,
    planned_stage_sequence text[],
    apply_status text default 'pending' check (
        apply_status in ('pending', 'applied', 'skipped', 'failed')
    ),
    error_message text,
    applied_at timestamptz,
    primary key (request_id, application_id)
);

create table if not exists public.admin_audit_logs (
    audit_id uuid primary key default gen_random_uuid(),
    user_id uuid references auth.users(id),
    email text,
    role text,
    action text not null,
    object_type text,
    object_id text,
    payload jsonb default '{}'::jsonb,
    created_at timestamptz default now()
);

create table if not exists public.application_status_events (
    event_id uuid primary key default gen_random_uuid(),
    application_id bigint references public.applications(application_id),
    previous_status text,
    new_status text not null,
    changed_by uuid references auth.users(id),
    changed_by_email text,
    changed_at timestamptz default now(),
    source text default 'supabase_admin_workflow',
    request_id uuid,
    metadata jsonb default '{}'::jsonb
);

create table if not exists public.outcome_change_requests (
    request_id uuid primary key default gen_random_uuid(),
    requested_by uuid references auth.users(id),
    requested_by_email text,
    requested_at timestamptz default now(),
    outcome text not null check (outcome in ('hired', 'rejected')),
    selection_mode text,
    requested_limit integer,
    eligible_count integer,
    selected_count integer,
    reason text not null,
    status text not null default 'dry_run' check (
        status in ('dry_run', 'approved', 'applied', 'partially_applied', 'failed', 'cancelled')
    ),
    approved_by uuid references auth.users(id),
    approved_by_email text,
    approved_at timestamptz,
    applied_by uuid references auth.users(id),
    applied_by_email text,
    applied_at timestamptz,
    metadata jsonb default '{}'::jsonb
);

alter table public.outcome_change_requests
drop constraint if exists outcome_change_requests_outcome_check;

alter table public.outcome_change_requests
add constraint outcome_change_requests_outcome_check
check (outcome in ('hired', 'rejected'));

create table if not exists public.outcome_change_request_items (
    request_id uuid references public.outcome_change_requests(request_id) on delete cascade,
    application_id bigint references public.applications(application_id),
    previous_status text,
    previous_stage text,
    planned_outcome text,
    apply_status text default 'pending' check (
        apply_status in ('pending', 'applied', 'skipped', 'failed')
    ),
    error_message text,
    applied_at timestamptz,
    primary key (request_id, application_id)
);

alter table public.profiles enable row level security;
alter table public.app_user_roles enable row level security;
alter table public.applications enable row level security;
alter table public.application_stage_events enable row level security;
alter table public.stage_change_requests enable row level security;
alter table public.stage_change_request_items enable row level security;
alter table public.admin_audit_logs enable row level security;
alter table public.application_status_events enable row level security;
alter table public.outcome_change_requests enable row level security;
alter table public.outcome_change_request_items enable row level security;

create or replace function public.has_app_role(role_name text)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
    select exists (
        select 1
        from public.app_user_roles
        where user_id = auth.uid()
          and role = role_name
          and is_active = true
    );
$$;

create or replace function public.current_user_role()
returns text
language sql
stable
security definer
set search_path = public
as $$
    select role
    from public.app_user_roles
    where user_id = auth.uid()
      and is_active = true
    order by case role
        when 'super_admin' then 1
        when 'dev_admin' then 2
        when 'hr_manager' then 3
        when 'business_manager' then 4
        when 'analyst_readonly' then 5
        else 99
    end
    limit 1;
$$;

create or replace function public.can_dry_run()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
    select public.has_app_role('super_admin')
        or public.has_app_role('dev_admin')
        or public.has_app_role('hr_manager')
        or public.has_app_role('business_manager');
$$;

create or replace function public.can_approve()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
    select public.has_app_role('super_admin')
        or public.has_app_role('dev_admin')
        or public.has_app_role('hr_manager')
        or public.has_app_role('business_manager');
$$;

create or replace function public.can_apply()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
    select public.has_app_role('super_admin')
        or public.has_app_role('dev_admin')
        or public.has_app_role('hr_manager')
        or public.has_app_role('business_manager');
$$;

drop policy if exists profiles_select_own on public.profiles;
create policy profiles_select_own
on public.profiles
for select
to authenticated
using (id = auth.uid() or public.has_app_role('super_admin') or public.has_app_role('dev_admin'));

drop policy if exists roles_select_own on public.app_user_roles;
create policy roles_select_own
on public.app_user_roles
for select
to authenticated
using (user_id = auth.uid() or public.has_app_role('super_admin') or public.has_app_role('dev_admin'));

drop policy if exists applications_read_authorized on public.applications;
create policy applications_read_authorized
on public.applications
for select
to authenticated
using (
    public.has_app_role('analyst_readonly')
    or public.has_app_role('business_manager')
    or public.has_app_role('hr_manager')
    or public.has_app_role('super_admin')
    or public.has_app_role('dev_admin')
);

drop policy if exists stage_events_read_authorized on public.application_stage_events;
create policy stage_events_read_authorized
on public.application_stage_events
for select
to authenticated
using (
    public.has_app_role('analyst_readonly')
    or public.has_app_role('business_manager')
    or public.has_app_role('hr_manager')
    or public.has_app_role('super_admin')
    or public.has_app_role('dev_admin')
);

drop policy if exists status_events_read_authorized on public.application_status_events;
create policy status_events_read_authorized
on public.application_status_events
for select
to authenticated
using (
    public.has_app_role('analyst_readonly')
    or public.has_app_role('business_manager')
    or public.has_app_role('hr_manager')
    or public.has_app_role('super_admin')
    or public.has_app_role('dev_admin')
);

drop policy if exists requests_read_authorized on public.stage_change_requests;
create policy requests_read_authorized
on public.stage_change_requests
for select
to authenticated
using (
    requested_by = auth.uid()
    or public.has_app_role('hr_manager')
    or public.has_app_role('business_manager')
    or public.has_app_role('super_admin')
    or public.has_app_role('dev_admin')
);

drop policy if exists outcome_requests_read_authorized on public.outcome_change_requests;
create policy outcome_requests_read_authorized
on public.outcome_change_requests
for select
to authenticated
using (
    requested_by = auth.uid()
    or public.has_app_role('hr_manager')
    or public.has_app_role('business_manager')
    or public.has_app_role('super_admin')
    or public.has_app_role('dev_admin')
);

drop policy if exists request_items_read_authorized on public.stage_change_request_items;
create policy request_items_read_authorized
on public.stage_change_request_items
for select
to authenticated
using (
    public.has_app_role('hr_manager')
    or public.has_app_role('business_manager')
    or public.has_app_role('super_admin')
    or public.has_app_role('dev_admin')
);

drop policy if exists outcome_request_items_read_authorized on public.outcome_change_request_items;
create policy outcome_request_items_read_authorized
on public.outcome_change_request_items
for select
to authenticated
using (
    public.has_app_role('hr_manager')
    or public.has_app_role('business_manager')
    or public.has_app_role('super_admin')
    or public.has_app_role('dev_admin')
);

drop policy if exists audit_logs_read_admin on public.admin_audit_logs;
create policy audit_logs_read_admin
on public.admin_audit_logs
for select
to authenticated
using (public.has_app_role('super_admin') or public.has_app_role('dev_admin'));

create or replace function public.allowed_recruitment_stage_rank(stage_name text)
returns integer
language sql
immutable
set search_path = public
as $$
    select case stage_name
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
        else null
    end;
$$;

create or replace function public.validate_recruitment_stage_sequence(stage_sequence text[])
returns void
language plpgsql
stable
security definer
set search_path = public
as $$
declare
    v_stage text;
    v_rank integer;
    v_previous_rank integer := 0;
begin
    if stage_sequence is null or array_length(stage_sequence, 1) is null then
        raise exception 'At least one recruitment stage is required';
    end if;

    foreach v_stage in array stage_sequence
    loop
        if v_stage in ('Hired', 'Rejected') then
            raise exception 'Hired and Rejected outcomes are excluded from this stage workflow';
        end if;

        v_rank := public.allowed_recruitment_stage_rank(v_stage);

        if v_rank is null then
            raise exception 'Invalid recruitment stage: %', v_stage;
        end if;

        if v_rank < v_previous_rank then
            raise exception 'Invalid backward recruitment stage transition: %', v_stage;
        end if;

        v_previous_rank := v_rank;
    end loop;
end;
$$;

drop function if exists public.create_stage_change_dry_run(text, text, text, integer, text);
drop function if exists public.create_stage_change_dry_run(text, text, text, integer, text, bigint[]);
drop function if exists public.create_stage_change_dry_run(text, text, integer, text, text, bigint[]);

create or replace function public.create_stage_change_dry_run(
    p_target_stage text,
    p_next_stage text default null,
    p_requested_limit integer default 100,
    p_selection_mode text default 'Focused group',
    p_reason text default null,
    p_application_ids bigint[] default null
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
    v_request_id uuid;
    v_sequence text[];
    v_final_stage text;
    v_eligible_count integer := 0;
    v_selected_count integer := 0;
begin
    if auth.uid() is null then
        raise exception 'Authentication required';
    end if;

    if not public.can_dry_run() then
        raise exception 'Insufficient role for dry-run';
    end if;

    if coalesce(trim(p_reason), '') = '' then
        raise exception 'Reason is required';
    end if;

    if nullif(p_next_stage, '') is not null and p_next_stage = p_target_stage then
        raise exception 'Target stage and next stage must be different.';
    end if;

    if p_selection_mode = 'Manual application selection'
        and coalesce(array_length(p_application_ids, 1), 0) = 0
    then
        raise exception 'Manual application selection requires at least one application_id';
    end if;

    v_sequence := case
        when nullif(p_next_stage, '') is null then array[p_target_stage]
        else array[p_target_stage, p_next_stage]
    end;
    perform public.validate_recruitment_stage_sequence(v_sequence);
    v_final_stage := v_sequence[array_length(v_sequence, 1)];

    if p_selection_mode = 'Manual application selection' then
        if exists (
            select 1
            from unnest(p_application_ids) as requested(application_id)
            left join public.applications as applications
              on applications.application_id = requested.application_id
            where applications.application_id is null
               or applications.status is distinct from 'active'
               or coalesce(applications.current_stage, '') is not distinct from coalesce(v_final_stage, '')
        ) then
            raise exception 'Manual application selection contains ineligible application IDs';
        end if;

        select count(distinct requested.application_id)
        into v_eligible_count
        from unnest(p_application_ids) as requested(application_id);
    else
        select count(*)
        into v_eligible_count
        from public.applications
        where status = 'active'
          and coalesce(current_stage, '') is distinct from coalesce(v_final_stage, '');
    end if;

    insert into public.stage_change_requests (
        requested_by,
        requested_by_email,
        target_stage,
        next_stage,
        selection_mode,
        requested_limit,
        eligible_count,
        selected_count,
        reason,
        status,
        metadata
    )
    values (
        auth.uid(),
        auth.jwt() ->> 'email',
        p_target_stage,
        p_next_stage,
        p_selection_mode,
        least(greatest(coalesce(p_requested_limit, 100), 10), 500),
        v_eligible_count,
        0,
        p_reason,
        'dry_run',
        jsonb_build_object('source', 'supabase_operational_source')
    )
    returning request_id into v_request_id;

    if p_selection_mode = 'Manual application selection' then
        insert into public.stage_change_request_items (
            request_id,
            application_id,
            previous_stage,
            planned_stage_sequence
        )
        select
            v_request_id,
            applications.application_id,
            applications.current_stage,
            v_sequence
        from public.applications as applications
        join (
            select distinct application_id
            from unnest(p_application_ids) as requested(application_id)
        ) as requested
          on applications.application_id = requested.application_id
        where applications.status = 'active'
          and coalesce(applications.current_stage, '') is distinct from coalesce(v_final_stage, '')
        order by applications.updated_at asc nulls last, applications.application_id
        limit least(greatest(coalesce(p_requested_limit, 100), 1), 500);
    elsif p_selection_mode = 'Global impact' then
        insert into public.stage_change_request_items (
            request_id,
            application_id,
            previous_stage,
            planned_stage_sequence
        )
        select
            v_request_id,
            application_id,
            current_stage,
            v_sequence
        from public.applications
        where status = 'active'
          and coalesce(current_stage, '') is distinct from coalesce(v_final_stage, '')
        order by updated_at desc, application_id
        limit least(greatest(coalesce(p_requested_limit, 100), 10), 500);
    else
        with eligible as (
            select
                *,
                count(*) over (partition by recruiter, office, department) as group_count
            from public.applications
            where status = 'active'
              and coalesce(current_stage, '') is distinct from coalesce(v_final_stage, '')
        ),
        selected_group as (
            select recruiter, office, department
            from eligible
            order by group_count desc nulls last, recruiter, office, department
            limit 1
        )
        insert into public.stage_change_request_items (
            request_id,
            application_id,
            previous_stage,
            planned_stage_sequence
        )
        select
            v_request_id,
            e.application_id,
            e.current_stage,
            v_sequence
        from eligible e
        join selected_group g
          on coalesce(e.recruiter, '') = coalesce(g.recruiter, '')
         and coalesce(e.office, '') = coalesce(g.office, '')
         and coalesce(e.department, '') = coalesce(g.department, '')
        order by e.updated_at desc, e.application_id
        limit least(greatest(coalesce(p_requested_limit, 100), 10), 500);
    end if;

    select count(*)
    into v_selected_count
    from public.stage_change_request_items
    where request_id = v_request_id;

    update public.stage_change_requests
    set selected_count = v_selected_count
    where request_id = v_request_id;

    insert into public.admin_audit_logs (
        user_id,
        email,
        role,
        action,
        object_type,
        object_id,
        payload
    )
    values (
        auth.uid(),
        auth.jwt() ->> 'email',
        public.current_user_role(),
        'create_stage_change_dry_run',
        'stage_change_request',
        v_request_id::text,
        jsonb_build_object('selected_count', v_selected_count)
    );

    return v_request_id;
end;
$$;

select pg_notify('pgrst', 'reload schema');

grant usage on schema public to service_role;

grant select, insert, update
on public.applications
to service_role;

grant select, insert
on public.application_stage_events
to service_role;

grant select
on public.profiles,
   public.app_user_roles,
   public.stage_change_requests,
   public.stage_change_request_items,
   public.admin_audit_logs
to service_role;

create or replace function public.approve_stage_change_request(p_request_id uuid)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
begin
    if auth.uid() is null then
        raise exception 'Authentication required';
    end if;

    if not public.can_approve() then
        raise exception 'Insufficient role for approval';
    end if;

    update public.stage_change_requests
    set
        status = 'approved',
        approved_by = auth.uid(),
        approved_by_email = auth.jwt() ->> 'email',
        approved_at = now()
    where request_id = p_request_id
      and status = 'dry_run';

    if not found then
        raise exception 'Request must exist and be in dry_run status';
    end if;

    insert into public.admin_audit_logs (
        user_id,
        email,
        role,
        action,
        object_type,
        object_id
    )
    values (
        auth.uid(),
        auth.jwt() ->> 'email',
        public.current_user_role(),
        'approve_stage_change_request',
        'stage_change_request',
        p_request_id::text
    );

    return p_request_id;
end;
$$;

create or replace function public.apply_stage_change_request(p_request_id uuid)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
    v_item record;
    v_stage text;
    v_previous_stage text;
    v_applied_count integer := 0;
    v_failed_count integer := 0;
begin
    if auth.uid() is null then
        raise exception 'Authentication required';
    end if;

    if not public.can_apply() then
        raise exception 'Insufficient role for apply';
    end if;

    if not exists (
        select 1
        from public.stage_change_requests
        where request_id = p_request_id
          and status = 'approved'
    ) then
        raise exception 'Request must be approved before apply';
    end if;

    for v_item in
        select *
        from public.stage_change_request_items
        where request_id = p_request_id
          and apply_status in ('pending', 'failed')
        order by application_id
    loop
        begin
            perform public.validate_recruitment_stage_sequence(v_item.planned_stage_sequence);
            v_previous_stage := v_item.previous_stage;

            foreach v_stage in array v_item.planned_stage_sequence
            loop
                insert into public.application_stage_events (
                    application_id,
                    previous_stage,
                    new_stage,
                    changed_by,
                    changed_by_email,
                    request_id,
                    metadata
                )
                values (
                    v_item.application_id,
                    v_previous_stage,
                    v_stage,
                    auth.uid(),
                    auth.jwt() ->> 'email',
                    p_request_id,
                    jsonb_build_object('idempotency_key', p_request_id::text || ':' || v_item.application_id::text || ':' || v_stage)
                );

                update public.applications
                set
                    current_stage = v_stage,
                    updated_at = now()
                where application_id = v_item.application_id;

                v_previous_stage := v_stage;
            end loop;

            update public.stage_change_request_items
            set
                apply_status = 'applied',
                applied_at = now(),
                error_message = null
            where request_id = p_request_id
              and application_id = v_item.application_id;

            v_applied_count := v_applied_count + 1;
        exception when others then
            update public.stage_change_request_items
            set
                apply_status = 'failed',
                error_message = sqlerrm
            where request_id = p_request_id
              and application_id = v_item.application_id;

            v_failed_count := v_failed_count + 1;
        end;
    end loop;

    update public.stage_change_requests
    set
        status = case
            when v_failed_count = 0 then 'applied'
            when v_applied_count > 0 then 'partially_applied'
            else 'failed'
        end,
        applied_by = auth.uid(),
        applied_by_email = auth.jwt() ->> 'email',
        applied_at = now(),
        metadata = coalesce(metadata, '{}'::jsonb) || jsonb_build_object(
            'applied_count', v_applied_count,
            'failed_count', v_failed_count
        )
    where request_id = p_request_id;

    insert into public.admin_audit_logs (
        user_id,
        email,
        role,
        action,
        object_type,
        object_id,
        payload
    )
    values (
        auth.uid(),
        auth.jwt() ->> 'email',
        public.current_user_role(),
        'apply_stage_change_request',
        'stage_change_request',
        p_request_id::text,
        jsonb_build_object('applied_count', v_applied_count, 'failed_count', v_failed_count)
    );

    return p_request_id;
end;
$$;

create or replace function public.create_hiring_outcome_dry_run(
    p_selection_mode text default 'Offer only',
    p_requested_limit integer default 10,
    p_reason text default null,
    p_application_ids bigint[] default null
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
    v_request_id uuid;
    v_eligible_count integer := 0;
    v_selected_count integer := 0;
    v_limit integer;
begin
    if auth.uid() is null then
        raise exception 'Authentication required';
    end if;

    if not public.can_dry_run() then
        raise exception 'Insufficient role for hiring outcome dry-run';
    end if;

    if coalesce(trim(p_reason), '') = '' then
        raise exception 'Reason is required';
    end if;

    if p_selection_mode not in (
        'Offer only',
        'Late-stage candidates',
        'Manual candidate selection'
    ) then
        raise exception 'Invalid hiring outcome selection mode: %', p_selection_mode;
    end if;

    if p_selection_mode = 'Manual candidate selection'
        and coalesce(array_length(p_application_ids, 1), 0) = 0
    then
        raise exception 'Manual candidate selection requires at least one application_id';
    end if;

    v_limit := least(greatest(coalesce(p_requested_limit, 10), 1), 100);

    if p_selection_mode = 'Manual candidate selection' then
        if exists (
            select 1
            from unnest(p_application_ids) as requested(application_id)
            left join public.applications as applications
              on applications.application_id = requested.application_id
            where applications.application_id is null
               or applications.status is distinct from 'active'
               or applications.status in ('hired', 'rejected')
               or applications.current_stage not in (
                    'Offer',
                    'Reference Check',
                    'Final Interview',
                    'Final (Executive) Interview'
               )
        ) then
            raise exception 'Manual candidate selection contains ineligible application IDs';
        end if;

        select count(distinct requested.application_id)
        into v_eligible_count
        from unnest(p_application_ids) as requested(application_id);
    else
        select count(*)
        into v_eligible_count
        from public.applications
        where status = 'active'
          and status not in ('hired', 'rejected')
          and (
            (p_selection_mode = 'Offer only' and current_stage = 'Offer')
            or (
                p_selection_mode = 'Late-stage candidates'
                and current_stage in (
                    'Offer',
                    'Reference Check',
                    'Final Interview',
                    'Final (Executive) Interview'
                )
            )
          );
    end if;

    insert into public.outcome_change_requests (
        requested_by,
        requested_by_email,
        outcome,
        selection_mode,
        requested_limit,
        eligible_count,
        selected_count,
        reason,
        status,
        metadata
    )
    values (
        auth.uid(),
        auth.jwt() ->> 'email',
        'hired',
        p_selection_mode,
        v_limit,
        v_eligible_count,
        0,
        p_reason,
        'dry_run',
        jsonb_build_object('source', 'supabase_hiring_outcome_workflow')
    )
    returning request_id into v_request_id;

    if p_selection_mode = 'Manual candidate selection' then
        insert into public.outcome_change_request_items (
            request_id,
            application_id,
            previous_status,
            previous_stage,
            planned_outcome
        )
        select
            v_request_id,
            applications.application_id,
            applications.status,
            applications.current_stage,
            'hired'
        from public.applications as applications
        join (
            select distinct application_id
            from unnest(p_application_ids) as requested(application_id)
        ) as requested
          on applications.application_id = requested.application_id
        where applications.status = 'active'
          and applications.status not in ('hired', 'rejected')
          and applications.current_stage in (
                'Offer',
                'Reference Check',
                'Final Interview',
                'Final (Executive) Interview'
          )
        order by
            applications.application_id
        limit v_limit;
    else
        insert into public.outcome_change_request_items (
        request_id,
        application_id,
        previous_status,
        previous_stage,
        planned_outcome
        )
        select
            v_request_id,
            application_id,
            status,
            current_stage,
            'hired'
        from public.applications
        where status = 'active'
          and status not in ('hired', 'rejected')
          and (
            (p_selection_mode = 'Offer only' and current_stage = 'Offer')
            or (
                p_selection_mode = 'Late-stage candidates'
                and current_stage in (
                    'Offer',
                    'Reference Check',
                    'Final Interview',
                    'Final (Executive) Interview'
                )
            )
          )
        order by
            case current_stage
                when 'Offer' then 4
                when 'Reference Check' then 3
                when 'Final (Executive) Interview' then 2
                when 'Final Interview' then 1
                else 0
            end desc,
            updated_at asc nulls last,
            application_id
        limit v_limit;
    end if;

    select count(*)
    into v_selected_count
    from public.outcome_change_request_items
    where request_id = v_request_id;

    update public.outcome_change_requests
    set selected_count = v_selected_count
    where request_id = v_request_id;

    insert into public.admin_audit_logs (
        user_id,
        email,
        role,
        action,
        object_type,
        object_id,
        payload
    )
    values (
        auth.uid(),
        auth.jwt() ->> 'email',
        public.current_user_role(),
        'create_hiring_outcome_dry_run',
        'outcome_change_request',
        v_request_id::text,
        jsonb_build_object('selected_count', v_selected_count, 'outcome', 'hired')
    );

    return v_request_id;
end;
$$;

create or replace function public.create_rejection_outcome_dry_run(
    p_selection_mode text default 'Reference Check only',
    p_requested_limit integer default 1,
    p_reason text default null,
    p_application_ids bigint[] default null
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
    v_request_id uuid;
    v_eligible_count integer := 0;
    v_selected_count integer := 0;
    v_limit integer;
begin
    if auth.uid() is null then
        raise exception 'Authentication required';
    end if;

    if not public.can_dry_run() then
        raise exception 'Insufficient role for rejection outcome dry-run';
    end if;

    if coalesce(trim(p_reason), '') = '' then
        raise exception 'Reason is required';
    end if;

    if p_selection_mode not in (
        'Early process rejection',
        'Reference Check only',
        'Late-stage rejection',
        'Manual candidate selection'
    ) then
        raise exception 'Invalid rejection outcome selection mode: %', p_selection_mode;
    end if;

    if p_selection_mode = 'Manual candidate selection'
        and coalesce(array_length(p_application_ids, 1), 0) = 0
    then
        raise exception 'Manual candidate selection requires at least one application_id';
    end if;

    v_limit := least(greatest(coalesce(p_requested_limit, 1), 1), 100);

    if p_selection_mode = 'Manual candidate selection' then
        if exists (
            select 1
            from unnest(p_application_ids) as requested(application_id)
            left join public.applications as applications
              on applications.application_id = requested.application_id
            where applications.application_id is null
               or applications.status is distinct from 'active'
               or applications.status in ('hired', 'rejected')
               or applications.current_stage not in (
                    'Application Review',
                    'Recruiter Interview',
                    'Hiring Manager Review',
                    'Hiring Manager Interview',
                    'Take Home Test',
                    'Face to Face',
                    'HR Interview',
                    'Final Interview',
                    'Final (Executive) Interview',
                    'Reference Check',
                    'Offer'
               )
        ) then
            raise exception 'Manual candidate selection contains ineligible application IDs';
        end if;

        select count(distinct requested.application_id)
        into v_eligible_count
        from unnest(p_application_ids) as requested(application_id);
    else
        select count(*)
        into v_eligible_count
        from public.applications
        where status = 'active'
          and status not in ('hired', 'rejected')
          and (
            (
                p_selection_mode = 'Early process rejection'
                and current_stage in ('Application Review', 'Recruiter Interview')
            )
            or (
                p_selection_mode = 'Reference Check only'
                and current_stage = 'Reference Check'
            )
            or (
                p_selection_mode = 'Late-stage rejection'
                and current_stage in (
                    'Final Interview',
                    'Final (Executive) Interview',
                    'Reference Check',
                    'Offer'
                )
            )
          );
    end if;

    insert into public.outcome_change_requests (
        requested_by,
        requested_by_email,
        outcome,
        selection_mode,
        requested_limit,
        eligible_count,
        selected_count,
        reason,
        status,
        metadata
    )
    values (
        auth.uid(),
        auth.jwt() ->> 'email',
        'rejected',
        p_selection_mode,
        v_limit,
        v_eligible_count,
        0,
        p_reason,
        'dry_run',
        jsonb_build_object('source', 'supabase_rejection_outcome_workflow')
    )
    returning request_id into v_request_id;

    if p_selection_mode = 'Manual candidate selection' then
        insert into public.outcome_change_request_items (
            request_id,
            application_id,
            previous_status,
            previous_stage,
            planned_outcome
        )
        select
            v_request_id,
            applications.application_id,
            applications.status,
            applications.current_stage,
            'rejected'
        from public.applications as applications
        join (
            select distinct application_id
            from unnest(p_application_ids) as requested(application_id)
        ) as requested
          on applications.application_id = requested.application_id
        order by applications.application_id
        limit v_limit;
    else
        insert into public.outcome_change_request_items (
            request_id,
            application_id,
            previous_status,
            previous_stage,
            planned_outcome
        )
        select
            v_request_id,
            application_id,
            status,
            current_stage,
            'rejected'
        from public.applications
        where status = 'active'
          and status not in ('hired', 'rejected')
          and (
            (
                p_selection_mode = 'Early process rejection'
                and current_stage in ('Application Review', 'Recruiter Interview')
            )
            or (
                p_selection_mode = 'Reference Check only'
                and current_stage = 'Reference Check'
            )
            or (
                p_selection_mode = 'Late-stage rejection'
                and current_stage in (
                    'Final Interview',
                    'Final (Executive) Interview',
                    'Reference Check',
                    'Offer'
                )
            )
          )
        order by
            case current_stage
                when 'Offer' then 4
                when 'Reference Check' then 3
                when 'Final (Executive) Interview' then 2
                when 'Final Interview' then 1
                else 0
            end desc,
            updated_at asc nulls last,
            application_id
        limit v_limit;
    end if;

    select count(*)
    into v_selected_count
    from public.outcome_change_request_items
    where request_id = v_request_id;

    update public.outcome_change_requests
    set selected_count = v_selected_count
    where request_id = v_request_id;

    insert into public.admin_audit_logs (
        user_id,
        email,
        role,
        action,
        object_type,
        object_id,
        payload
    )
    values (
        auth.uid(),
        auth.jwt() ->> 'email',
        public.current_user_role(),
        'create_rejection_outcome_dry_run',
        'outcome_change_request',
        v_request_id::text,
        jsonb_build_object('selected_count', v_selected_count, 'outcome', 'rejected')
    );

    return v_request_id;
end;
$$;

create or replace function public.create_hiring_outcome_dry_run(
    p_selection_mode text default 'Offer only',
    p_requested_limit integer default 10,
    p_reason text default null
)
returns uuid
language sql
security definer
set search_path = public
as $$
    select public.create_hiring_outcome_dry_run(
        p_selection_mode,
        p_requested_limit,
        p_reason,
        null::bigint[]
    );
$$;

create or replace function public.create_rejection_outcome_dry_run(
    p_selection_mode text default 'Reference Check only',
    p_requested_limit integer default 1,
    p_reason text default null
)
returns uuid
language sql
security definer
set search_path = public
as $$
    select public.create_rejection_outcome_dry_run(
        p_selection_mode,
        p_requested_limit,
        p_reason,
        null::bigint[]
    );
$$;

create or replace function public.approve_hiring_outcome_request(p_request_id uuid)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
begin
    if auth.uid() is null then
        raise exception 'Authentication required';
    end if;

    if not public.can_approve() then
        raise exception 'Insufficient role for hiring outcome approval';
    end if;

    update public.outcome_change_requests
    set
        status = 'approved',
        approved_by = auth.uid(),
        approved_by_email = auth.jwt() ->> 'email',
        approved_at = now()
    where request_id = p_request_id
      and status = 'dry_run'
      and outcome = 'hired';

    if not found then
        raise exception 'Hiring outcome request must exist and be in dry_run status';
    end if;

    insert into public.admin_audit_logs (
        user_id,
        email,
        role,
        action,
        object_type,
        object_id
    )
    values (
        auth.uid(),
        auth.jwt() ->> 'email',
        public.current_user_role(),
        'approve_hiring_outcome_request',
        'outcome_change_request',
        p_request_id::text
    );

    return p_request_id;
end;
$$;

create or replace function public.approve_rejection_outcome_request(p_request_id uuid)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
begin
    if auth.uid() is null then
        raise exception 'Authentication required';
    end if;

    if not public.can_approve() then
        raise exception 'Insufficient role for rejection outcome approval';
    end if;

    update public.outcome_change_requests
    set
        status = 'approved',
        approved_by = auth.uid(),
        approved_by_email = auth.jwt() ->> 'email',
        approved_at = now()
    where request_id = p_request_id
      and status = 'dry_run'
      and outcome = 'rejected';

    if not found then
        raise exception 'Rejection outcome request must exist and be in dry_run status';
    end if;

    insert into public.admin_audit_logs (
        user_id,
        email,
        role,
        action,
        object_type,
        object_id
    )
    values (
        auth.uid(),
        auth.jwt() ->> 'email',
        public.current_user_role(),
        'approve_rejection_outcome_request',
        'outcome_change_request',
        p_request_id::text
    );

    return p_request_id;
end;
$$;

create or replace function public.apply_hiring_outcome_request(p_request_id uuid)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
    v_item record;
    v_applied_count integer := 0;
    v_skipped_count integer := 0;
    v_failed_count integer := 0;
begin
    if auth.uid() is null then
        raise exception 'Authentication required';
    end if;

    if not public.can_apply() then
        raise exception 'Insufficient role for hiring outcome apply';
    end if;

    if not exists (
        select 1
        from public.outcome_change_requests
        where request_id = p_request_id
          and status = 'approved'
          and outcome = 'hired'
    ) then
        raise exception 'Hiring outcome request must be approved before apply';
    end if;

    for v_item in
        select
            items.*,
            applications.status as current_application_status,
            applications.current_stage as current_application_stage
        from public.outcome_change_request_items as items
        left join public.applications as applications
          on items.application_id = applications.application_id
        where items.request_id = p_request_id
          and items.apply_status in ('pending', 'failed')
        order by items.application_id
    loop
        begin
            if v_item.current_application_status is distinct from 'active'
                or v_item.current_application_stage not in (
                    'Offer',
                    'Reference Check',
                    'Final Interview',
                    'Final (Executive) Interview'
                )
            then
                update public.outcome_change_request_items
                set
                    apply_status = 'skipped',
                    error_message = 'Application is no longer eligible for hiring outcome',
                    applied_at = now()
                where request_id = p_request_id
                  and application_id = v_item.application_id;

                v_skipped_count := v_skipped_count + 1;
                continue;
            end if;

            update public.applications
            set
                status = 'hired',
                current_stage = 'Offer',
                hired_at = now(),
                updated_at = now()
            where application_id = v_item.application_id
              and status = 'active'
              and current_stage in (
                  'Offer',
                  'Reference Check',
                  'Final Interview',
                  'Final (Executive) Interview'
              );

            if not found then
                update public.outcome_change_request_items
                set
                    apply_status = 'skipped',
                    error_message = 'Application is no longer eligible for hiring outcome',
                    applied_at = now()
                where request_id = p_request_id
                  and application_id = v_item.application_id;

                v_skipped_count := v_skipped_count + 1;
            else
                insert into public.application_status_events (
                    application_id,
                    previous_status,
                    new_status,
                    changed_by,
                    changed_by_email,
                    request_id,
                    metadata
                )
                values (
                    v_item.application_id,
                    v_item.previous_status,
                    'hired',
                    auth.uid(),
                    auth.jwt() ->> 'email',
                    p_request_id,
                    jsonb_build_object(
                        'previous_stage', v_item.previous_stage,
                        'new_stage', 'Offer',
                        'workflow', 'hiring_outcome'
                    )
                );

                insert into public.application_stage_events (
                    application_id,
                    previous_stage,
                    new_stage,
                    changed_by,
                    changed_by_email,
                    request_id,
                    metadata
                )
                values (
                    v_item.application_id,
                    v_item.previous_stage,
                    'Offer',
                    auth.uid(),
                    auth.jwt() ->> 'email',
                    p_request_id,
                    jsonb_build_object('workflow', 'hiring_outcome')
                );

                update public.outcome_change_request_items
                set
                    apply_status = 'applied',
                    applied_at = now(),
                    error_message = null
                where request_id = p_request_id
                  and application_id = v_item.application_id;

                v_applied_count := v_applied_count + 1;
            end if;
        exception when others then
            update public.outcome_change_request_items
            set
                apply_status = 'failed',
                error_message = sqlerrm
            where request_id = p_request_id
              and application_id = v_item.application_id;

            v_failed_count := v_failed_count + 1;
        end;
    end loop;

    update public.outcome_change_requests
    set
        status = case
            when v_failed_count = 0 and v_skipped_count = 0 then 'applied'
            when v_applied_count > 0 then 'partially_applied'
            else 'failed'
        end,
        applied_by = auth.uid(),
        applied_by_email = auth.jwt() ->> 'email',
        applied_at = now(),
        metadata = coalesce(metadata, '{}'::jsonb) || jsonb_build_object(
            'applied_count', v_applied_count,
            'skipped_count', v_skipped_count,
            'failed_count', v_failed_count
        )
    where request_id = p_request_id;

    insert into public.admin_audit_logs (
        user_id,
        email,
        role,
        action,
        object_type,
        object_id,
        payload
    )
    values (
        auth.uid(),
        auth.jwt() ->> 'email',
        public.current_user_role(),
        'apply_hiring_outcome_request',
        'outcome_change_request',
        p_request_id::text,
        jsonb_build_object(
            'applied_count', v_applied_count,
            'skipped_count', v_skipped_count,
            'failed_count', v_failed_count
        )
    );

    return p_request_id;
end;
$$;

create or replace function public.apply_rejection_outcome_request(p_request_id uuid)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
    v_item record;
    v_request record;
    v_applied_count integer := 0;
    v_skipped_count integer := 0;
    v_failed_count integer := 0;
begin
    if auth.uid() is null then
        raise exception 'Authentication required';
    end if;

    if not public.can_apply() then
        raise exception 'Insufficient role for rejection outcome apply';
    end if;

    select *
    into v_request
    from public.outcome_change_requests
    where request_id = p_request_id
      and status = 'approved'
      and outcome = 'rejected';

    if not found then
        raise exception 'Rejection outcome request must be approved before apply';
    end if;

    for v_item in
        select
            items.*,
            applications.status as current_application_status,
            applications.current_stage as current_application_stage
        from public.outcome_change_request_items as items
        left join public.applications as applications
          on items.application_id = applications.application_id
        where items.request_id = p_request_id
          and items.apply_status in ('pending', 'failed')
        order by items.application_id
    loop
        begin
            if v_item.current_application_status is distinct from 'active'
                or v_item.current_application_stage not in (
                    'Application Review',
                    'Recruiter Interview',
                    'Hiring Manager Review',
                    'Hiring Manager Interview',
                    'Take Home Test',
                    'Face to Face',
                    'HR Interview',
                    'Final Interview',
                    'Final (Executive) Interview',
                    'Reference Check',
                    'Offer'
                )
            then
                update public.outcome_change_request_items
                set
                    apply_status = 'skipped',
                    error_message = 'Application is no longer eligible for rejection outcome',
                    applied_at = now()
                where request_id = p_request_id
                  and application_id = v_item.application_id;

                v_skipped_count := v_skipped_count + 1;
                continue;
            end if;

            update public.applications
            set
                status = 'rejected',
                updated_at = now()
            where application_id = v_item.application_id
              and status = 'active';

            if not found then
                update public.outcome_change_request_items
                set
                    apply_status = 'skipped',
                    error_message = 'Application is no longer eligible for rejection outcome',
                    applied_at = now()
                where request_id = p_request_id
                  and application_id = v_item.application_id;

                v_skipped_count := v_skipped_count + 1;
            else
                insert into public.application_status_events (
                    application_id,
                    previous_status,
                    new_status,
                    changed_by,
                    changed_by_email,
                    request_id,
                    metadata
                )
                values (
                    v_item.application_id,
                    v_item.previous_status,
                    'rejected',
                    auth.uid(),
                    auth.jwt() ->> 'email',
                    p_request_id,
                    jsonb_build_object(
                        'previous_stage', v_item.previous_stage,
                        'workflow', 'rejection_outcome',
                        'rejection_reason', v_request.reason,
                        'selection_mode', v_request.selection_mode
                    )
                );

                update public.outcome_change_request_items
                set
                    apply_status = 'applied',
                    applied_at = now(),
                    error_message = null
                where request_id = p_request_id
                  and application_id = v_item.application_id;

                v_applied_count := v_applied_count + 1;
            end if;
        exception when others then
            update public.outcome_change_request_items
            set
                apply_status = 'failed',
                error_message = sqlerrm
            where request_id = p_request_id
              and application_id = v_item.application_id;

            v_failed_count := v_failed_count + 1;
        end;
    end loop;

    update public.outcome_change_requests
    set
        status = case
            when v_failed_count = 0 and v_skipped_count = 0 then 'applied'
            when v_applied_count > 0 then 'partially_applied'
            else 'failed'
        end,
        applied_by = auth.uid(),
        applied_by_email = auth.jwt() ->> 'email',
        applied_at = now(),
        metadata = coalesce(metadata, '{}'::jsonb) || jsonb_build_object(
            'applied_count', v_applied_count,
            'skipped_count', v_skipped_count,
            'failed_count', v_failed_count
        )
    where request_id = p_request_id;

    insert into public.admin_audit_logs (
        user_id,
        email,
        role,
        action,
        object_type,
        object_id,
        payload
    )
    values (
        auth.uid(),
        auth.jwt() ->> 'email',
        public.current_user_role(),
        'apply_rejection_outcome_request',
        'outcome_change_request',
        p_request_id::text,
        jsonb_build_object(
            'applied_count', v_applied_count,
            'skipped_count', v_skipped_count,
            'failed_count', v_failed_count
        )
    );

    return p_request_id;
end;
$$;

grant select
on public.application_status_events,
   public.outcome_change_requests,
   public.outcome_change_request_items
to authenticated;

grant execute on function public.create_stage_change_dry_run(text, text, integer, text, text, bigint[])
to authenticated;

grant execute on function public.approve_stage_change_request(uuid)
to authenticated;

grant execute on function public.apply_stage_change_request(uuid)
to authenticated;

grant execute on function public.create_hiring_outcome_dry_run(text, integer, text)
to authenticated;

grant execute on function public.create_hiring_outcome_dry_run(text, integer, text, bigint[])
to authenticated;

grant execute on function public.approve_hiring_outcome_request(uuid)
to authenticated;

grant execute on function public.apply_hiring_outcome_request(uuid)
to authenticated;

grant execute on function public.create_rejection_outcome_dry_run(text, integer, text, bigint[])
to authenticated;

grant execute on function public.create_rejection_outcome_dry_run(text, integer, text)
to authenticated;

grant execute on function public.approve_rejection_outcome_request(uuid)
to authenticated;

grant execute on function public.apply_rejection_outcome_request(uuid)
to authenticated;

grant select, insert, update
on public.application_status_events,
   public.outcome_change_requests,
   public.outcome_change_request_items
to service_role;
