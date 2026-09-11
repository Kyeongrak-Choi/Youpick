-- Run after 007_recommendation_short_review.sql.
-- Returns project-wide operational metrics for the internal dashboard.

create or replace function public.get_youpick_dashboard()
returns jsonb
language sql
security definer
set search_path = public
as $$
    with feedback_stats as (
        select count(*)::integer as total, count(*) filter (where is_helpful)::integer as helpful
        from public.feedback
    ),
    cache_stats as (
        select count(*) filter (where cached)::integer as hits, count(*)::integer as total
        from public.search_requests
    )
    select jsonb_build_object(
        'total_requests', (select count(*)::integer from public.search_requests),
        'total_recommendations', (select count(*)::integer from public.recommendations),
        'feedback_total', (select total from feedback_stats),
        'helpful_total', (select helpful from feedback_stats),
        'helpful_rate', coalesce(round((select helpful::numeric / nullif(total, 0) * 100 from feedback_stats), 1), 0),
        'cache_hits', (select hits from cache_stats),
        'cache_hit_rate', coalesce(round((select hits::numeric / nullif(total, 0) * 100 from cache_stats), 1), 0),
        'popular_categories', coalesce((
            select jsonb_agg(jsonb_build_object('label', category, 'count', request_count) order by request_count desc)
            from (
                select category, count(*)::integer as request_count
                from public.search_requests group by category order by request_count desc limit 5
            ) ranked_categories
        ), '[]'::jsonb),
        'popular_purposes', coalesce((
            select jsonb_agg(jsonb_build_object('label', purpose, 'count', request_count) order by request_count desc)
            from (
                select purpose, count(*)::integer as request_count
                from public.search_requests group by purpose order by request_count desc limit 5
            ) ranked_purposes
        ), '[]'::jsonb),
        'daily_requests', coalesce((
            select jsonb_agg(jsonb_build_object('date', request_day, 'count', request_count) order by request_day)
            from (
                select created_at::date::text as request_day, count(*)::integer as request_count
                from public.search_requests
                where created_at >= now() - interval '6 days'
                group by created_at::date order by created_at::date
            ) recent_days
        ), '[]'::jsonb)
    );
$$;

revoke all on function public.get_youpick_dashboard() from public;
grant execute on function public.get_youpick_dashboard() to service_role;
