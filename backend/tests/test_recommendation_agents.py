from datetime import UTC, datetime

from app.agents.recommendation import AnalysisAgent, FilterAgent, RankingAgent, temporal_window, youtube_search_query
from app.schemas import RecommendationRequest, ViewingPurpose
from app.services.youtube import YouTubeVideo, parse_iso8601_duration


def video(video_id: str, duration: int, title: str = "FastAPI Supabase tutorial") -> YouTubeVideo:
    return YouTubeVideo(video_id, title, "FastAPI Supabase login guide", "Test Channel",
        "https://example.com/image.jpg", duration, datetime(2026, 1, 1, tzinfo=UTC), 100, ["fastapi", "supabase"])


def test_duration_parser() -> None:
    assert parse_iso8601_duration("PT1H2M3S") == 3723
    assert parse_iso8601_duration("P0D") == 0
    assert parse_iso8601_duration("P1DT2H") == 93_600


def test_filter_removes_shorts_and_too_long_videos() -> None:
    result = FilterAgent().run([video("short", 60), video("kept", 600), video("long", 1801)], 30)
    assert [item.video_id for item in result] == ["kept"]


def test_filter_keeps_long_videos_when_viewing_time_is_unlimited() -> None:
    result = FilterAgent().run([video("short", 60), video("long", 10_800)], None)
    assert [item.video_id for item in result] == ["long"]


def test_temporal_window_detects_this_week_without_a_space() -> None:
    assert temporal_window("이번주 미국 증시 흐름을 요약해 줘").days == 7


def test_temporal_window_is_none_for_a_timeless_request() -> None:
    assert temporal_window("블랙홀의 원리를 설명해 줘") is None


def test_youtube_search_query_removes_time_and_request_filler() -> None:
    assert youtube_search_query("경제·주식", "이번 주 미국 증시 흐름을 요약해 주는 영상을 찾아줘") == "미국 증시 흐름"


def test_analysis_and_ranking() -> None:
    request = RecommendationRequest(category="테크", detail_request="FastAPI Supabase login",
        max_duration_minutes=30, purpose=ViewingPurpose.PRACTICE)
    results = RankingAgent().run(AnalysisAgent().run(request, [video("weak", 900, "Python basics"), video("match", 900)]))
    assert results[0].video_id == "match"
