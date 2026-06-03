"""策略参数优化 API"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from stock_service.api.dependencies import get_current_user, get_session
from stock_service.crud import quant_crud
from stock_service.quant.application.optimizer import ParameterOptimizer, WalkForwardResult
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


class WalkForwardRequest(BaseModel):
    strategy_id: int
    param_grid: dict[str, list]
    stock_codes: list[str] | None = None
    start_date: date
    end_date: date
    train_days: int = 180
    test_days: int = 60
    step_days: int = 60
    initial_capital: float = 1_000_000
    metric: str = "sharpe_ratio"


@router.post("/walk-forward", response_model=ApiResponse)
async def walk_forward(
    req: WalkForwardRequest,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user),
):
    """滚动前进优化：在多个滚动窗口上训练+测试，防止过拟合"""
    optimizer = ParameterOptimizer(session)
    config = BacktestConfig(initial_capital=req.initial_capital)

    try:
        result: WalkForwardResult = await optimizer.walk_forward(
            strategy_id=req.strategy_id,
            param_grid=req.param_grid,
            stock_codes=req.stock_codes or [],
            start_date=req.start_date,
            end_date=req.end_date,
            train_days=req.train_days,
            test_days=req.test_days,
            step_days=req.step_days,
            config=config,
            metric=req.metric,
        )

        data = {
            "windows": [
                {
                    "window_id": w.window_id,
                    "train_period": f"{w.train_start} ~ {w.train_end}",
                    "test_period": f"{w.test_start} ~ {w.test_end}",
                    "best_params": w.best_params,
                    "train_metrics": w.train_metrics,
                    "test_metrics": w.test_metrics,
                }
                for w in result.windows
            ],
            "avg_test_metrics": result.avg_test_metrics,
            "best_params_per_window": result.best_params_per_window,
            "stability_score": result.stability_score,
        }

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


@router.post("/async/grid-search", response_model=ApiResponse)
async def async_grid_search(
    req: GridSearchRequest,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user),
):
    """异步提交网格搜索任务，立即返回 task_id"""
    # 验证策略存在
    strategy = await quant_crud.get_strategy(session, req.strategy_id)
    if not strategy:
        raise HTTPException(404, "Strategy not found")

    # 解析股票代码
    codes = req.stock_codes
    if not codes:
        from stock_service.quant.infrastructure.analysis_adapter import AnalysisAdapter
        adapter = AnalysisAdapter(session)
        codes = await adapter.get_latest_popularity_codes()
    if not codes:
        raise HTTPException(400, "No stock codes provided or found")

    user_id = current_user.id

    task = await quant_crud.create_task(session, {
        "task_type": "grid_search",
        "status": "pending",
        "params": {
            "strategy_id": req.strategy_id,
            "param_grid": req.param_grid,
            "stock_codes": codes,
            "start_date": req.start_date.isoformat(),
            "end_date": req.end_date.isoformat(),
            "initial_capital": req.initial_capital,
            "metric": req.metric,
            "top_n": req.top_n,
        },
        "user_id": user_id,
    })
    await session.commit()

    from stock_service.quant.tasks import run_grid_search_task
    try:
        celery_result = run_grid_search_task.delay(task["id"], task["params"])
    except Exception as exc:
        await quant_crud.update_task_error(session, task["id"], f"Celery dispatch failed: {exc}")
        await session.commit()
        raise HTTPException(503, f"Task queue unavailable: {exc}")

    await quant_crud.update_task_status(session, task["id"], "pending",
                                        celery_task_id=celery_result.id)
    await session.commit()

    return ApiResponse(code=0, msg="ok", data={
        "task_id": task["id"],
        "celery_task_id": celery_result.id,
        "status": "pending",
    })


@router.post("/async/walk-forward", response_model=ApiResponse)
async def async_walk_forward(
    req: WalkForwardRequest,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user),
):
    """异步提交滚动前进优化任务，立即返回 task_id"""
    # 验证策略存在
    strategy = await quant_crud.get_strategy(session, req.strategy_id)
    if not strategy:
        raise HTTPException(404, "Strategy not found")

    # 解析股票代码
    codes = req.stock_codes
    if not codes:
        from stock_service.quant.infrastructure.analysis_adapter import AnalysisAdapter
        adapter = AnalysisAdapter(session)
        codes = await adapter.get_latest_popularity_codes()
    if not codes:
        raise HTTPException(400, "No stock codes provided or found")

    user_id = current_user.id

    task = await quant_crud.create_task(session, {
        "task_type": "walk_forward",
        "status": "pending",
        "params": {
            "strategy_id": req.strategy_id,
            "param_grid": req.param_grid,
            "stock_codes": codes,
            "start_date": req.start_date.isoformat(),
            "end_date": req.end_date.isoformat(),
            "train_days": req.train_days,
            "test_days": req.test_days,
            "step_days": req.step_days,
            "initial_capital": req.initial_capital,
            "metric": req.metric,
        },
        "user_id": user_id,
    })
    await session.commit()

    from stock_service.quant.tasks import run_walk_forward_task
    try:
        celery_result = run_walk_forward_task.delay(task["id"], task["params"])
    except Exception as exc:
        await quant_crud.update_task_error(session, task["id"], f"Celery dispatch failed: {exc}")
        await session.commit()
        raise HTTPException(503, f"Task queue unavailable: {exc}")

    await quant_crud.update_task_status(session, task["id"], "pending",
                                        celery_task_id=celery_result.id)
    await session.commit()

    return ApiResponse(code=0, msg="ok", data={
        "task_id": task["id"],
        "celery_task_id": celery_result.id,
        "status": "pending",
    })
