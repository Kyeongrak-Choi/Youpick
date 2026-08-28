# YouPick

사용자가 **현재 입력한 조건**만을 기준으로 YouTube 영상을 찾아 추천하는 멀티 에이전트 AI 오케스트레이션 실습 프로젝트입니다. 기존 시청 기록이나 구독 목록 대신 카테고리, 상세 요청, 시청 가능 시간, 시청 목적을 조합해 영상을 선별하고 추천 이유를 제공합니다.

> 프로젝트 기획서: [YouPick 프로젝트 기획서](https://kyeongrak-choi.github.io/post.html?path=posts%2FEncore%2FProject%2FYouPick_%ED%94%84%EB%A1%9C%EC%A0%9D%ED%8A%B8_%EA%B8%B0%ED%9A%8D%EC%84%9C_%EC%B4%88%EC%95%88.md)

## 목표

- YouTube의 기존 개인화 추천과 독립적으로, 한 번의 사용자 요청에 맞는 영상을 추천한다.
- Shorts(기본값: 60초 이하)를 제외하고 시간 제한을 만족하는 영상만 남긴다.
- 역할이 분리된 에이전트를 FastAPI 오케스트레이터가 순서대로 실행한다.
- 같은 조건의 반복 요청은 Redis 캐시로 YouTube API 호출을 줄인다.
- 사이드바에서 YouTube API의 앱 기준 예상 잔여 할당량을 확인한다.
- 검색 이력과 피드백은 Supabase(PostgreSQL)에 저장해 이후 고도화에 활용한다.

## 기술 스택

| 영역 | 선택 기술 | 역할 |
| --- | --- | --- |
| Backend / API | Python, FastAPI | 요청 검증, 추천 워크플로 오케스트레이션, REST API |
| Multi-agent | Python 서비스 계층 | 검색·상세조회·필터·분석·정렬 역할 분리 |
| Frontend | Streamlit | 조건 입력, 추천 결과·이유·상태 표시 |
| 영속 데이터 | Supabase (PostgreSQL) | 검색 이력, 사용자 피드백, 운영 데이터 |
| 캐시 | Redis | 동일 조건 검색 결과 캐싱, API 쿼터 절감 |
| 외부 API | YouTube Data API v3 | 후보 검색과 영상 상세 정보 수집 |

초기 구현에서는 새로운 에이전트 프레임워크를 바로 도입하지 않습니다. 각 에이전트를 Python 클래스 또는 함수로 명확히 나눈 뒤, FastAPI의 `RecommendationOrchestrator`가 실행 순서와 결과를 관리합니다. 이를 통해 멀티 에이전트의 역할 분담과 오케스트레이션을 직접 학습할 수 있습니다.

## 추천 흐름

```text
Streamlit UI
  → FastAPI /api/v1/recommendations
    → Orchestrator Agent
      → Search Agent       : YouTube search.list로 후보 검색
      → Video Detail Agent : videos.list로 길이·태그·통계 조회
      → Filter Agent       : Shorts·시간 제한 제외
      → Analysis Agent     : 요청과 영상의 적합성·추천 이유 분석
      → Ranking Agent      : 점수 계산 및 최종 정렬
    → Redis Cache / Supabase 기록
  → 추천 목록과 추천 이유 표시
```

## 프로젝트 구조

```text
Youpick/
├── backend/                         # FastAPI 서버와 추천 오케스트레이션
│   ├── app/
│   │   ├── api/v1/                  # 라우터 (recommendations, health 등)
│   │   ├── agents/                  # 역할별 에이전트와 오케스트레이터
│   │   ├── core/                    # 설정, 보안, 로깅
│   │   ├── db/                      # Supabase/PostgreSQL 연결 및 모델
│   │   ├── repositories/            # 검색 이력·피드백 데이터 접근
│   │   ├── schemas/                 # Pydantic 요청·응답 모델
│   │   ├── services/                # YouTube, Redis, AI 분석 어댑터
│   │   └── main.py                  # FastAPI 애플리케이션 진입점
│   └── tests/                       # backend 단위·통합 테스트
├── frontend/                        # Streamlit 사용자 화면
│   ├── pages/                       # 검색 이력, 피드백 등 확장 화면
│   ├── components/                  # 조건 폼, 결과 카드, 상태 표시 컴포넌트
│   ├── services/                    # FastAPI 호출 클라이언트
│   └── app.py                       # Streamlit 진입점
├── docs/                            # API 명세, 에이전트 설계, 회고
├── infra/                           # 로컬 Redis·DB 개발 환경 설정
├── tests/                           # E2E/공통 테스트
├── .env.example                     # 필요한 환경 변수 이름만 공유
├── .gitignore
└── README.md
```

현재는 폴더 구조와 문서만 만든 상태입니다. 각 폴더의 `.gitkeep`은 빈 디렉터리도 Git에 유지하기 위한 파일이며, 기능 구현을 시작하면 실제 코드 파일로 대체합니다.

## MVP 범위

### 입력

- 카테고리: 과학, 테크·IT, 경제·주식 등
- 상세 요청: 자연어 검색 문장
- 시간 제한: 예) 10분, 30분, 60분 이내
- 시청 목적: 빠른 요약, 개념 이해, 심층 분석, 실습

