from __future__ import annotations

from fastapi import APIRouter

from stock_service.schemas.responses import ApiResponse


router = APIRouter(tags=["health"])


@router.get("/api/health", response_model=ApiResponse)
async def health() -> ApiResponse:
    from stock_service.db.database import DATABASE_URL
    return ApiResponse(data={"ready": True, "db": DATABASE_URL.split("@")[1] if "@" in DATABASE_URL else DATABASE_URL})
