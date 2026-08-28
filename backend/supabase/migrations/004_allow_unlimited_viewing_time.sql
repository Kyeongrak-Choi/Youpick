-- Run after 001_initial_schema.sql. NULL means the user selected "제한 없음".

alter table public.search_requests
    alter column max_duration_minutes drop not null;

alter table public.search_requests
    drop constraint if exists search_requests_max_duration_minutes_check;

alter table public.search_requests
    add constraint search_requests_max_duration_minutes_check
    check (max_duration_minutes is null or max_duration_minutes between 1 and 240);
