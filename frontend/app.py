import os
from copy import deepcopy
from uuid import uuid4

from dotenv import load_dotenv
import streamlit as st
import streamlit.components.v1 as components

from components.recommendation_card import render_recommendation_card
from services.api_client import YouPickApiClient, YouPickApiError

load_dotenv()
st.set_page_config(page_title="YouPick", page_icon="▶", layout="wide", initial_sidebar_state="expanded")

DURATIONS = {
    "10분 이내": 10,
    "30분 이내": 30,
    "60분 이내": 60,
    "120분 이내": 120,
    "제한 없음": None,
}
PURPOSE_OPTIONS = [
    "빠른 요약",
    "개념 이해",
    "심층 학습",
    "실습·문제 해결",
    "최신 트렌드·뉴스",
    "비교·구매 판단",
    "투자·시장 분석",
    "아이디어·영감",
    "취미·휴식",
    "직접 입력",
]
QUICK_REQUESTS = [
    {
        "label": "과학 · 블랙홀 원리",
        "prompt": "블랙홀의 원리를 쉽게 설명해 주는 영상을 찾아줘",
        "category": "과학",
        "purpose": "개념 이해",
        "duration": "30분 이내",
    },
    {
        "label": "경제 · 미국 증시 요약",
        "prompt": "이번 주 미국 증시 흐름을 요약해 주는 영상을 찾아줘",
        "category": "경제·주식",
        "purpose": "투자·시장 분석",
        "duration": "10분 이내",
    },
    {
        "label": "테크 · 노트북 비교",
        "prompt": "개발용 노트북을 비교해 주는 영상을 찾아줘",
        "category": "테크·IT",
        "purpose": "비교·구매 판단",
        "duration": "30분 이내",
    },
    {
        "label": "자기계발 · 시간 관리",
        "prompt": "효율적인 시간 관리 루틴에 영감을 주는 영상을 찾아줘",
        "category": "자기계발",
        "purpose": "아이디어·영감",
        "duration": "10분 이내",
    },
]
WELCOME_MESSAGE = """안녕하세요, **YouPick**입니다.

무엇을 보고 싶은지 편하게 말해 주세요. 현재 목적과 시간 안에 볼 수 있는 YouTube 영상을 골라드릴게요."""


def api_client() -> YouPickApiClient:
    return YouPickApiClient(os.getenv("BACKEND_URL", "http://127.0.0.1:8000"))


def google_id_token() -> str:
    """The exposed, short-lived Google ID token used by the API to verify the account."""
    return st.user.tokens["id"]


def account_conversation_to_chat(conversation: dict) -> dict:
    messages = [{"role": "assistant", "kind": "text", "content": WELCOME_MESSAGE}]
    requests = sorted(conversation.get("search_requests", []), key=lambda item: item.get("created_at", ""))
    for request in requests:
        messages.append({"role": "user", "kind": "text", "content": request["detail_request"]})
        videos = sorted(request.get("recommendations", []), key=lambda item: item.get("rank", 0))
        for video in videos:
            video["recommendation_id"] = video.pop("id")
        messages.append({
            "role": "assistant", "kind": "result",
            "content": {
                "recommendations": videos,
                "candidate_count": request["candidate_count"],
                "filtered_count": request["filtered_count"],
                "cached": request["cached"],
            },
            "id": str(uuid4()),
        })
    return {
        "id": conversation["id"], "title": conversation["title"], "request_count": len(requests),
        "messages": messages,
    }


def load_account_history() -> None:
    try:
        rows = api_client().conversations(google_id_token())
        st.session_state.conversation_history = [account_conversation_to_chat(row) for row in rows]
    except YouPickApiError as exc:
        st.session_state.conversation_history = []
        st.warning(f"계정 대화 이력을 불러오지 못했어요: {exc}")


def render_youtube_quota() -> None:
    """Display the application's estimated remaining YouTube API quota."""
    try:
        quota = api_client().youtube_quota()
        remaining = quota["remaining_units"]
        limit = quota["daily_limit"]
        used = quota["used_units"]
        ratio = remaining / limit if limit else 0
        st.metric("YouTube API 잔여량", f"{remaining:,} / {limit:,} 유닛", f"오늘 {used:,} 유닛 사용")
        st.progress(ratio, text="앱 호출 기준 예상 잔여량 · 매일 미국 태평양 자정 초기화")
    except YouPickApiError:
        st.caption("YouTube API 잔여량을 확인하려면 백엔드를 실행해 주세요.")


def reset_chat() -> None:
    st.session_state.messages = [{"role": "assistant", "kind": "text", "content": WELCOME_MESSAGE}]
    st.session_state.conversation_id = str(uuid4())


