-- Run after 005_google_account_history.sql.
-- YouTube quota is shared by the Google Cloud project, not by individual users.

create table if not exists public.youtube_api_quota_daily (
    quota_day date primary key,
    used_units integer not null default 0 check (used_units >= 0),
    updated_at timestamptz not null default now()
);

create or replace function public.increment_youtube_api_quota(
    usage_day date,
    added_units integer
)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
    current_used integer;
begin
    if added_units <= 0 then
        raise exception 'added_units must be positive';
    end if;

    insert into public.youtube_api_quota_daily (quota_day, used_units)
    values (usage_day, added_units)
    on conflict (quota_day) do update
        set used_units = public.youtube_api_quota_daily.used_units + excluded.used_units,
            updated_at = now()
    returning used_units into current_used;

    return current_used;
end;
$$;

alter table public.youtube_api_quota_daily enable row level security;
revoke all on table public.youtube_api_quota_daily from anon, authenticated;
revoke all on function public.increment_youtube_api_quota(date, integer) from public;
grant execute on function public.increment_youtube_api_quota(date, integer) to service_role;
