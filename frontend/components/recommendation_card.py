from datetime import datetime

import streamlit as st


def format_duration(seconds: int) -> str:
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"


def rank_badge(rank: int) -> tuple[str, str, str]:
    if rank == 1:
        return "🥇", "TOP 1", "rank-gold"
    if rank == 2:
        return "🥈", "TOP 2", "rank-silver"
    if rank == 3:
        return "🥉", "TOP 3", "rank-bronze"
    return "▶", f"TOP {rank}", "rank-default"


def fallback_short_review(video: dict) -> str:
    """Keep older, pre-review history entries visually complete."""
    title = video["title"].replace("\n", " ").strip()
    return f"‘{title[:32].rstrip(' ,.') }’ 주제를 다루는 영상입니다."


def render_recommendation_card(video: dict, rank: int, render_actions=None) -> None:
    left, right = st.columns([1, 2])
    with left:
        st.image(video["thumbnail_url"], use_container_width=True)
        if render_actions:
            st.markdown('<div class="thumbnail-action-spacer"></div>', unsafe_allow_html=True)
            render_actions(video, rank)
    with right:
        medal, rank_label, badge_style = rank_badge(rank)
        score = int(video["relevance_score"])
        st.markdown(
            f"""
            <div class="rank-hero {badge_style}">
                <span class="rank-medal">{medal}</span>
                <div><span>{rank_label}</span><strong>{rank}위 추천</strong></div>
                <div class="rank-score"><span>조건 적합도</span><strong>{score}점</strong></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.subheader(video["title"])
        st.write(f"{video['channel_name']} · {format_duration(video['duration_seconds'])}")
        st.progress(score, text="추천 조건 일치도")
        published_at = datetime.fromisoformat(video["published_at"].replace("Z", "+00:00"))
        st.caption(f"업로드: {published_at.date().isoformat()}")
        st.write(video["recommendation_reason"])
        short_review = video.get("short_review") or fallback_short_review(video)
        st.caption("짧은 리뷰 · 공개 설명에서 핵심 문장 추출")
        st.info(short_review, icon="💡")
