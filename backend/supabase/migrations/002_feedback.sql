-- Run this after 001_initial_schema.sql in Supabase Dashboard → SQL Editor.

create table if not exists public.feedback (
    id uuid primary key default gen_random_uuid(),
    recommendation_id uuid not null references public.recommendations(id) on delete cascade,
    is_helpful boolean not null,
    comment text check (char_length(comment) <= 500),
    created_at timestamptz not null default now()
);

create index if not exists feedback_recommendation_id_idx
    on public.feedback(recommendation_id);

alter table public.feedback enable row level security;
