from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.v1.dependencies import get_recommendation_orchestrator
from app.main import app


def test_health_check() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_recommendations_require_youtube_key() -> None:
    def missing_key() -> None:
        raise HTTPException(status_code=503, detail="YOUTUBE_API_KEY is not configured")

    app.dependency_overrides[get_recommendation_orchestrator] = missing_key
    try:
        response = TestClient(app).post(
            "/api/v1/recommendations",
            json={
                "category": "테크·IT",
                "detail_request": "FastAPI Supabase 로그인",
                "max_duration_minutes": 30,
                "purpose": "practice",
            },
        )
        assert response.status_code == 503
    finally:
        app.dependency_overrides.clear()
