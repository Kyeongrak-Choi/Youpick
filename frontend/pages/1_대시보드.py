"""Project operations dashboard for YouPick."""

import os

from dotenv import load_dotenv
import streamlit as st

from services.api_client import YouPickApiClient, YouPickApiError


load_dotenv()
st.set_page_config(page_title="YouPick 대시보드", page_icon="📊", layout="wide")


def api_client() -> YouPickApiClient:
    return YouPickApiClient(os.getenv("BACKEND_URL", "http://127.0.0.1:8000"))


if not getattr(st.user, "is_logged_in", False):
    st.title("YouPick 운영 대시보드")
    st.info("대시보드를 보려면 Google 계정으로 로그인해 주세요.")
    if st.button("Google 계정으로 로그인", type="primary"):
        st.login("google")
    st.stop()

st.markdown(
    """
    <style>
      .stApp { background: radial-gradient(circle at top, #182242 0%, #090d1a 46%); }
      .block-container { max-width: 1150px; padding-top: 2rem; }
      .dashboard-hero { margin-bottom: 1.6rem; }
      .dashboard-hero h1 { letter-spacing: -.05em; margin-bottom: .2rem; }
      .dashboard-hero p { color: #94a3b8; }
      [data-testid="stMetric"] { background: #111a2d; border: 1px solid #2c3a58; border-radius: 14px; padding: .75rem 1rem; }
      [data-testid="stMetricLabel"] { color: #a5b4fc; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <section class="dashboard-hero">
      <h1>프로젝트 운영 대시보드</h1>
      <p>추천 품질, 사용자 반응, 캐시 효율, API 사용량을 한눈에 확인합니다.</p>
    </section>
    """,
    unsafe_allow_html=True,
)

try:
    overview = api_client().dashboard_overview(st.user.tokens["id"])
except YouPickApiError as exc:
    st.error(f"대시보드를 불러오지 못했어요: {exc}")
    st.stop()

quota = overview["quota"]
metric1, metric2, metric3, metric4 = st.columns(4)
metric1.metric("총 추천 요청", f"{overview['total_requests']:,}건")
metric2.metric("추천 영상", f"{overview['total_recommendations']:,}개")
metric3.metric("도움됨 비율", f"{overview['helpful_rate']:.1f}%", f"피드백 {overview['feedback_total']:,}건")
metric4.metric("API 잔여량", f"{quota['remaining_units']:,} 유닛", f"오늘 {quota['used_units']:,} 유닛 사용")

st.divider()
trend_column, efficiency_column = st.columns([1.7, 1])
with trend_column:
    st.subheader("최근 7일 추천 요청")
    daily_requests = overview["daily_requests"]
    if daily_requests:
        st.bar_chart(daily_requests, x="date", y="count", color="#8b5cf6", use_container_width=True)
    else:
        st.info("아직 최근 추천 요청 데이터가 없습니다.")

with efficiency_column:
    st.subheader("캐시 효율")
    st.metric("캐시 적중률", f"{overview['cache_hit_rate']:.1f}%", f"적중 {overview['cache_hits']:,}건")
    st.caption("같은 조건의 추천을 다시 요청할 때 YouTube API 호출을 줄인 비율입니다.")

category_column, purpose_column = st.columns(2)
with category_column:
    st.subheader("인기 카테고리")
    categories = overview["popular_categories"]
    if categories:
        st.bar_chart(categories, x="label", y="count", color="#6366f1", horizontal=True, use_container_width=True)
    else:
        st.info("집계할 카테고리 데이터가 없습니다.")

with purpose_column:
    st.subheader("인기 시청 목적")
    purposes = overview["popular_purposes"]
    if purposes:
        st.bar_chart(purposes, x="label", y="count", color="#14b8a6", horizontal=True, use_container_width=True)
    else:
        st.info("집계할 시청 목적 데이터가 없습니다.")

st.caption("집계 값은 프로젝트 전체 추천·피드백 데이터를 기준으로 합니다.")
