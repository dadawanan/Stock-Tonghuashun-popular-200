from datetime import date

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from stock_service.db.models.quant_models import (
    BacktestDailyNav,
    BacktestResult,
    BacktestTrade,
    FeedbackLog,
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


def _rows_to_dicts(rows) -> list[dict]:
    return [{c.name: getattr(r, c.name) for c in r.__table__.columns} for r in rows]


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


_SIM_ACCOUNT_ALLOWED = {"account_name", "current_capital", "total_assets", "status", "strategy_id", "config"}


async def update_sim_account(session: AsyncSession, account_id: int, data: dict) -> dict | None:
    account = await session.get(SimAccount, account_id)
    if not account:
        return None
    for key, value in data.items():
        if key in _SIM_ACCOUNT_ALLOWED:
            setattr(account, key, value)
    await session.flush()
    return _rows_to_dicts([account])[0]


# ── PositionDailySnapshot ──


async def batch_insert_position_snapshots(session: AsyncSession, snapshots: list[dict]) -> int:
    if not snapshots:
        return 0
    for snap in snapshots:
        session.add(PositionDailySnapshot(**snap))
    await session.flush()
    return len(snapshots)


# ── FeedbackLog ──


async def create_feedback_log(session: AsyncSession, data: dict) -> dict:
    log = FeedbackLog(**data)
    session.add(log)
    await session.flush()
    return _rows_to_dicts([log])[0]


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
        stmt = pg_insert(StockDaily).values(**row)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_stock_daily_code_date",
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
