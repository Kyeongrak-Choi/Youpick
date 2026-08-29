# YouPick

현재 입력한 조건과 자연어 요청을 바탕으로 YouTube 영상을 추천하는 **멀티 에이전트 AI 오케스트레이션** 실습 프로젝트입니다. Python, FastAPI, Supabase(PostgreSQL), Redis, Streamlit으로 백엔드와 프런트엔드를 함께 구현했습니다.

> 기획서: [YouPick 프로젝트 기획서](https://kyeongrak-choi.github.io/post.html?path=posts%2FEncore%2FProject%2FYouPick_%ED%94%84%EB%A1%9C%EC%A0%9D%ED%8A%B8_%EA%B8%B0%ED%9A%8D%EC%84%9C_%EC%B4%88%EC%95%88.md)

## 현재 구현 상태

- 카테고리, 시청 목적, 시청 시간, 자연어 요청을 조합한 YouTube 영상 추천
- `Search → Detail → Filter → Analysis → Ranking` 역할 분리 및 FastAPI 오케스트레이션
- Shorts(60초 이하) 제외, 10·30·60·120분 또는 제한 없음 조건 지원
- `이번 주`, `최근`, `최신` 등의 시간 표현을 인식해 최근 영상 우선 검색·정렬
- 동일 요청 Redis 캐시로 YouTube API 호출 절감
- 추천 순위 카드, 적합도, 추천 이유, YouTube 이동, 피드백 UI
- Google 계정 로그인과 계정별 Supabase 대화 이력 저장·재열기
- YouTube API 앱 기준 예상 잔여 쿼터 표시

## 기술 스택

| 영역 | 기술 | 역할 |
| --- | --- | --- |
| Backend | Python, FastAPI | API, 인증 토큰 검증, 추천 워크플로 |
| Multi-agent | Python 서비스 계층 | 검색·상세조회·필터·분석·정렬 역할 분리 |
| Frontend | Streamlit | 로그인, 채팅형 요청 UI, 추천·이력 화면 |
| Database | Supabase / PostgreSQL | 요청, 추천 결과, 피드백, 계정별 대화 이력 |
| Cache | Redis | 동일 요청 추천 결과 캐시, 쿼터 절감 |
| External API | YouTube Data API v3 | 영상 검색과 상세 정보 조회 |
| Auth | Google OIDC | Google 로그인, 계정 식별 |

## 추천 처리 흐름

```text
Streamlit (Google 로그인)
  → FastAPI /api/v1/recommendations
    → Google ID token 검증
    → RecommendationOrchestrator
       ├─ SearchAgent       : YouTube search.list
       ├─ VideoDetailAgent  : YouTube videos.list
       ├─ FilterAgent       : Shorts·시간 조건 필터링
       ├─ AnalysisAgent     : 요청 키워드·최신성·목적 점수화
       └─ RankingAgent      : 최종 순위 정렬
    → Redis 캐시 / Supabase 이력 저장
  → 추천 카드와 계정별 대화 이력 표시
```

## 프로젝트 구조

```text
Youpick/
├── backend/
│   ├── app/
│   │   ├── agents/recommendation.py    # 멀티 에이전트·오케스트레이터
│   │   ├── api/v1/                     # 추천·피드백·이력·쿼터 API
│   │   ├── repositories/history.py      # Supabase 저장·조회
│   │   ├── services/                    # YouTube, Redis cache, quota
│   │   └── main.py                      # FastAPI 진입점
│   ├── supabase/migrations/             # Supabase SQL 마이그레이션
│   ├── tests/                           # 백엔드 테스트
│   └── .env.example
├── frontend/
│   ├── .streamlit/
│   │   ├── config.toml                  # 다크 테마
│   │   └── secrets.toml.example         # Google OIDC 설정 템플릿
│   ├── components/recommendation_card.py
│   ├── services/api_client.py
│   ├── app.py                           # Streamlit 진입점
│   └── .env.example
└── README.md
```

## 사전 준비

- Python 3.11 이상
- YouTube Data API v3 키
- Supabase 프로젝트와 Secret key
- Google OAuth 웹 애플리케이션 Client ID / Client secret
- Redis는 선택 사항입니다. 미설정 시 메모리 캐시를 사용합니다.

## 1. Supabase 설정

Supabase Dashboard → **SQL Editor**에서 아래 SQL을 번호 순서대로 실행합니다.

1. [001_initial_schema.sql](backend/supabase/migrations/001_initial_schema.sql)
2. [002_feedback.sql](backend/supabase/migrations/002_feedback.sql)
3. [003_allow_custom_purpose.sql](backend/supabase/migrations/003_allow_custom_purpose.sql)
4. [004_allow_unlimited_viewing_time.sql](backend/supabase/migrations/004_allow_unlimited_viewing_time.sql)
5. [005_google_account_history.sql](backend/supabase/migrations/005_google_account_history.sql)
6. [006_youtube_quota_usage.sql](backend/supabase/migrations/006_youtube_quota_usage.sql)
7. [007_recommendation_short_review.sql](backend/supabase/migrations/007_recommendation_short_review.sql)

## 2. Google 로그인 설정

Google Cloud Console → **Google 인증 플랫폼 → 클라이언트**에서 **웹 애플리케이션** OAuth 클라이언트를 만듭니다.

- 승인된 리디렉션 URI: `http://localhost:8501/oauth2callback`
- 테스트 모드라면 **대상 → 테스트 사용자**에 로그인할 Google 계정을 추가합니다.
- `Client ID`는 백엔드와 프런트엔드에 **동일한 값**을 사용합니다.

`redirect_uri_mismatch` 오류가 발생하면 Google Console의 리디렉션 URI가 위 주소와 한 글자까지 같은지 확인합니다. `127.0.0.1`이나 끝의 슬래시(`/`)는 사용하지 않습니다.

## 3. 환경 변수 설정

### Backend

```bash
cd backend
cp .env.example .env
```

`backend/.env`에 실제 값을 입력합니다. 이 파일은 Git에 올리지 않습니다.

```env
YOUTUBE_API_KEY=...
SUPABASE_URL=https://....supabase.co
SUPABASE_SECRET_KEY=...
REDIS_URL=redis://localhost:6379/0
GOOGLE_OAUTH_CLIENT_ID=....apps.googleusercontent.com
```

주요 선택 설정:

| 변수 | 기본값 | 설명 |
| --- | --- | --- |
| `YOUTUBE_CANDIDATE_LIMIT` | `50` | 검색할 영상 후보 수. `search.list` 한 번에 가능한 최대치 |
| `RECOMMENDATION_CACHE_TTL_SECONDS` | `1800` | 캐시 유지 시간(초) |
| `YOUTUBE_DAILY_QUOTA_LIMIT` | `10000` | 예상 잔여 쿼터 계산 기준 |

### Frontend

```bash
cd frontend
cp .env.example .env
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

`frontend/.env`에는 백엔드 주소만 둡니다.

```env
BACKEND_URL=http://127.0.0.1:8000
```

`frontend/.streamlit/secrets.toml`에 Google OAuth 정보를 입력합니다.

```toml
[auth]
redirect_uri = "http://localhost:8501/oauth2callback"
cookie_secret = "충분히_긴_임의의_문자열"
expose_tokens = ["id"]

[auth.google]
client_id = "...apps.googleusercontent.com"
client_secret = "Google_Cloud에서_발급한_Client_secret"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
```

`secrets.toml`, `.env`, API 키, OAuth Client secret은 절대 Git에 올리지 않습니다.

## 서버 실행

처음 한 번만 각 가상환경과 의존성을 준비합니다.

```bash
# backend
cd backend
python3 -m venv .venv
./.venv/bin/pip install -e '.[dev]'

# frontend
cd ../frontend
python3 -m venv .venv
./.venv/bin/pip install -e .
```

### 1) FastAPI 실행

첫 번째 터미널에서 실행합니다.

```bash
cd /Users/krchoi/Workspace/python/Youpick/backend
./.venv/bin/uvicorn app.main:app --reload
```

- API 상태 확인: <http://127.0.0.1:8000/health>
- API 문서: <http://127.0.0.1:8000/docs>

### 2) Streamlit 실행

두 번째 터미널에서 실행합니다.

```bash
cd /Users/krchoi/Workspace/python/Youpick/frontend
./.venv/bin/streamlit run app.py
```

브라우저에서 **<http://localhost:8501>**로 접속하고, `Google 계정으로 로그인` 버튼을 누릅니다. OAuth 관련 설정을 바꾼 뒤에는 Streamlit을 `Ctrl + C`로 종료한 후 다시 실행해야 합니다.

## 테스트

```bash
cd /Users/krchoi/Workspace/python/Youpick/backend
./.venv/bin/pytest
```

## YouTube API 쿼터 표시 기준

YouTube API는 남은 일일 쿼터를 응답으로 직접 반환하지 않습니다. 따라서 YouPick은 앱이 발생시킨 호출을 기준으로 예상치를 계산해 Supabase의 `youtube_api_quota_daily` 테이블에 저장합니다. 이 값은 **사용자별이 아니라 Google Cloud 프로젝트 전체**의 값이므로, 어느 계정으로 로그인해도 같은 사용량과 잔여량이 표시됩니다.

- `search.list`: 100유닛
- `videos.list`: 1유닛
- 같은 요청이 Redis 캐시에 있으면 YouTube API를 호출하지 않아 유닛을 차감하지 않음
- Google Console, 다른 프로그램, 직접 호출한 API 사용량은 포함하지 않음
- 기준 일자는 미국 태평양 시간이며, Supabase에 저장돼 서버 재시작이나 다른 로그인 사용자에게도 유지됨

## 문제 해결

| 증상 | 확인 방법 |
| --- | --- |
| `streamlit: command not found` | `frontend`에서 `./.venv/bin/streamlit run app.py`로 실행 |
| `StreamlitAuthError` | `frontend/.streamlit/secrets.toml`의 `[auth]`, `[auth.google]` 섹션과 TOML 따옴표 문법 확인 |
| `401 invalid_client` | frontend의 Client ID·Secret이 Google Console의 같은 OAuth 클라이언트 값인지 확인 |
| `400 redirect_uri_mismatch` | Google Console에 `http://localhost:8501/oauth2callback`을 정확히 등록하고 localhost로 접속 |
| 프런트엔드에서 백엔드 연결 실패 | FastAPI가 8000 포트에서 실행 중인지, `frontend/.env`의 `BACKEND_URL` 확인 |
| 잔여 쿼터가 Console과 다름 | 앱이 자체 추정한 값이며 Console/다른 앱의 호출은 포함하지 않음 |

## 참고

- [YouTube Data API - search.list](https://developers.google.com/youtube/v3/docs/search/list)
- [YouTube Data API - Quota Calculator](https://developers.google.com/youtube/v3/determine_quota_cost)
- [Google OAuth 웹 서버 애플리케이션](https://developers.google.com/identity/protocols/oauth2/web-server)
