from datetime import UTC, datetime, timedelta
import re
from uuid import UUID

from app.schemas import RecommendedVideo, RecommendationRequest, RecommendationResponse, ViewingPurpose
from app.services.cache import RecommendationCache
from app.services.youtube import YouTubeClient, YouTubeVideo
from app.repositories.history import RecommendationHistoryRepository


def temporal_window(detail_request: str) -> timedelta | None:
    """Turn common Korean freshness phrases into a search window."""
    normalized = detail_request.replace(" ", "").lower()
    if any(phrase in normalized for phrase in ("오늘", "금일")):
        return timedelta(days=1)
    if any(phrase in normalized for phrase in ("어제", "어제자")):
        return timedelta(days=2)
    if any(phrase in normalized for phrase in ("이번주", "금주", "최근일주일")):
        return timedelta(days=7)
    if any(phrase in normalized for phrase in ("이번달", "금월", "최근한달")):
        return timedelta(days=31)
    if any(phrase in normalized for phrase in ("최근", "최신", "요즘")):
        return timedelta(days=30)
    return None


def youtube_search_query(category: str, detail_request: str) -> str:
    """Remove natural-language filler so YouTube receives the actual topic words."""
    stop_words = {
        "이번", "주", "오늘", "금일", "어제", "최근", "최신", "요즘", "이번달", "금월",
        "영상", "영상을", "찾아줘", "찾아", "주세요", "해줘", "해주세요", "주는", "주제",
        "보여줘", "알려줘", "추천해줘", "요약해", "정리해", "설명해", "부탁해",
    }
    tokens = re.findall(r"[0-9A-Za-z가-힣·]+", detail_request)
    topic_words = []
    for token in tokens:
        word = token.lower()
        if word in stop_words:
            continue
        # Korean object/topic particles often stick to the search keyword.
        for particle in ("으로", "에서", "에게", "을", "를", "은", "는", "이", "가"):
            if word.endswith(particle) and len(word) > len(particle) + 1:
                word = word[: -len(particle)]
                break
        if word:
            topic_words.append(word)
    return " ".join(topic_words[:6]) or category.replace("·", " ")


class SearchAgent:
    def __init__(self, youtube: YouTubeClient, candidate_limit: int) -> None:
        self.youtube, self.candidate_limit = youtube, candidate_limit

    async def run(self, request: RecommendationRequest) -> list[str]:
        window = temporal_window(request.detail_request)
        published_after = datetime.now(UTC) - window if window else None
        return await self.youtube.search_video_ids(
            youtube_search_query(request.category, request.detail_request), self.candidate_limit, published_after
        )


class VideoDetailAgent:
    def __init__(self, youtube: YouTubeClient) -> None:
        self.youtube = youtube

    async def run(self, ids: list[str]) -> list[YouTubeVideo]:
        return await self.youtube.get_videos(ids)


class FilterAgent:
    def run(self, videos: list[YouTubeVideo], max_minutes: int | None) -> list[YouTubeVideo]:
        if max_minutes is None:
            return [video for video in videos if video.duration_seconds > 60]
        return [video for video in videos if 60 < video.duration_seconds <= max_minutes * 60]


