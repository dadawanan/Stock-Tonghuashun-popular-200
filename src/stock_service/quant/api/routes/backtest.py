from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from stock_service.api.dependencies import get_current_user, get_session
from stock_service.crud import quant_crud
from stock_service.quant.application.backtest_engine import BacktestEngine
from stock_service.quant.application.strategy_engine import engine as _strategy_engine
from stock_service.quant.domain.backtest_rules import BacktestConfig
from stock_service.quant.schemas import BacktestRequest
from stock_service.schemas.responses import ApiResponse

router = APIRouter(prefix="/api/quant/backtest", tags=["quant-backtest"])


@router.post("/async/run", response_model=ApiResponse)
async def async_run_backtest(
    req: BacktestRequest,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user),
):
    """异步提交回测任务，立即返回 task_id"""
    strategy = await quant_crud.get_strategy(session, req.strategy_id)
    if not strategy:
        raise HTTPException(404, "Strategy not found")

    codes = req.stock_codes
    if not codes:
        from stock_service.quant.infrastructure.analysis_adapter import AnalysisAdapter
        adapter = AnalysisAdapter(session)
        codes = await adapter.get_latest_popularity_codes()

    if not codes:
        raise HTTPException(400, "No stock codes provided or found")

    user_id = current_user.id

    task = await quant_crud.create_task(session, {
        "task_type": "backtest",
        "status": "pending",
        "params": {
            "strategy_id": req.strategy_id,
            "stock_codes": codes,
            "start_date": req.start_date.isoformat(),
            "end_date": req.end_date.isoformat(),
            "initial_capital": req.initial_capital,
            "commission_rate": req.commission_rate,
            "stamp_tax": req.stamp_tax,
            "slippage": req.slippage,
            "max_position_pct": req.max_position_pct,
            "max_holdings": req.max_holdings,
            "stop_loss_pct": req.stop_loss_pct,
        },
        "user_id": user_id,
    })
    await session.commit()

    from stock_service.quant.tasks import run_backtest_task
    try:
        celery_result = run_backtest_task.delay(task["id"], task["params"])
    except Exception as exc:
        # Broker unreachable — mark task as failed so it doesn't sit in 'pending' forever
        await quant_crud.update_task_error(session, task["id"], f"Celery dispatch failed: {exc}")
        await session.commit()
        raise HTTPException(503, f"Task queue unavailable: {exc}")

    # 更新 celery_task_id
    await quant_crud.update_task_status(session, task["id"], "pending",
                                        celery_task_id=celery_result.id)
    await session.commit()

    return ApiResponse(code=0, msg="ok", data={
        "task_id": task["id"],
        "celery_task_id": celery_result.id,
        "status": "pending",
    })


@router.post("/run", response_model=ApiResponse)
async def run_backtest(
    req: BacktestRequest,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    strategy = await quant_crud.get_strategy(session, req.strategy_id)
    if not strategy:
        raise HTTPException(404, "Strategy not found")

    codes = req.stock_codes
    if not codes:
        from stock_service.quant.infrastructure.analysis_adapter import AnalysisAdapter
        adapter = AnalysisAdapter(session)
        codes = await adapter.get_latest_popularity_codes()

    if not codes:
        raise HTTPException(400, "No stock codes provided or found")

    engine = BacktestEngine(session)
    config = BacktestConfig(
        initial_capital=req.initial_capital,
        commission_rate=req.commission_rate,
        stamp_tax=req.stamp_tax,
        slippage=req.slippage,
        max_position_pct=req.max_position_pct,
        max_holdings=req.max_holdings,
        stop_loss_pct=req.stop_loss_pct,
    )

    result = await engine.run(
        strategy_id=req.strategy_id,
        stock_codes=codes,
        start_date=req.start_date,
        end_date=req.end_date,
        config=config,
        strategy_engine=_strategy_engine,
    )
    return ApiResponse(code=0, msg="ok", data=result)


@router.get("/results", response_model=ApiResponse)
async def list_results(
    strategy_id: int | None = None,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    results = await quant_crud.list_backtest_results(session, strategy_id)
    return ApiResponse(code=0, msg="ok", data=results)


@router.get("/results/{backtest_id}", response_model=ApiResponse)
async def get_result(
    backtest_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    result = await quant_crud.get_backtest_result(session, backtest_id)
    if not result:
        raise HTTPException(404, "Backtest result not found")
    return ApiResponse(code=0, msg="ok", data=result)


@router.get("/results/{backtest_id}/trades", response_model=ApiResponse)
async def get_trades(
    backtest_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    trades = await quant_crud.get_backtest_trades(session, backtest_id)
    return ApiResponse(code=0, msg="ok", data=trades)


@router.get("/results/{backtest_id}/nav", response_model=ApiResponse)
async def get_nav(
    backtest_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    nav = await quant_crud.get_backtest_nav(session, backtest_id)
    return ApiResponse(code=0, msg="ok", data=nav)


@router.delete("/results/{backtest_id}", response_model=ApiResponse)
async def delete_result(
    backtest_id: int,
    session: AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user),
):
    ok = await quant_crud.delete_backtest_result(session, backtest_id)
    if not ok:
        raise HTTPException(404, "Backtest result not found")
    return ApiResponse(code=0, msg="ok")


@router.post("/results/batch-delete", response_model=ApiResponse)
async def batch_delete_results(
    ids: list[int],
    session: AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user),
):
    if not ids:
        raise HTTPException(400, "No IDs provided")
    count = await quant_crud.batch_delete_backtest_results(session, ids)
    return ApiResponse(code=0, msg="ok", data={"deleted": count})
