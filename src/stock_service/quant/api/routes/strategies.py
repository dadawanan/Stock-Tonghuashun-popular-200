from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from stock_service.api.dependencies import get_current_user, get_session
from stock_service.crud import quant_crud
from stock_service.quant.schemas import (
    StrategyCreate, StrategyUpdate, StrategyResponse,
)
from stock_service.schemas.responses import ApiResponse

router = APIRouter(prefix="/api/quant/strategies", tags=["quant-strategies"])


@router.get("/", response_model=ApiResponse)
async def list_strategies(
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    strategies = await quant_crud.list_strategies(session)
    return ApiResponse(code=0, msg="ok", data=strategies)


@router.post("/", response_model=ApiResponse)
async def create_strategy(
    req: StrategyCreate,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    strategy = await quant_crud.create_strategy(session, {
        "name": req.name,
        "type": req.type,
        "params": req.params,
        "description": req.description,
    })
    return ApiResponse(code=0, msg="ok", data=strategy)


@router.get("/{strategy_id}", response_model=ApiResponse)
async def get_strategy(
    strategy_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    strategy = await quant_crud.get_strategy(session, strategy_id)
    if not strategy:
        raise HTTPException(404, "Strategy not found")
    return ApiResponse(code=0, msg="ok", data=strategy)


@router.put("/{strategy_id}", response_model=ApiResponse)
async def update_strategy(
    strategy_id: int,
    req: StrategyUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    data = req.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(400, "No fields to update")
    strategy = await quant_crud.update_strategy(session, strategy_id, data)
    if not strategy:
        raise HTTPException(404, "Strategy not found")
    return ApiResponse(code=0, msg="ok", data=strategy)


@router.delete("/{strategy_id}", response_model=ApiResponse)
async def delete_strategy(
    strategy_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    ok = await quant_crud.delete_strategy(session, strategy_id)
    if not ok:
        raise HTTPException(404, "Strategy not found")
    return ApiResponse(code=0, msg="ok")