class AnalysisAgent:
    purpose_text = {
        ViewingPurpose.SUMMARY: "핵심 내용을 빠르게 파악하려는 목적",
        ViewingPurpose.CONCEPT: "개념을 이해하려는 목적",
        ViewingPurpose.DEEP_DIVE: "주제를 깊이 분석하려는 목적",
        ViewingPurpose.PRACTICE: "직접 실습하려는 목적",
        "빠른 요약": "핵심 내용을 빠르게 파악하려는 목적",
        "개념 이해": "개념을 이해하려는 목적",
        "심층 학습": "주제를 깊이 학습하려는 목적",
        "실습·문제 해결": "직접 적용하거나 문제를 해결하려는 목적",
        "최신 트렌드·뉴스": "최신 흐름과 이슈를 파악하려는 목적",
        "비교·구매 판단": "제품·서비스를 비교하고 판단하려는 목적",
        "투자·시장 분석": "시장 흐름과 투자 관점을 살피려는 목적",
        "아이디어·영감": "새로운 아이디어와 영감을 얻으려는 목적",
        "취미·휴식": "취미를 즐기거나 편안하게 시청하려는 목적",
    }

    def run(self, request: RecommendationRequest, videos: list[YouTubeVideo]) -> list[RecommendedVideo]:
        keywords = {word.lower() for word in f"{request.category} {request.detail_request}".split() if len(word) > 1}
        window = temporal_window(request.detail_request)
        now = datetime.now(UTC)
        results = []
        for video in videos:
            haystack = " ".join([video.title, video.description, *video.tags]).lower()
            # Repeated matches matter: a keyword present in the title as well as
            # the description/tags is a stronger signal than a single mention.
            matches = sum(haystack.count(word) for word in keywords)
            duration_ratio = (
                video.duration_seconds / (request.max_duration_minutes * 60)
                if request.max_duration_minutes
                else None
            )
            duration_bonus = 15 if duration_ratio is not None and .2 <= duration_ratio <= .9 else 5
            freshness_bonus = 0.0
            if window:
                age_seconds = max(0.0, (now - video.published_at).total_seconds())
                freshness_bonus = max(0.0, 25 * (1 - age_seconds / window.total_seconds()))
            score = min(99.9, round(40 + matches * 4 + duration_bonus + freshness_bonus, 1))
            minutes = max(1, round(video.duration_seconds / 60))
            purpose_description = self.purpose_text.get(request.purpose, f"{request.purpose}을 위한 목적")
            freshness_reason = " 최근 업로드된 영상이라 " if window else " "
            results.append(RecommendedVideo(
                video_id=video.video_id, title=video.title, channel_name=video.channel_name,
                thumbnail_url=video.thumbnail_url, duration_seconds=video.duration_seconds,
                published_at=video.published_at, view_count=video.view_count, tags=video.tags,
                relevance_score=score,
                recommendation_reason=(f"{purpose_description}에 맞고{freshness_reason}요청 키워드 {matches}개가 "
                                       f"제목·설명·태그에서 확인되었습니다. {minutes}분 길이로 시청 시간 안에 볼 수 있습니다."),
            ))
        return results


class RankingAgent:
    def run(self, videos: list[RecommendedVideo]) -> list[RecommendedVideo]:
        return sorted(videos, key=lambda item: (item.relevance_score, item.view_count or 0), reverse=True)


class RecommendationOrchestrator:
    def __init__(self, search: SearchAgent, detail: VideoDetailAgent, filter_agent: FilterAgent,
                 analysis: AnalysisAgent, ranking: RankingAgent, cache: RecommendationCache, ttl: int,
                 history: RecommendationHistoryRepository | None = None) -> None:
        self.search, self.detail, self.filter_agent = search, detail, filter_agent
        self.analysis, self.ranking, self.cache, self.ttl = analysis, ranking, cache, ttl
        self.history = history

    async def recommend(self, request: RecommendationRequest, user_id: str | None = None,
                        user_email: str | None = None, conversation_id: UUID | None = None) -> RecommendationResponse:
        key = self.cache.key_for(request.model_dump(mode="json"))
        cached = await self.cache.get(key)
        if cached:
            response = RecommendationResponse.model_validate({**cached, "cached": True})
            if self.history:
                saved_ids = await self.history.save(response, user_id, user_email, conversation_id)
                if saved_ids:
                    response = response.model_copy(update={
                        "recommendations": [
                            item.model_copy(update={"recommendation_id": saved_ids.get(index)})
                            for index, item in enumerate(response.recommendations, start=1)
                        ]
                    })
            return response
        ids = await self.search.run(request)
        details = await self.detail.run(ids)
        filtered = self.filter_agent.run(details, request.max_duration_minutes)
        recommended = self.ranking.run(self.analysis.run(request, filtered))
        response = RecommendationResponse(request=request, recommendations=recommended,
            candidate_count=len(details), filtered_count=len(filtered), cached=False, generated_at=datetime.now(UTC))
        if self.history:
            saved_ids = await self.history.save(response, user_id, user_email, conversation_id)
            if saved_ids:
                response = response.model_copy(update={
                    "recommendations": [
                        item.model_copy(update={"recommendation_id": saved_ids.get(index)})
                        for index, item in enumerate(response.recommendations, start=1)
                    ]
                })
        await self.cache.set(key, response.model_dump(mode="json"), self.ttl)
        return response
