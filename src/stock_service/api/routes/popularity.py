from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from stock_service.api.dependencies import get_session
from stock_service.application.services.popularity_service import compare_stock_sets, run_popularity_pipeline
from stock_service.crud import v2_crud
from stock_service.schemas.responses import ApiResponse


logger = logging.getLogger("stock-api")
router = APIRouter(tags=["popularity"])


@router.post("/api/popularity/fetch", response_model=ApiResponse)
async def api_popularity_fetch() -> ApiResponse:
    try:
        return ApiResponse(data=await run_popularity_pipeline())
    except Exception as exc:
        logger.exception("popularity fetch 失败")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/api/popularity/latest", response_model=ApiResponse)
async def api_popularity_latest(
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    try:
        rows = await v2_crud.get_latest_popularity_snapshot(session)
        return ApiResponse(
            data={
                "snapshot_time": rows[0]["snapshot_time"] if rows else None,
                "count": len(rows),
                "stocks": rows,
            }
        )
    except Exception as exc:
        logger.exception("查询 latest popularity 失败")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/api/popularity/compare-latest", response_model=ApiResponse)
async def api_popularity_compare_latest(
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    try:
        snapshot_times = await v2_crud.get_latest_popularity_snapshot_times(session, limit=2)
        if len(snapshot_times) < 2:
            raise HTTPException(status_code=400, detail="至少需要两次榜单快照才能比较")
        current_rows = await v2_crud.get_popularity_snapshot_by_time(session, snapshot_times[0])
        previous_rows = await v2_crud.get_popularity_snapshot_by_time(session, snapshot_times[1])
        return ApiResponse(
            data={
                "current_snapshot_time": snapshot_times[0],
                "previous_snapshot_time": snapshot_times[1],
                **compare_stock_sets(previous_rows, current_rows),
            }
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("compare latest popularity 失败")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/api/fetch", response_model=ApiResponse)
async def api_fetch() -> ApiResponse:
    return await api_popularity_fetch()
