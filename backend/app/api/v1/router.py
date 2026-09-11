from fastapi import APIRouter

from app.api.v1.recommendations import router as recommendations_router
from app.api.v1.feedback import router as feedback_router
from app.api.v1.quota import router as quota_router
from app.api.v1.history import router as history_router
from app.api.v1.dashboard import router as dashboard_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(recommendations_router)
api_router.include_router(feedback_router)
api_router.include_router(quota_router)
api_router.include_router(history_router)
api_router.include_router(dashboard_router)
