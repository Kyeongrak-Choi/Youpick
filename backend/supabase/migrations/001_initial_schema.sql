-- Run this once in Supabase Dashboard → SQL Editor.
-- Stores anonymous recommendation requests and their generated results.

create table if not exists public.search_requests (
    id uuid primary key default gen_random_uuid(),
    category text not null,
    detail_request text not null,
    max_duration_minutes integer not null check (max_duration_minutes between 1 and 240),
    purpose text not null check (purpose in ('summary', 'concept', 'deep_dive', 'practice')),
    candidate_count integer not null default 0,
    filtered_count integer not null default 0,
    cached boolean not null default false,
    created_at timestamptz not null default now()
);

create table if not exists public.recommendations (
    id uuid primary key default gen_random_uuid(),
    search_request_id uuid not null references public.search_requests(id) on delete cascade,
    video_id text not null,
    title text not null,
    channel_name text not null,
    thumbnail_url text not null,
    duration_seconds integer not null,
    published_at timestamptz not null,
    view_count bigint,
    tags jsonb not null default '[]'::jsonb,
    relevance_score numeric(5, 1) not null,
    recommendation_reason text not null,
    rank integer not null check (rank > 0),
    created_at timestamptz not null default now(),
    unique (search_request_id, rank)
);

create index if not exists recommendations_video_id_idx on public.recommendations(video_id);
create index if not exists search_requests_created_at_idx on public.search_requests(created_at desc);

-- Do not grant public access. The backend uses the service-role key only.
alter table public.search_requests enable row level security;
alter table public.recommendations enable row level security;
