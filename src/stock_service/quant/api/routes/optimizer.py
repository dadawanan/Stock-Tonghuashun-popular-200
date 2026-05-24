"""策略参数优化 API"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from stock_service.api.dependencies import get_current_user, get_session
from stock_service.quant.application.optimizer import ParameterOptimizer
from stock_service.quant.domain.backtest_rules import BacktestConfig
from stock_service.schemas.responses import ApiResponse

router = APIRouter(prefix="/api/quant/optimizer", tags=["quant-optimizer"])


class GridSearchRequest(BaseModel):
    strategy_id: int
    param_grid: dict[str, list]
    stock_codes: list[str] | None = None
    start_date: date
    end_date: date
    initial_capital: float = 1_000_000
    metric: str = "sharpe_ratio"
    top_n: int = 5


@router.post("/grid-search", response_model=ApiResponse)
async def grid_search(
    req: GridSearchRequest,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user),
):
    """Run grid search optimization for strategy parameters."""
    optimizer = ParameterOptimizer(session)

    config = BacktestConfig(initial_capital=req.initial_capital)

    try:
        results = await optimizer.grid_search(
            strategy_id=req.strategy_id,
            param_grid=req.param_grid,
            stock_codes=req.stock_codes or [],
            start_date=req.start_date,
            end_date=req.end_date,
            config=config,
            metric=req.metric,
            top_n=req.top_n,
        )

        data = [
            {
                "params": r.params,
                "metrics": r.metrics,
                "backtest_id": r.backtest_id,
            }
            for r in results
        ]

        return ApiResponse(code=0, msg="ok", data=data)
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/suggest/{strategy_type}", response_model=ApiResponse)
async def suggest_params(
    strategy_type: str,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user),
):
    """Get suggested parameter ranges for a strategy type."""
    optimizer = ParameterOptimizer(session)
    params = optimizer.suggest_params(strategy_type)
    return ApiResponse(code=0, msg="ok", data=params)
