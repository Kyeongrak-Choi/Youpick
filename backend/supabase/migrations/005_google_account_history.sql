-- Run after 004_allow_unlimited_viewing_time.sql.
-- Google OIDC's stable `sub` claim is used as the per-account identifier.

create table if not exists public.conversations (
    id uuid primary key default gen_random_uuid(),
    user_id text not null,
    user_email text,
    title text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.search_requests
    add column if not exists user_id text,
    add column if not exists conversation_id uuid references public.conversations(id) on delete cascade;

create index if not exists conversations_user_updated_idx
    on public.conversations(user_id, updated_at desc);
create index if not exists search_requests_user_created_idx
    on public.search_requests(user_id, created_at desc);
create index if not exists search_requests_conversation_idx
    on public.search_requests(conversation_id, created_at);

alter table public.conversations enable row level security;
