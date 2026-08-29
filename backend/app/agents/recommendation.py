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

    @staticmethod
    def _matched_terms(keywords: set[str], text: str) -> list[str]:
        normalized = text.lower()
        return sorted((word for word in keywords if word in normalized), key=len, reverse=True)

    @staticmethod
    def _duration_text(seconds: int) -> str:
        minutes, remaining_seconds = divmod(seconds, 60)
        return f"{minutes}분 {remaining_seconds}초" if remaining_seconds else f"{minutes}분"

    @staticmethod
    def _view_count_text(view_count: int | None) -> str | None:
        if view_count is None:
            return None
        if view_count >= 10_000:
            return f"조회수 약 {view_count / 10_000:.1f}만 회"
        return f"조회수 {view_count:,}회"

    @staticmethod
    def _short_review_for(video: YouTubeVideo, keywords: set[str]) -> str:
        """Select the most relevant public-description sentence and keep it review-length."""
        description = re.sub(r"https?://\S+", "", video.description)
        raw_sentences = re.split(r"(?:\r?\n)+|(?<=[.!?])\s+", description)
        filler_words = ("안녕하세요", "구독", "좋아요", "알림", "광고", "문의", "인스타", "카카오")
        candidates = []
        for sentence in raw_sentences:
            sentence = re.sub(r"\s+", " ", sentence).strip(" -•#\t")
            if len(sentence) < 12 or any(word in sentence.lower() for word in filler_words):
                continue
            # Descriptions often contain line-wrapped fragments such as "...이해하고".
            # Use only a sentence that appears complete; never cut a raw fragment mid-sentence.
            if not re.search(r"(?:다|요|니다|습니다|죠|까요)[.!?]?$", sentence):
                continue
            matched = len(AnalysisAgent._matched_terms(keywords, sentence))
            # Prefer request-related sentences around 50 characters over a long description block.
            score = matched * 100 - abs(len(sentence) - 50)
            candidates.append((score, sentence))

        if candidates:
            _, review = max(candidates, key=lambda item: item[0])
            if len(review) <= 65:
                return review

        title = re.sub(r"\[[^\]]+\]", "", video.title).strip()
        title = title[:29].rstrip(" ,.")
        return f"{title}를 중심으로 핵심 흐름을 정리하는 영상입니다."

    def _reason_for(
        self, request: RecommendationRequest, video: YouTubeVideo, keywords: set[str], now: datetime,
        freshness_window: timedelta | None,
    ) -> str:
        title_terms = self._matched_terms(keywords, video.title)
        tag_terms = self._matched_terms(keywords, " ".join(video.tags))
        description_terms = self._matched_terms(keywords, video.description)
        if title_terms:
            evidence = "제목에서 ‘" + "’, ‘".join(title_terms[:3]) + "’을 직접 다룹니다"
        elif tag_terms:
            evidence = "태그에 ‘" + "’, ‘".join(tag_terms[:3]) + "’이 포함돼 있습니다"
        elif description_terms:
            evidence = "설명에서 ‘" + "’, ‘".join(description_terms[:3]) + "’ 관련 내용을 확인했습니다"
        else:
            evidence = f"‘{video.title[:44]}’이라는 주제로 요청과 가까운 내용을 다룹니다"

        published_date = video.published_at.astimezone(UTC).strftime("%Y.%m.%d")
        age_days = max(0, int((now - video.published_at).total_seconds() // 86_400))
        if freshness_window:
            if age_days == 0:
                freshness = "오늘 업로드된 최신 영상입니다"
            elif age_days == 1:
                freshness = "어제 업로드된 최신 영상입니다"
            else:
                freshness = f"{age_days}일 전({published_date}) 업로드돼 최신성 조건에 맞습니다"
        else:
            freshness = f"업로드일은 {published_date}입니다"

        duration = self._duration_text(video.duration_seconds)
        if request.max_duration_minutes:
            time_fit = f"{duration} 길이로 설정한 {request.max_duration_minutes}분 안에 시청할 수 있습니다"
        else:
            time_fit = f"{duration} 길이의 영상입니다"
        popularity = self._view_count_text(video.view_count)
        purpose = self.purpose_text.get(request.purpose, f"{request.purpose} 목적")
        parts = [f"{purpose}에 적합합니다", evidence, freshness, time_fit]
        if popularity:
            parts.append(popularity)
        return ". ".join(parts) + "."

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
            results.append(RecommendedVideo(
                video_id=video.video_id, title=video.title, channel_name=video.channel_name,
                thumbnail_url=video.thumbnail_url, duration_seconds=video.duration_seconds,
                published_at=video.published_at, view_count=video.view_count, tags=video.tags,
                relevance_score=score,
                recommendation_reason=self._reason_for(request, video, keywords, now, window),
                short_review=self._short_review_for(video, keywords),
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
        # Bump this cache namespace when the response-generation logic changes.
        key = self.cache.key_for({**request.model_dump(mode="json"), "recommendation_reason_version": 7})
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
