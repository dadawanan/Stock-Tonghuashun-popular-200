from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from stock_service.api.dependencies import get_current_user, get_session
from stock_service.crud import quant_crud
from stock_service.quant.application.feedback_service import FeedbackService
from stock_service.quant.schemas import WeightAdjustmentRequest
from stock_service.schemas.responses import ApiResponse

router = APIRouter(prefix="/api/quant/feedback", tags=["quant-feedback"])


@router.get("/insights/{backtest_id}", response_model=ApiResponse)
async def get_insights(
    backtest_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    service = FeedbackService(session)
    try:
        insights = await service.analyze_backtest_insights(backtest_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return ApiResponse(code=0, msg="ok", data=insights)


@router.get("/suggestions/{backtest_id}", response_model=ApiResponse)
async def get_suggestions(
    backtest_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    service = FeedbackService(session)
    suggestions = await service.suggest_weight_adjustment(backtest_id)
    return ApiResponse(code=0, msg="ok", data=suggestions)


@router.post("/apply-weight", response_model=ApiResponse)
async def apply_weight(
    req: WeightAdjustmentRequest,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    strategy = await quant_crud.get_strategy(session, req.strategy_id)
    if not strategy:
        raise HTTPException(404, "Strategy not found")

    old_params = strategy.get("params") or {}
    weights = old_params.get("weights", {})
    weights.update(req.adjustments)
    new_params = {**old_params, "weights": weights}

    await quant_crud.update_strategy(session, req.strategy_id, {"params": new_params})
    return ApiResponse(code=0, msg="ok", data={"updated_params": new_params})
