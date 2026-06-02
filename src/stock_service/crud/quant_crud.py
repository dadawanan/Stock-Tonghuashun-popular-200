from datetime import date

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from stock_service.crud.utils import _rows_to_dicts
from stock_service.db.models.quant_models import (
    BacktestDailyNav,
    BacktestResult,
    BacktestTrade,
    FeedbackLog,
    PendingOrder,
    PositionAccount,
    PositionDailySnapshot,
    SimAccount,
    StockBasic,
    StockDaily,
    StockIndicator,
    Strategy,
    StrategyPick,
    TradeOrder,
)
from stock_service.db.models.v2_models import StockMaster


# ── StockBasic ──


async def get_stock_basic_by_code(session: AsyncSession, code: str) -> dict | None:
    result = await session.execute(select(StockBasic).where(StockBasic.code == code))
    row = result.scalars().first()
    if row is None:
        return None
    return _rows_to_dicts([row])[0]


async def list_stock_basic(session: AsyncSession, *, market: str | None = None) -> list[dict]:
    stmt = select(StockBasic)
    if market:
        stmt = stmt.where(StockBasic.market == market)
    result = await session.execute(stmt.order_by(StockBasic.code))
    return _rows_to_dicts(result.scalars().all())


# ── StockDaily ──


async def get_stock_daily(
    session: AsyncSession, code: str, *, start_date: date | None = None, end_date: date | None = None
) -> list[dict]:
    stmt = select(StockDaily).where(StockDaily.code == code)
    if start_date:
        stmt = stmt.where(StockDaily.trade_date >= start_date)
    if end_date:
        stmt = stmt.where(StockDaily.trade_date <= end_date)
    result = await session.execute(stmt.order_by(StockDaily.trade_date.desc()))
    return _rows_to_dicts(result.scalars().all())


# ── StockIndicator ──


async def get_stock_indicator(session: AsyncSession, code: str, *, trade_date: date | None = None) -> dict | None:
    stmt = select(StockIndicator).where(StockIndicator.code == code)
    if trade_date:
        stmt = stmt.where(StockIndicator.trade_date == trade_date)
    stmt = stmt.order_by(StockIndicator.trade_date.desc()).limit(1)
    result = await session.execute(stmt)
    row = result.scalars().first()
    if row is None:
        return None
    return _rows_to_dicts([row])[0]


# ── StrategyPick ──


async def list_strategy_picks(session: AsyncSession, strategy_id: int) -> list[dict]:
    result = await session.execute(
        select(StrategyPick)
        .where(StrategyPick.strategy_id == strategy_id)
        .order_by(StrategyPick.trade_date.desc())
    )
    return _rows_to_dicts(result.scalars().all())


# ── BacktestResult ──


async def list_backtest_results(
    session: AsyncSession, strategy_id: int | None = None
) -> list[dict]:
    stmt = select(BacktestResult)
    if strategy_id is not None:
        stmt = stmt.where(BacktestResult.strategy_id == strategy_id)
    result = await session.execute(stmt.order_by(BacktestResult.created_at.desc()))
    return _rows_to_dicts(result.scalars().all())


# ── TradeOrder ──


async def list_trade_orders(session: AsyncSession, account_id: int) -> list[dict]:
    result = await session.execute(
        select(
            TradeOrder,
            StockMaster.stock_name,
        )
        .outerjoin(StockMaster, TradeOrder.code == StockMaster.stock_code)
        .where(TradeOrder.account_id == account_id)
        .order_by(TradeOrder.created_at.desc())
    )
    rows = []
    for order, stock_name in result.all():
        row = {c.name: getattr(order, c.name) for c in order.__table__.columns}
        row["stock_name"] = stock_name
        rows.append(row)
    return rows


# ── PositionAccount ──