### 출력

- 영상 제목, 채널명, 썸네일, 재생 시간, 업로드 날짜
- 사용자 조건과 연결된 추천 이유
- 정렬 점수 또는 적합도(개발용으로 먼저 제공)
- 결과 캐시 여부와 에이전트 처리 상태(학습·디버깅용)

### 제외 범위

- YouTube 로그인, 재생목록 조작, 구독 관리
- 사용자별 장기 개인화 추천
- Shorts 완전 판별: MVP에서는 `contentDetails.duration`이 60초 이하인 영상을 제외

## 에이전트 책임

| 에이전트 | 입력 | 출력 | 책임 |
| --- | --- | --- | --- |
| Orchestrator | 추천 요청 | 최종 추천 응답 | 실행 순서, 실패 처리, 상태 수집 |
| Search Agent | 검색어·카테고리·시간 | 후보 영상 ID | `search.list` 호출과 1차 후보 수집 |
| Video Detail Agent | 영상 ID 목록 | 영상 상세 목록 | `videos.list`로 길이·태그·통계 보강 |
| Filter Agent | 영상 상세·시간 제한 | 필터링된 영상 | Shorts 및 시간 초과 영상 제외 |
| Analysis Agent | 요청 조건·영상 정보 | 적합도·추천 이유 | 요청과 영상의 의미적 적합성 평가 |
| Ranking Agent | 분석 결과 | 정렬된 추천 목록 | 적합도와 보조 지표를 조합해 순위 결정 |

## 데이터와 캐시 설계 초안

- Redis 키 예시: `recommendations:{category}:{duration}:{purpose}:{request_hash}`
- Redis 값: 최종 추천 결과와 생성 시각. TTL은 개발 초기에 30분으로 시작한다.
- Supabase 테이블 후보:
  - `search_requests`: 입력 조건, 요청 시각, 처리 시간, 캐시 히트 여부
  - `recommendations`: 요청별 추천 영상과 순위, 점수, 추천 이유
- `feedback`: 추천 결과에 대한 유용함 평가와 선택 이유
- 비밀 값(YouTube API 키, Supabase 키)은 `.env`에만 저장하며 Git에 올리지 않는다.

Supabase 영속화 스키마는 [001_initial_schema.sql](backend/supabase/migrations/001_initial_schema.sql)에 있습니다. Supabase SQL Editor에서 한 번 실행한 후 `backend/.env`에 `SUPABASE_URL`과 `SUPABASE_SECRET_KEY`를 설정하면, 추천 요청과 결과가 자동으로 저장됩니다. 기존 `SUPABASE_SERVICE_ROLE_KEY`도 호환되지만 새 프로젝트에서는 Secret key 사용을 권장합니다. 이 키는 백엔드에서만 사용하며 Streamlit 등 프론트엔드에는 절대 전달하지 않습니다.

추천 결과의 유용함 평가는 `POST /api/v1/feedback`으로 보냅니다. 사용 전에 [002_feedback.sql](backend/supabase/migrations/002_feedback.sql)을 SQL Editor에서 실행해야 합니다.

```json
{
  "recommendation_id": "추천 결과의 UUID",
  "is_helpful": true,
  "comment": "실습에 도움이 됐어요."
}
```

## 환경 변수

`backend/.env.example`을 복사해 `backend/.env`를 만든 후 실제 값을 입력합니다.

```bash
cp backend/.env.example backend/.env
```

| 변수 | 설명 |
| --- | --- |
| `YOUTUBE_API_KEY` | YouTube Data API v3 키 |
| `YOUTUBE_DAILY_QUOTA_LIMIT` | 일일 할당량 기준값. 기본값은 10,000유닛 |
| `GOOGLE_OAUTH_CLIENT_ID` | Google 로그인용 OAuth Client ID. Streamlit 설정과 같은 값 |
| `SUPABASE_URL` | Supabase 프로젝트 URL |
| `SUPABASE_KEY` | Supabase 서버용 키 |
| `REDIS_URL` | Redis 연결 URL. 예: `redis://localhost:6379/0` |
| `BACKEND_URL` | Streamlit이 호출할 FastAPI 주소 |