def archive_current_chat() -> None:
    """Keep the current session's finished conversation before opening a new one."""
    user_messages = [message for message in st.session_state.messages if message["role"] == "user"]
    if not user_messages:
        return
    # Requests are persisted to the logged-in account by the backend. This function
    # remains as a no-op so the new-chat flow reads naturally.
    return


def open_archived_chat(chat: dict) -> None:
    st.session_state.messages = deepcopy(chat["messages"])
    st.session_state.opened_archive_id = chat["id"]
    st.session_state.conversation_id = chat["id"]
    st.rerun()


def submit_feedback(video: dict, helpful: bool) -> None:
    if not video.get("recommendation_id"):
        st.info("이전 캐시 결과는 피드백을 연결할 수 없습니다. 다시 요청해 주세요.")
        return
    try:
        api_client().send_feedback(
            {"recommendation_id": video["recommendation_id"], "is_helpful": helpful}, google_id_token()
        )
        st.toast("피드백을 저장했어요. 다음 추천 개선에 활용할게요.", icon="✓")
    except YouPickApiError as exc:
        st.error(f"피드백 저장에 실패했어요: {exc}")


def request_recommendation(prompt: str, category: str, purpose: str, duration_label: str) -> None:
    """Add one user request and its recommendation response to the chat history."""
    clean_prompt = prompt.strip()
    if len(clean_prompt) < 3 or not category.strip() or not purpose.strip():
        st.warning("요청은 세 글자 이상, 카테고리와 시청 목적은 모두 입력해 주세요.")
        return

    # A new request from an opened archive starts a new branch of conversation.
    st.session_state.opened_archive_id = None
    st.session_state.messages.append({"role": "user", "kind": "text", "content": clean_prompt})
    payload = {
        "category": category.strip(),
        "detail_request": clean_prompt,
        "max_duration_minutes": DURATIONS[duration_label],
        "purpose": purpose.strip(),
    }
    try:
        with st.spinner("조건에 맞는 영상을 고르고 있어요..."):
            result = api_client().recommend(payload, google_id_token(), st.session_state.conversation_id)
        result_id = str(uuid4())
        st.session_state.messages.append(
            {"role": "assistant", "kind": "result", "content": result, "id": result_id}
        )
        st.session_state.scroll_target_id = result_id
    except YouPickApiError as exc:
        error_message = f"추천을 가져오지 못했어요: {exc}"
        st.session_state.messages.append({"role": "assistant", "kind": "text", "content": error_message})
    load_account_history()
    st.rerun()


def locked_dropdown(label: str, options: list[str], key: str, default_index: int = 0) -> str:
    """A closed-on-select dropdown that never accepts values outside its options."""
    return st.selectbox(
        label,
        options,
        index=default_index,
        key=key,
        accept_new_options=False,
    )


def render_result(result: dict, focus: bool = False) -> None:
    if focus:
        st.markdown('<div id="top-recommendation" class="recommendation-anchor"></div>', unsafe_allow_html=True)
        components.html(
            """
            <script>
              const moveToTopRecommendation = () => {
                const target = window.parent.document.getElementById('top-recommendation');
                if (!target) return;
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                const containers = [
                  window.parent.document.querySelector('[data-testid="stAppViewContainer"]'),
                  window.parent.document.querySelector('section[data-testid="stMain"]'),
                  window.parent.document.scrollingElement,
                ].filter(Boolean);
                containers.forEach((container) => {
                  const offset = target.getBoundingClientRect().top - 18;
                  if (Math.abs(offset) > 2) container.scrollTop += offset;
                });
              };
              // Streamlit focuses chat_input after a rerun, so repeat after its own scroll completes.
              [100, 450, 900, 1400].forEach((delay) => {
                window.setTimeout(moveToTopRecommendation, delay);
              });
            </script>
            """,
            height=0,
        )
        st.session_state.scroll_target_id = None
    summary_left, summary_center, summary_right = st.columns(3)
    summary_left.metric("추천 결과", f"{len(result['recommendations'])}개")
    summary_center.metric("검토한 후보", f"{result['candidate_count']}개")
    summary_right.metric("검색 방식", "캐시" if result["cached"] else "새로 검색")

    if not result["recommendations"]:
        st.info("조건에 맞는 영상이 없습니다. 시간 제한을 늘리거나 요청을 조금 더 넓게 입력해 보세요.")
        return

    st.caption("아래 결과는 시청 기록이 아닌, 이번 대화의 요청과 설정만 반영합니다.")
    for rank, video in enumerate(result["recommendations"], start=1):
        with st.container(border=True):
            render_recommendation_card(video, rank)
            helpful, unhelpful, _ = st.columns([1, 1, 5])
            with helpful:
                if st.button("도움됐어요", key=f"helpful-{video['recommendation_id']}-{rank}"):
                    submit_feedback(video, True)
            with unhelpful:
                if st.button("아쉬워요", key=f"not-helpful-{video['recommendation_id']}-{rank}"):
                    submit_feedback(video, False)