async def get_positions(session: AsyncSession, account_id: int) -> list[dict]:
    result = await session.execute(
        select(
            PositionAccount,
            StockMaster.stock_name,
        )
        .outerjoin(StockMaster, PositionAccount.code == StockMaster.stock_code)
        .where(PositionAccount.account_id == account_id)
    )
    rows = []
    for pos, stock_name in result.all():
        row = {c.name: getattr(pos, c.name) for c in pos.__table__.columns}
        row["stock_name"] = stock_name
        rows.append(row)
    return rows


async def get_position(session: AsyncSession, account_id: int, code: str) -> dict | None:
    result = await session.execute(
        select(PositionAccount).where(
            PositionAccount.account_id == account_id,
            PositionAccount.code == code,
        )
    )
    row = result.scalars().first()
    return _rows_to_dicts([row])[0] if row else None


async def create_position(session: AsyncSession, data: dict) -> dict:
    position = PositionAccount(**data)
    session.add(position)
    await session.flush()
    return _rows_to_dicts([position])[0]


_POSITION_ALLOWED = {"quantity", "avg_price", "available_quantity"}


async def update_position(session: AsyncSession, account_id: int, code: str, data: dict) -> dict | None:
    result = await session.execute(
        select(PositionAccount).where(
            PositionAccount.account_id == account_id,
            PositionAccount.code == code,
        )
    )
    position = result.scalars().first()
    if not position:
        return None
    for key, value in data.items():
        if key in _POSITION_ALLOWED:
            setattr(position, key, value)
    await session.flush()
    return _rows_to_dicts([position])[0]


async def delete_position(session: AsyncSession, account_id: int, code: str) -> bool:
    result = await session.execute(
        select(PositionAccount).where(
            PositionAccount.account_id == account_id,
            PositionAccount.code == code,
        )
    )
    position = result.scalars().first()
    if not position:
        return False
    await session.delete(position)
    await session.flush()
    return True


# ── TradeOrder (create) ──


async def create_trade_order(session: AsyncSession, data: dict) -> dict:
    order = TradeOrder(**data)
    session.add(order)
    await session.flush()
    return _rows_to_dicts([order])[0]


# ── Strategy ──


async def create_strategy(session: AsyncSession, data: dict) -> dict:
    strategy = Strategy(**data)
    session.add(strategy)
    await session.flush()
    return _rows_to_dicts([strategy])[0]


async def get_strategy(session: AsyncSession, strategy_id: int) -> dict | None:
    result = await session.execute(select(Strategy).where(Strategy.id == strategy_id))
    row = result.scalars().first()
    return _rows_to_dicts([row])[0] if row else None


async def list_strategies(session: AsyncSession, *, active_only: bool = True) -> list[dict]:
    stmt = select(Strategy)
    if active_only:
        stmt = stmt.where(Strategy.is_active == True)
    result = await session.execute(stmt.order_by(Strategy.id))
    return _rows_to_dicts(result.scalars().all())


_STRATEGY_ALLOWED = {"name", "type", "params", "description", "is_active"}


async def update_strategy(session: AsyncSession, strategy_id: int, data: dict) -> dict | None:
    strategy = await session.get(Strategy, strategy_id)
    if not strategy:
        return None
    for key, value in data.items():
        if key in _STRATEGY_ALLOWED:
            setattr(strategy, key, value)
    await session.flush()
    return _rows_to_dicts([strategy])[0]


async def delete_strategy(session: AsyncSession, strategy_id: int) -> bool:
    strategy = await session.get(Strategy, strategy_id)
    if not strategy:
        return False
    strategy.is_active = False
    await session.flush()
    return True


# ── BacktestResult (extended) ──


async def create_backtest_result(session: AsyncSession, data: dict) -> dict:
    result = BacktestResult(**data)
    session.add(result)
    await session.flush()
    return _rows_to_dicts([result])[0]


async def get_backtest_result(session: AsyncSession, backtest_id: int) -> dict | None:
    result = await session.execute(select(BacktestResult).where(BacktestResult.id == backtest_id))
    row = result.scalars().first()
    return _rows_to_dicts([row])[0] if row else None


