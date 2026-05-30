from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from stock_service.api.dependencies import get_current_user, get_session
from stock_service.crud import quant_crud, v2_crud
from stock_service.quant.application import strategy_engine
from stock_service.quant.domain.strategy_interface import StrategyContext
from stock_service.quant.infrastructure.analysis_adapter import AnalysisAdapter
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


class SignalPreviewRequest(BaseModel):
    strategy_ids: list[int] | None = None
    max_stocks: int = 50


@router.post("/signals/preview", response_model=ApiResponse)
async def preview_signals(
    req: SignalPreviewRequest,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """手动触发策略信号预览：用最新人气榜数据跑策略，返回信号不执行交易"""
    strategies = await quant_crud.list_strategies(session)
    if req.strategy_ids:
        strategies = [s for s in strategies if s["id"] in req.strategy_ids]
    if not strategies:
        raise HTTPException(400, "没有可用的策略")

    # 获取人气榜 Top N 股票
    snapshots = await v2_crud.get_latest_popularity_snapshot(session)
    stock_codes = [s["stock_code"] for s in snapshots[:req.max_stocks]]
    if not stock_codes:
        raise HTTPException(400, "没有人气榜数据，请先运行人气榜采集")

    # 使用人气榜股票覆盖最多的交易日（而非全局最新，可能只有少量数据）
    from sqlalchemy import func, select, text
    from stock_service.db.models.quant_models import StockDaily

    latest_date_row = await session.execute(text("""
        SELECT sd.trade_date, COUNT(DISTINCT sd.code) as cnt
        FROM stock_daily sd
        WHERE sd.code IN (
            SELECT stock_code FROM popularity_snapshot
            WHERE trade_date = (SELECT MAX(trade_date) FROM popularity_snapshot)
        )
        AND sd.trade_date >= CURRENT_DATE - INTERVAL '7 days'
        GROUP BY sd.trade_date
        ORDER BY cnt DESC
        LIMIT 1
    """))
    row = latest_date_row.first()
    trade_date = row[0] if row else None
    if not trade_date:
        raise HTTPException(400, "没有行情数据，请先运行数据补全")

    # 填充上下文数据
    # 优先从 market_snapshot 获取实时数据（pct_change/volume_ratio/main_net_inflow）
    # 再从 stock_daily 补充 OHLCV
    market_snapshot = await v2_crud.get_latest_market_snapshot(session)

    market_data: dict[str, dict] = {}
    indicators: dict[str, dict] = {}
    for code in stock_codes:
        data: dict = {}
        # 从 stock_daily 获取 OHLCV
        daily = await quant_crud.get_stock_daily(session, code, start_date=trade_date, end_date=trade_date)
        if daily:
            data.update({
                k: float(v) if isinstance(v, Decimal) else v
                for k, v in daily[0].items()
            })
        # 从 market_snapshot 补充实时字段（覆盖 stock_daily 中可能缺失的字段）
        snap = market_snapshot.get(code)
        if snap:
            data.update(snap)
        if data:
            market_data[code] = data

        ind = await quant_crud.get_stock_indicator(session, code)
        if ind:
            indicators[code] = {
                k: float(v) for k, v in ind.items()
                if isinstance(v, (int, float, Decimal)) and k not in ("id",)
            }

    adapter = AnalysisAdapter(session)
    analysis = await adapter.get_analysis_signals(stock_codes)

    popularity = await quant_crud.get_latest_popularity_data(session)

    context = StrategyContext(
        trade_date=trade_date,
        market_data=market_data,
        indicators=indicators,
        analysis=analysis,
        popularity=popularity,
        positions={},
    )

    # 运行所有策略
    all_signals: dict[str, dict[str, list]] = {}
    strategy_results: dict[str, list] = {}

    for strat_info in strategies:
        strat_type = strat_info["type"]
        strat_name = strat_info["name"]
        strat_params = strat_info.get("params") or {}

        strategy = strategy_engine.engine._strategies.get(strat_type)
        if not strategy:
            continue

        strategy.set_params(strat_params)
        signals = await strategy.generate_signals(stock_codes, context)
        strategy_results[strat_name] = [
            {"code": s.code, "type": s.signal_type.value, "score": s.score, "reason": s.reason}
            for s in signals
        ]

        for signal in signals:
            if signal.code not in all_signals:
                all_signals[signal.code] = {"buy": [], "sell": []}
            direction = signal.signal_type.value
            all_signals[signal.code][direction].append(signal)

    # 汇总共识信号
    consensus = []
    for code, directions in all_signals.items():
        buy_count = len(directions["buy"])
        sell_count = len(directions["sell"])
        if buy_count == len(strategies):
            avg_score = sum(s.score for s in directions["buy"]) / buy_count
            consensus.append({
                "code": code,
                "direction": "buy",
                "score": round(avg_score, 4),
                "strategies": [s.reason for s in directions["buy"]],
            })
        if sell_count == len(strategies):
            avg_score = sum(s.score for s in directions["sell"]) / sell_count
            consensus.append({
                "code": code,
                "direction": "sell",
                "score": round(avg_score, 4),
                "strategies": [s.reason for s in directions["sell"]],
            })

    return ApiResponse(code=0, msg="ok", data={
        "trade_date": str(trade_date),
        "stock_count": len(stock_codes),
        "strategy_count": len(strategies),
        "strategy_names": [s["name"] for s in strategies],
        "strategy_signals": strategy_results,
        "consensus_signals": consensus,
        "total_signals": sum(len(v) for v in strategy_results.values()),
    })
