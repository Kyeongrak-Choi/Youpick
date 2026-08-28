"""Google ID-token validation for requests originating from the Streamlit UI."""

from dataclasses import dataclass

import httpx
from fastapi import Header, HTTPException, status

from app.core.config import get_settings


@dataclass(frozen=True)
class CurrentUser:
    id: str
    email: str | None
    name: str | None


async def get_current_user(authorization: str | None = Header(default=None)) -> CurrentUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google 로그인이 필요합니다.")
    settings = get_settings()
    if not settings.google_oauth_client_id:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="GOOGLE_OAUTH_CLIENT_ID is not configured.")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(
                "https://oauth2.googleapis.com/tokeninfo",
                params={"id_token": authorization.removeprefix("Bearer ")},
            )
            response.raise_for_status()
            claims = response.json()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Google 로그인 정보를 확인할 수 없습니다.") from exc
    if claims.get("aud") != settings.google_oauth_client_id or str(claims.get("email_verified")).lower() != "true":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="유효하지 않은 Google 로그인입니다.")
    return CurrentUser(id=claims["sub"], email=claims.get("email"), name=claims.get("name"))
