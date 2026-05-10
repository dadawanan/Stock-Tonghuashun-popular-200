from __future__ import annotations

from fastapi import APIRouter

from stock_service.schemas.responses import ApiResponse


router = APIRouter(tags=["health"])


@router.get("/api/health", response_model=ApiResponse)
async def health() -> ApiResponse:
    return ApiResponse(data={"ready": True})