def render_sidebar_history() -> None:
    """Show archived conversations as well as the current one."""
    archived_chats = st.session_state.conversation_history
    user_requests = [message for message in st.session_state.messages if message["role"] == "user"]
    with st.container(height=360, border=True):
        if archived_chats:
            st.caption("이전 대화")
            for chat in reversed(archived_chats):
                suffix = "…" if len(chat["title"]) >= 42 else ""
                if st.button(
                    f"🗂 {chat['title']}{suffix}",
                    key=f"open-history-{chat['id']}",
                    use_container_width=True,
                ):
                    open_archived_chat(chat)
                st.caption(f"↳ 요청 {chat['request_count']}개")
            st.divider()

        if not user_requests:
            st.caption("현재 대화에는 아직 요청이 없어요.")
            return

        st.caption("현재 대화")
        request_number = 0
        for message in st.session_state.messages:
            if message["role"] == "user":
                request_number += 1
                preview = message["content"].replace("\n", " ")
                suffix = "…" if len(preview) > 52 else ""
                st.markdown(f"**{request_number}. 🧑 {preview[:52]}{suffix}**")
            elif message["kind"] == "result":
                count = len(message["content"]["recommendations"])
                st.caption(f"↳ ▶ YouPick 추천 {count}개")
            elif message["role"] == "assistant" and message["content"] != WELCOME_MESSAGE:
                st.caption("↳ ▶ 응답을 확인해 주세요")


if "messages" not in st.session_state:
    reset_chat()
if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []
if "opened_archive_id" not in st.session_state:
    st.session_state.opened_archive_id = None
if "scroll_target_id" not in st.session_state:
    st.session_state.scroll_target_id = None

st.markdown(
    """
    <style>
      .stApp { background: radial-gradient(circle at top, #182242 0%, #090d1a 46%); }
      .block-container { max-width: 1000px; padding-top: 2rem; }
      [data-testid="stSidebar"] { background: #0e1628 !important; border-right: 1px solid #27324a; }
      [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
      [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] strong,
      [data-testid="stSidebar"] [data-testid="stCaptionContainer"] { color: #e2e8f0 !important; }
      [data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"] { background: #151f34; border-color: #31405e; }
      [data-testid="stChatMessage"] { padding: 0.8rem 0; }
      .welcome-hero { text-align: center; margin: 19vh 0 2rem; }
      .welcome-hero h1 { font-size: clamp(2.2rem, 5vw, 4.3rem); letter-spacing: -0.07em; }
      .welcome-hero p { color: #64748b; font-size: 1.1rem; }
      .composer-caption { color: #64748b; font-size: 0.9rem; text-align: center; }
      .rank-hero {
        align-items: center; border: 1px solid; border-radius: 12px; display: flex;
        gap: 0.7rem; margin-bottom: 0.8rem; padding: 0.65rem 0.9rem;
      }
      .rank-medal { font-size: 1.75rem; line-height: 1; }
      .rank-hero span { color: #cbd5e1; display: block; font-size: 0.75rem; font-weight: 700; }
      .rank-hero strong { color: #f8fafc; display: block; font-size: 1rem; }
      .rank-score { border-left: 1px solid rgba(255,255,255,.22); margin-left: auto; padding-left: 0.9rem; text-align: right; }
      .rank-gold { background: linear-gradient(90deg, #4a3411, #2b2112); border-color: #d9a441; }
      .rank-silver { background: linear-gradient(90deg, #293547, #182231); border-color: #9aacbe; }
      .rank-bronze { background: linear-gradient(90deg, #48291b, #2d1d19); border-color: #be734c; }
      .rank-default { background: linear-gradient(90deg, #202653, #171d39); border-color: #626cc3; }
      .recommendation-anchor { scroll-margin-top: 1rem; }
      button[kind="primary"] {
        background: linear-gradient(135deg, #7c3aed, #2563eb) !important;
        border: 1px solid #a78bfa !important; border-radius: 12px !important;
        box-shadow: 0 8px 22px rgba(79, 70, 229, .35); font-size: 1rem !important;
        font-weight: 700 !important; letter-spacing: .02em; min-height: 3rem;
      }
      button[kind="primary"]:hover { filter: brightness(1.14); transform: translateY(-1px); }
    </style>
    """,
    unsafe_allow_html=True,
)