async def delete_backtest_result(session: AsyncSession, backtest_id: int) -> bool:
    """删除回测结果及其关联的交易明细和净值数据"""
    result = await session.get(BacktestResult, backtest_id)
    if not result:
        return False

    # 删除关联的交易明细
    await session.execute(
        select(BacktestTrade).where(BacktestTrade.backtest_id == backtest_id)
    )
    trades = await session.execute(
        select(BacktestTrade).where(BacktestTrade.backtest_id == backtest_id)
    )
    for trade in trades.scalars().all():
        await session.delete(trade)

    # 删除关联的净值数据
    navs = await session.execute(
        select(BacktestDailyNav).where(BacktestDailyNav.backtest_id == backtest_id)
    )
    for nav in navs.scalars().all():
        await session.delete(nav)

    # 删除关联的反馈日志
    logs = await session.execute(
        select(FeedbackLog).where(FeedbackLog.backtest_id == backtest_id)
    )
    for log in logs.scalars().all():
        await session.delete(log)

    # 删除回测结果
    await session.delete(result)
    await session.flush()
    return True


async def batch_delete_backtest_results(
    session: AsyncSession, backtest_ids: list[int]
) -> int:
    """批量删除回测结果"""
    if not backtest_ids:
        return 0

    count = 0
    for backtest_id in backtest_ids:
        if await delete_backtest_result(session, backtest_id):
            count += 1

    await session.flush()
    return count


# ── BacktestTrade ──


async def batch_insert_backtest_trades(session: AsyncSession, trades: list[dict]) -> int:
    if not trades:
        return 0
    for trade in trades:
        session.add(BacktestTrade(**trade))
    await session.flush()
    return len(trades)


async def get_backtest_trades(
    session: AsyncSession, backtest_id: int
) -> list[dict]:
    result = await session.execute(
        select(
            BacktestTrade,
            StockMaster.stock_name,
        )
        .outerjoin(StockMaster, BacktestTrade.code == StockMaster.stock_code)
        .where(BacktestTrade.backtest_id == backtest_id)
        .order_by(BacktestTrade.trade_date)
    )
    rows = []
    for trade, stock_name in result.all():
        row = {c.name: getattr(trade, c.name) for c in trade.__table__.columns}
        row["stock_name"] = stock_name
        rows.append(row)
    return rows


# ── BacktestDailyNav ──


async def batch_insert_backtest_nav(session: AsyncSession, navs: list[dict]) -> int:
    if not navs:
        return 0
    for nav in navs:
        session.add(BacktestDailyNav(**nav))
    await session.flush()
    return len(navs)


async def get_backtest_nav(
    session: AsyncSession, backtest_id: int
) -> list[dict]:
    result = await session.execute(
        select(BacktestDailyNav)
        .where(BacktestDailyNav.backtest_id == backtest_id)
        .order_by(BacktestDailyNav.trade_date)
    )
    return _rows_to_dicts(result.scalars().all())


# ── SimAccount ──


async def create_sim_account(session: AsyncSession, data: dict) -> dict:
    account = SimAccount(**data)
    session.add(account)
    await session.flush()
    return _rows_to_dicts([account])[0]


async def get_sim_account(session: AsyncSession, account_id: int) -> dict | None:
    result = await session.execute(select(SimAccount).where(SimAccount.id == account_id))
    row = result.scalars().first()
    return _rows_to_dicts([row])[0] if row else None


async def list_sim_accounts(session: AsyncSession, user_id: int) -> list[dict]:
    result = await session.execute(
        select(SimAccount)
        .where(SimAccount.user_id == user_id, SimAccount.status == "active")
        .order_by(SimAccount.id)
    )
    return _rows_to_dicts(result.scalars().all())


_SIM_ACCOUNT_ALLOWED = {"account_name", "current_capital", "total_assets", "peak_assets", "status", "strategy_id", "strategy_ids", "config"}


