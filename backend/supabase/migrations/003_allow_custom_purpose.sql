-- Run after 001_initial_schema.sql. Allows users to describe their own viewing purpose.

alter table public.search_requests
    drop constraint if exists search_requests_purpose_check;