if not getattr(st.user, "is_logged_in", False):
    st.markdown(
        """
        <section class="welcome-hero">
          <h1>YouPick</h1>
          <p>Google 계정으로 로그인하면 대화와 추천 결과를 계정별로 보관합니다.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Google 계정으로 로그인", type="primary", use_container_width=True):
        st.login("google")
    st.stop()

if st.session_state.get("account_subject") != st.user.sub:
    st.session_state.account_subject = st.user.sub
    load_account_history()

with st.sidebar:
    st.title("YouPick")
    st.caption(f"{st.user.get('name', 'Google 사용자')} · {st.user.get('email', '')}")
    st.caption("대화의 맥락보다, 지금의 목적을 우선합니다.")
    st.divider()
    st.subheader("대화 이력")
    render_sidebar_history()
    st.divider()
    st.subheader("API 할당량")
    render_youtube_quota()
    st.caption("Google Console의 실제 사용량과 약간의 차이가 날 수 있습니다.")
    st.divider()
    if st.button("새 대화", use_container_width=True):
        if st.session_state.opened_archive_id is None:
            archive_current_chat()
        reset_chat()
        st.session_state.opened_archive_id = None
        st.rerun()
    if st.button("로그아웃", use_container_width=True):
        st.logout()

has_user_message = any(message["role"] == "user" for message in st.session_state.messages)

if not has_user_message:
    st.markdown(
        """
        <section class="welcome-hero">
          <h1>무엇을 보고 싶으세요?</h1>
          <p>지금 필요한 영상의 주제와 목적을 편하게 말해 주세요.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )
    with st.container(border=True):
        landing_prompt = st.text_area(
            "영상 요청",
            placeholder="예: 블랙홀의 원리를 쉽게 설명해 주는 영상을 찾아줘",
            label_visibility="collapsed",
            height=120,
            key="landing-prompt",
        )
        category_column, purpose_column, duration_column = st.columns(3)
        with category_column:
            category_choice = locked_dropdown(
                "카테고리",
                ["테크·IT", "과학", "경제·주식", "자기계발", "디자인", "직접 입력"],
                "landing-category",
            )
        with purpose_column:
            purpose_choice = locked_dropdown(
                "시청 목적",
                PURPOSE_OPTIONS,
                "landing-purpose",
                default_index=0,
            )
        with duration_column:
            duration_label = locked_dropdown("시청 시간", list(DURATIONS), "landing-duration", default_index=1)
        category = (
            st.text_input("직접 입력할 카테고리", placeholder="예: 역사, 요리")
            if category_choice == "직접 입력"
            else category_choice
        )
        purpose = (
            st.text_input("직접 입력할 시청 목적", placeholder="예: 면접 대비, 취미 탐색")
            if purpose_choice == "직접 입력"
            else purpose_choice
        )
        submitted = st.button("✦  보내기", type="primary", use_container_width=True, help="추천 요청 보내기")
    st.markdown("<p class='composer-caption'>요청과 조건을 함께 입력하면 더 정확한 영상을 추천해 드려요.</p>", unsafe_allow_html=True)

    suggestion_columns = st.columns(len(QUICK_REQUESTS))
    for column, suggestion in zip(suggestion_columns, QUICK_REQUESTS):
        with column:
            if st.button(suggestion["label"], use_container_width=True):
                request_recommendation(
                    suggestion["prompt"],
                    suggestion["category"],
                    suggestion["purpose"],
                    suggestion["duration"],
                )
    if submitted:
        request_recommendation(landing_prompt, category, purpose, duration_label)
else:
    st.title("YouPick 대화")
    st.caption("현재 대화의 요청과 설정만 반영해 영상을 추천합니다.")
    with st.expander("다음 추천 조건", expanded=True):
        category_column, purpose_column, duration_column = st.columns(3)
        with category_column:
            category_choice = locked_dropdown(
                "카테고리",
                ["테크·IT", "과학", "경제·주식", "자기계발", "디자인", "직접 입력"],
                "chat-category",
            )
        with purpose_column:
            purpose_choice = locked_dropdown(
                "시청 목적",
                PURPOSE_OPTIONS,
                "chat-purpose",
                default_index=0,
            )
        with duration_column:
            duration_label = locked_dropdown("시청 시간", list(DURATIONS), "chat-duration", default_index=1)
        category = (
            st.text_input("직접 입력할 카테고리", placeholder="예: 역사, 요리", key="chat-category-custom")
            if category_choice == "직접 입력"
            else category_choice
        )
        purpose = (
            st.text_input("직접 입력할 시청 목적", placeholder="예: 면접 대비, 취미 탐색", key="chat-purpose-custom")
            if purpose_choice == "직접 입력"
            else purpose_choice
        )
    for message in st.session_state.messages:
        avatar = "▶" if message["role"] == "assistant" else "🙂"
        with st.chat_message(message["role"], avatar=avatar):
            if message["kind"] == "text":
                st.markdown(message["content"])
            else:
                st.markdown("조건에 맞는 영상을 찾았어요.")
                render_result(message["content"], focus=message.get("id") == st.session_state.scroll_target_id)

    prompt = st.chat_input("예: 이번 주 미국 증시 흐름을 요약해 주는 영상을 찾아줘")
    if prompt:
        request_recommendation(prompt, category, purpose, duration_label)