async def update_sim_account(session: AsyncSession, account_id: int, data: dict) -> dict | None:
    account = await session.get(SimAccount, account_id)
    if not account:
        return None
    for key, value in data.items():
        if key in _SIM_ACCOUNT_ALLOWED:
            setattr(account, key, value)
    await session.flush()
    return _rows_to_dicts([account])[0]


async def delete_sim_account(session: AsyncSession, account_id: int) -> bool:
    """删除模拟账户及其关联的持仓和订单"""
    account = await session.get(SimAccount, account_id)
    if not account:
        return False

    # 删除关联的持仓
    positions = await session.execute(
        select(PositionAccount).where(PositionAccount.account_id == account_id)
    )
    for pos in positions.scalars().all():
        await session.delete(pos)

    # 删除关联的订单
    orders = await session.execute(
        select(TradeOrder).where(TradeOrder.account_id == account_id)
    )
    for order in orders.scalars().all():
        await session.delete(order)

    # 删除关联的持仓快照
    snapshots = await session.execute(
        select(PositionDailySnapshot).where(PositionDailySnapshot.account_id == account_id)
    )
    for snap in snapshots.scalars().all():
        await session.delete(snap)

    # 删除账户
    await session.delete(account)
    await session.flush()
    return True


# ── PositionDailySnapshot ──


async def batch_insert_position_snapshots(session: AsyncSession, snapshots: list[dict]) -> int:
    if not snapshots:
        return 0
    for snap in snapshots:
        stmt = pg_insert(PositionDailySnapshot).values(**snap)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_position_snapshot",
            set_={
                "quantity": stmt.excluded.quantity,
                "available_quantity": stmt.excluded.available_quantity,
                "avg_price": stmt.excluded.avg_price,
                "close_price": stmt.excluded.close_price,
                "market_value": stmt.excluded.market_value,
                "pnl": stmt.excluded.pnl,
                "pnl_pct": stmt.excluded.pnl_pct,
                "created_at": func.now(),
            },
        )
        await session.execute(stmt)
    await session.flush()
    return len(snapshots)


async def get_position_snapshots(
    session: AsyncSession, account_id: int
) -> list[dict]:
    """获取账户的持仓快照历史"""
    result = await session.execute(
        select(PositionDailySnapshot)
        .where(PositionDailySnapshot.account_id == account_id)
        .order_by(PositionDailySnapshot.trade_date)
    )
    return _rows_to_dicts(result.scalars().all())


# ── FeedbackLog ──


async def create_feedback_log(session: AsyncSession, data: dict) -> dict:
    log = FeedbackLog(**data)
    session.add(log)
    await session.flush()
    return _rows_to_dicts([log])[0]




# ── Auto-trade helpers ──


async def list_all_active_accounts_with_strategy(session: AsyncSession) -> list[dict]:
    """获取所有配置了策略的活跃模拟账户（支持单策略和多策略）"""
    # 获取所有活跃账户
    result = await session.execute(
        select(SimAccount).where(SimAccount.status == "active")
    )
    accounts = result.scalars().all()

    rows = []
    for account in accounts:
        row = {c.name: getattr(account, c.name) for c in account.__table__.columns}

        # 收集所有策略ID（支持 strategy_id 和 strategy_ids）
        strategy_ids = []
        if account.strategy_id:
            strategy_ids.append(account.strategy_id)
        if account.strategy_ids:
            for sid in account.strategy_ids:
                if sid not in strategy_ids:
                    strategy_ids.append(sid)

        if not strategy_ids:
            continue

        # 获取策略信息
        strategies_result = await session.execute(
            select(Strategy).where(
                Strategy.id.in_(strategy_ids),
                Strategy.is_active == True,
            )
        )
        strategies = strategies_result.scalars().all()

        if not strategies:
            continue

        row["strategies"] = [
            {"id": s.id, "type": s.type, "params": s.params or {}}
            for s in strategies
        ]
        # 兼容旧字段
        row["strategy_type"] = strategies[0].type
        row["strategy_params"] = strategies[0].params or {}
        rows.append(row)

    return rows


