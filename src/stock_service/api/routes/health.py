from __future__ import annotations

from fastapi import APIRouter

from stock_service.api.dependencies import get_db
from stock_service.schemas.responses import ApiResponse


router = APIRouter(tags=["health"])


@router.get("/api/health", response_model=ApiResponse)
async def health() -> ApiResponse:
    try:
        db = await get_db()
        async with db.pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return ApiResponse(data={"ready": True})
    except Exception as exc:
        return ApiResponse(code=1, msg=str(exc), data={"ready": False})

