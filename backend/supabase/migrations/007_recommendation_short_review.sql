-- Run after 006_youtube_quota_usage.sql.
-- The review is generated from public YouTube metadata, not from the full video transcript.

alter table public.recommendations
    add column if not exists short_review text;