async def get_latest_popularity_data(session: AsyncSession) -> dict[str, dict]:
    """获取最新人气榜数据，返回 {stock_code: {...}} 格式"""
    from stock_service.db.models.v2_models import PopularitySnapshot, StockMaster

    # 获取最新的快照时间
    sub = select(func.max(PopularitySnapshot.snapshot_time)).scalar_subquery()
    result = await session.execute(
        select(PopularitySnapshot, StockMaster.stock_code)
        .join(StockMaster, PopularitySnapshot.stock_code == StockMaster.stock_code)
        .where(PopularitySnapshot.snapshot_time == sub)
        .order_by(PopularitySnapshot.popularity_rank)
    )

    data = {}
    for snap, stock_code in result.all():
        data[stock_code] = {
            "rank": snap.popularity_rank,
            "score": float(snap.popularity_score) if snap.popularity_score else 0,
            "is_new_entry": snap.is_new_entry if hasattr(snap, 'is_new_entry') else False,
            "rank_change": snap.rank_change if hasattr(snap, 'rank_change') else 0,
        }
    return data


async def list_feedback_logs(
    session: AsyncSession, backtest_id: int
) -> list[dict]:
    result = await session.execute(
        select(FeedbackLog)
        .where(FeedbackLog.backtest_id == backtest_id)
        .order_by(FeedbackLog.created_at.desc())
    )
    return _rows_to_dicts(result.scalars().all())


# ── StockDaily (batch upsert) ──


async def batch_upsert_stock_daily(session: AsyncSession, rows: list[dict]) -> int:
    if not rows:
        return 0
    for row in rows:
        row.setdefault("created_at", func.now())
        row.setdefault("updated_at", func.now())
        stmt = pg_insert(StockDaily).values(**row)
        stmt = stmt.on_conflict_do_update(
            index_elements=["code", "trade_date"],
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
                "amount": stmt.excluded.amount,
                "updated_at": func.now(),
            },
        )
        await session.execute(stmt)
    await session.flush()
    return len(rows)


async def batch_upsert_stock_indicator(session: AsyncSession, rows: list[dict]) -> int:
    if not rows:
        return 0
    for row in rows:
        row.setdefault("created_at", func.now())
        row.setdefault("updated_at", func.now())
        stmt = pg_insert(StockIndicator).values(**row)
        stmt = stmt.on_conflict_do_update(
            index_elements=["code", "trade_date"],
            set_={
                "ma5": stmt.excluded.ma5,
                "ma20": stmt.excluded.ma20,
                "rsi": stmt.excluded.rsi,
                "macd": stmt.excluded.macd,
                "boll_upper": stmt.excluded.boll_upper,
                "boll_lower": stmt.excluded.boll_lower,
                "atr": stmt.excluded.atr,
                "updated_at": func.now(),
            },
        )
        await session.execute(stmt)
    await session.flush()
    return len(rows)


# ── V2 CRUD extensions (for quant module) ──


async def get_latest_popularity(
    session: AsyncSession, limit: int = 200
) -> list[dict]:
    """Get latest popularity snapshots."""
    from stock_service.db.models.v2_models import PopularitySnapshot, StockMaster

    result = await session.execute(
        select(PopularitySnapshot, StockMaster.stock_code)
        .join(StockMaster, PopularitySnapshot.stock_code == StockMaster.stock_code)
        .order_by(PopularitySnapshot.trade_date.desc(), PopularitySnapshot.popularity_rank)
        .limit(limit)
    )
    rows = result.all()
    return [
        {
            "stock_code": row.stock_code,
            "popularity_rank": row[0].popularity_rank,
            "popularity_score": row[0].popularity_score,
            "is_new_entry": row[0].is_new_entry,
            "rank_change": row[0].rank_change,
        }
        for row in rows
    ]