`backend/.env`의 `CORS_ORIGINS`에는 브라우저에서 API를 호출할 프론트엔드 주소를 쉼표로 구분해 설정합니다. 로컬 Streamlit 기본 주소는 이미 예시에 포함되어 있습니다.

### YouTube API 잔여 할당량

YouTube Data API는 API 응답에 남은 일일 할당량을 직접 제공하지 않습니다. 따라서 YouPick은 앱이 발생시킨 `search.list` 호출은 100유닛, `videos.list` 호출은 1유닛으로 누적해 사이드바에 **예상 잔여량**을 표시합니다. Redis를 설정했다면 서버 재시작 뒤에도 같은 날의 사용량이 유지됩니다. Google Cloud Console, 다른 앱 또는 직접 실행한 호출은 포함되지 않으므로 Console의 실제 수치와 차이가 날 수 있습니다. 기준 일자는 YouTube의 일일 쿼터가 초기화되는 미국 태평양 시간입니다.

### Google 로그인과 계정별 대화 이력

YouPick은 Streamlit의 Google OIDC 로그인으로 받은 Google ID 토큰을 FastAPI가 검증하고, Google 계정의 고유 식별자(`sub`)로 Supabase 이력을 분리합니다. 비밀 값은 Git에 올리지 않습니다.

1. Google Cloud Console의 **OAuth 동의 화면**을 설정하고, **사용자 인증 정보 → OAuth 클라이언트 ID → 웹 애플리케이션**을 만듭니다.
2. 승인된 리디렉션 URI에 `http://localhost:8501/oauth2callback`을 추가합니다. 배포한다면 실제 서비스 주소의 `/oauth2callback`도 추가합니다.
3. `backend/.env`에 OAuth 클라이언트 ID를 넣습니다.

   ```env
   GOOGLE_OAUTH_CLIENT_ID=...apps.googleusercontent.com
   ```

4. `frontend/.streamlit/secrets.toml.example`을 `frontend/.streamlit/secrets.toml`으로 복사한 뒤, `client_id`, `client_secret`, `cookie_secret`을 입력합니다. `cookie_secret`은 충분히 긴 임의 문자열을 사용합니다.
5. Supabase SQL Editor에서 [005_google_account_history.sql](backend/supabase/migrations/005_google_account_history.sql)을 실행합니다.

로그인 후 새로 요청한 추천과 대화는 계정별로 저장되며, 다른 브라우저나 새 세션에서도 왼쪽 **대화 이력**에서 다시 열 수 있습니다. Google 로그인 ID 토큰은 짧은 유효기간이 있으므로 만료되면 다시 로그인하면 됩니다.

## 구현 순서 제안

1. `schemas`와 `/health`, `/recommendations` API 계약을 먼저 정의한다.
2. YouTube 검색·상세 조회 서비스를 만들고, 샘플 응답으로 단위 테스트를 작성한다.
3. Filter Agent와 단순 키워드 기반 Ranking Agent를 구현한다.
4. Orchestrator에서 각 에이전트를 연결하고 Redis 캐시를 추가한다.
5. Streamlit에서 입력 폼과 추천 카드 화면을 만든다.
6. Supabase에 검색 이력과 피드백을 저장한다.
7. Analysis Agent를 LLM 또는 임베딩 기반으로 고도화하고, 점수·이유를 개선한다.

## 백엔드 실행

백엔드 구현을 완료했습니다. Python 3.11 이상과 [uv](https://docs.astral.sh/uv/)가 필요합니다.

```bash
cd backend
uv sync --extra dev
cp .env.example .env
uv run uvicorn app.main:app --reload
```

```bash
# 별도 터미널: 상태 확인
curl http://127.0.0.1:8000/health

# YOUTUBE_API_KEY 설정 후 추천 요청
curl -X POST http://127.0.0.1:8000/api/v1/recommendations \
  -H 'Content-Type: application/json' \
  -d '{"category":"테크·IT","detail_request":"FastAPI와 Supabase 로그인 구현","max_duration_minutes":30,"purpose":"practice"}'

# 테스트
cd backend && uv run pytest
```

## 프론트엔드 실행

별도 터미널에서 실행합니다.

```bash
cd frontend
python3 -m venv .venv
.venv/bin/pip install -e .
cp .env.example .env
.venv/bin/streamlit run app.py
```

프론트엔드 `.env`에는 `BACKEND_URL`만 둡니다. YouTube·Supabase 비밀 키는 반드시 `backend/.env`에만 둡니다.

## 참고

- [YouTube Data API - search.list](https://developers.google.com/youtube/v3/docs/search/list)
- [YouTube Data API - Quota Calculator](https://developers.google.com/youtube/v3/determine_quota_cost)