async def get_latest_popularity_by_code(
    session: AsyncSession, code: str
) -> dict | None:
    from stock_service.db.models.v2_models import PopularitySnapshot, StockMaster

    result = await session.execute(
        select(PopularitySnapshot)
        .join(StockMaster, PopularitySnapshot.stock_code == StockMaster.stock_code)
        .where(StockMaster.stock_code == code)
        .order_by(PopularitySnapshot.trade_date.desc())
        .limit(1)
    )
    row = result.scalars().first()
    if not row:
        return None
    return _rows_to_dicts([row])[0]


async def get_latest_stock_analysis(
    session: AsyncSession, code: str
) -> dict | None:
    from stock_service.db.models.v2_models import StockAnalysisSnapshot, StockMaster

    result = await session.execute(
        select(StockAnalysisSnapshot)
        .join(StockMaster, StockAnalysisSnapshot.stock_code == StockMaster.stock_code)
        .where(StockMaster.stock_code == code)
        .order_by(StockAnalysisSnapshot.analyzed_at.desc())
        .limit(1)
    )
    row = result.scalars().first()
    if not row:
        return None
    return _rows_to_dicts([row])[0]


async def get_benchmark_daily(
    session: AsyncSession, start_date: date, end_date: date,
    benchmark_code: str = "000300.SH"
) -> list[dict]:
    """获取基准指数日线数据"""
    result = await session.execute(
        select(StockDaily)
        .where(
            StockDaily.code == benchmark_code,
            StockDaily.trade_date >= start_date,
            StockDaily.trade_date <= end_date,
        )
        .order_by(StockDaily.trade_date)
    )
    return _rows_to_dicts(result.scalars().all())


# ── PendingOrder ──


async def create_pending_order(session: AsyncSession, data: dict) -> dict:
    """创建挂单"""
    order = PendingOrder(**data)
    session.add(order)
    await session.flush()
    return _rows_to_dicts([order])[0]


async def get_pending_order(session: AsyncSession, order_id: int) -> dict | None:
    """获取挂单"""
    result = await session.execute(
        select(PendingOrder, StockMaster.stock_name)
        .outerjoin(StockMaster, PendingOrder.code == StockMaster.stock_code)
        .where(PendingOrder.id == order_id)
    )
    row = result.first()
    if not row:
        return None
    order, stock_name = row
    d = {c.name: getattr(order, c.name) for c in order.__table__.columns}
    d["stock_name"] = stock_name
    return d


async def list_pending_orders(
    session: AsyncSession, account_id: int, status: str | None = "pending"
) -> list[dict]:
    """获取账户的挂单列表"""
    stmt = (
        select(PendingOrder, StockMaster.stock_name)
        .outerjoin(StockMaster, PendingOrder.code == StockMaster.stock_code)
        .where(PendingOrder.account_id == account_id)
    )
    if status:
        stmt = stmt.where(PendingOrder.status == status)
    stmt = stmt.order_by(PendingOrder.created_at.desc())

    result = await session.execute(stmt)
    rows = []
    for order, stock_name in result.all():
        d = {c.name: getattr(order, c.name) for c in order.__table__.columns}
        d["stock_name"] = stock_name
        rows.append(d)
    return rows


async def list_all_pending_orders(session: AsyncSession) -> list[dict]:
    """获取所有待处理的挂单（用于定时检查）"""
    result = await session.execute(
        select(PendingOrder, StockMaster.stock_name)
        .outerjoin(StockMaster, PendingOrder.code == StockMaster.stock_code)
        .where(PendingOrder.status == "pending")
        .order_by(PendingOrder.created_at)
    )
    rows = []
    for order, stock_name in result.all():
        d = {c.name: getattr(order, c.name) for c in order.__table__.columns}
        d["stock_name"] = stock_name
        rows.append(d)
    return rows


async def update_pending_order(
    session: AsyncSession, order_id: int, data: dict
) -> dict | None:
    """更新挂单"""
    order = await session.get(PendingOrder, order_id)
    if not order:
        return None
    for key, value in data.items():
        if key in {"status", "filled_at", "filled_price", "note"}:
            setattr(order, key, value)
    await session.flush()
    return _rows_to_dicts([order])[0]


async def cancel_pending_order(session: AsyncSession, order_id: int) -> bool:
    """取消挂单"""
    order = await session.get(PendingOrder, order_id)
    if not order or order.status != "pending":
        return False
    order.status = "cancelled"
    await session.flush()
    return True


async def cancel_all_pending_orders(session: AsyncSession, account_id: int) -> int:
    """取消账户所有挂单"""
    result = await session.execute(
        select(PendingOrder).where(
            PendingOrder.account_id == account_id,
            PendingOrder.status == "pending",
        )
    )
    count = 0
    for order in result.scalars().all():
        order.status = "cancelled"
        count += 1
    await session.flush()
    return count


async def list_all_active_sim_accounts(session: AsyncSession) -> list[dict]:
    """获取所有活跃的模拟账户（用于每日结算）"""
    result = await session.execute(
        select(SimAccount).where(SimAccount.status == "active")
    )
    return _rows_to_dicts(result.scalars().all())



async def get_best_trade_date_for_popularity(session: AsyncSession) -> date | None:
    """获取人气榜股票覆盖最多的交易日（最近 7 天内）"""
    from stock_service.db.models.v2_models import PopularitySnapshot
    pop_sub = (
        select(PopularitySnapshot.stock_code)
        .where(PopularitySnapshot.trade_date == select(func.max(PopularitySnapshot.trade_date)).scalar_subquery())
        .scalar_subquery()
    )
    result = await session.execute(
        select(StockDaily.trade_date, func.count(StockDaily.code.distinct()).label("cnt"))
        .where(StockDaily.code.in_(pop_sub))
        .where(StockDaily.trade_date >= func.current_date() - 7)
        .group_by(StockDaily.trade_date)
        .order_by(func.count(StockDaily.code.distinct()).desc())
        .limit(1)
    )
    row = result.first()
    return row[0] if row else None


async def get_missing_popularity_codes(session: AsyncSession, limit: int = 200) -> list[str]:
    """获取人气榜中缺少近 3 天日线数据的股票代码"""
    from stock_service.db.models.v2_models import PopularitySnapshot
    latest_pop = select(func.max(PopularitySnapshot.trade_date)).scalar_subquery()
    recent_codes = (
        select(StockDaily.code.distinct())
        .where(StockDaily.trade_date >= func.current_date() - 3)
        .scalar_subquery()
    )
    result = await session.execute(
        select(PopularitySnapshot.stock_code.distinct())
        .where(PopularitySnapshot.trade_date == latest_pop)
        .where(PopularitySnapshot.stock_code.notin_(recent_codes))
        .order_by(PopularitySnapshot.stock_code)
        .limit(limit)
    )
    return [row[0] for row in result.all()]


async def list_all_stock_codes(session: AsyncSession) -> list[str]:
    """获取 stock_daily 中所有不重复的股票代码"""
    result = await session.execute(
        select(StockDaily.code.distinct()).order_by(StockDaily.code)
    )
    return [row[0] for row in result.all()]


__all__ = [
    "get_stock_basic_by_code",
    "list_stock_basic",
    "get_stock_daily",
    "get_stock_indicator",
    "list_strategy_picks",
    "list_backtest_results",
    "list_trade_orders",
    "get_positions",
    "get_position",
    "create_position",
    "update_position",
    "delete_position",
    "create_trade_order",
    "create_strategy",
    "get_strategy",
    "list_strategies",
    "update_strategy",
    "delete_strategy",
    "create_backtest_result",
    "get_backtest_result",
    "batch_insert_backtest_trades",
    "get_backtest_trades",
    "batch_insert_backtest_nav",
    "get_backtest_nav",
    "create_sim_account",
    "get_sim_account",
    "list_sim_accounts",
    "update_sim_account",
    "batch_insert_position_snapshots",
    "create_feedback_log",
    "list_feedback_logs",
    "batch_upsert_stock_daily",
    "get_latest_popularity",
    "get_latest_popularity_by_code",
    "get_latest_stock_analysis",
]
