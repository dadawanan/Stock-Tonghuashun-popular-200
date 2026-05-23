# Quant Trading Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a quantitative trading module with pluggable strategies, backtesting, simulated trading, and closed-loop feedback on top of the existing stock analysis pipeline.

**Architecture:** Layered architecture (Domain → Application → Infrastructure → API) following existing patterns. Strategy pattern for pluggable strategies. Reuse existing `schema_quant_v1.sql` tables with extensions.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 async, PostgreSQL, pandas, akshare

---

## File Structure

```
src/stock_service/quant/
├── __init__.py
├── domain/
│   ├── __init__.py
│   ├── strategy_interface.py    # BaseStrategy ABC, Signal, SignalType
│   ├── backtest_rules.py        # BacktestConfig, BacktestRules, BacktestMetrics
│   ├── risk_manager.py          # RiskManager
│   └── indicators.py            # TechnicalIndicators (pure functions)
├── application/
│   ├── __init__.py
│   ├── strategy_engine.py       # StrategyEngine + 4 built-in strategies
│   ├── backtest_engine.py       # BacktestEngine
│   ├── sim_trading_engine.py    # SimTradingEngine
│   └── feedback_service.py      # FeedbackService
├── infrastructure/
│   ├── __init__.py
│   ├── data_provider.py         # QuantDataProvider (akshare + CSV)
│   └── analysis_adapter.py      # AnalysisAdapter (reads from v2 tables)
├── crud/
│   ├── __init__.py
│   └── quant_crud.py            # Extended CRUD (strategy, backtest, sim)
├── schemas.py                   # Pydantic models
└── api/
    ├── __init__.py
    └── routes/
        ├── __init__.py
        ├── strategies.py        # Strategy CRUD
        ├── data.py              # Data fetch + import
        ├── backtest.py          # Backtest run + results
        ├── sim_trading.py       # Sim account + trading
        └── feedback.py          # Feedback insights
```

---

## Task 1: Database Schema & ORM Models

**Files:**
- Modify: `schema_quant_v1.sql`
- Modify: `src/stock_service/db/models/quant_models.py`

- [ ] **Step 1: Update schema_quant_v1.sql with new tables**

Add the following SQL to `schema_quant_v1.sql` (after existing tables, before COMMIT):

```sql
-- ------------------------------------------------------------
-- G. 策略定义
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS strategy (
    id          BIGSERIAL PRIMARY KEY,
    name        VARCHAR(64) NOT NULL,
    type        VARCHAR(32) NOT NULL,
    params      JSONB,
    description TEXT,
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE strategy IS '量化策略定义（popularity/sentiment/technical/multi_factor）';

-- ------------------------------------------------------------
-- H. 回测交易明细
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS backtest_trade (
    id              BIGSERIAL PRIMARY KEY,
    backtest_id     BIGINT NOT NULL REFERENCES backtest_result(id),
    code            VARCHAR(16) NOT NULL,
    side            VARCHAR(8) NOT NULL,
    price           NUMERIC(18, 4),
    quantity        INTEGER,
    trade_date      DATE NOT NULL,
    pnl             NUMERIC(18, 4),
    signal_source   VARCHAR(32),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_backtest_trade_backtest ON backtest_trade (backtest_id, trade_date);

-- ------------------------------------------------------------
-- I. 回测每日净值
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS backtest_daily_nav (
    id              BIGSERIAL PRIMARY KEY,
    backtest_id     BIGINT NOT NULL REFERENCES backtest_result(id),
    trade_date      DATE NOT NULL,
    nav             NUMERIC(18, 6),
    total_assets    NUMERIC(18, 2),
    cash            NUMERIC(18, 2),
    position_value  NUMERIC(18, 2),
    benchmark_nav   NUMERIC(18, 6),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_backtest_daily_nav UNIQUE (backtest_id, trade_date)
);

-- ------------------------------------------------------------
-- J. 模拟账户
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sim_account (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES users(id),
    account_name    VARCHAR(64) NOT NULL,
    initial_capital NUMERIC(18, 2) NOT NULL DEFAULT 1000000.00,
    current_capital NUMERIC(18, 2) NOT NULL,
    total_assets    NUMERIC(18, 2) NOT NULL,
    status          VARCHAR(16) DEFAULT 'active',
    strategy_id     BIGINT REFERENCES strategy(id),
    config          JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sim_account_user ON sim_account (user_id);

-- ------------------------------------------------------------
-- K. 持仓每日快照
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS position_daily_snapshot (
    id                  BIGSERIAL PRIMARY KEY,
    account_id          BIGINT NOT NULL,
    code                VARCHAR(16) NOT NULL,
    trade_date          DATE NOT NULL,
    quantity            INTEGER,
    available_quantity  INTEGER,
    avg_price           NUMERIC(18, 4),
    close_price         NUMERIC(18, 4),
    market_value        NUMERIC(18, 2),
    pnl                 NUMERIC(18, 2),
    pnl_pct             NUMERIC(18, 4),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_position_snapshot UNIQUE (account_id, code, trade_date)
);

-- ------------------------------------------------------------
-- L. 反馈日志
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS feedback_log (
    id              BIGSERIAL PRIMARY KEY,
    backtest_id     BIGINT NOT NULL REFERENCES backtest_result(id),
    strategy_id     BIGINT NOT NULL REFERENCES strategy(id),
    feedback_type   VARCHAR(32) NOT NULL,
    before_params   JSONB,
    after_params    JSONB,
    reason          TEXT,
    status          VARCHAR(16) DEFAULT 'pending',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ------------------------------------------------------------
-- 扩展现有表
-- ------------------------------------------------------------
ALTER TABLE trade_order ADD COLUMN IF NOT EXISTS strategy_id BIGINT;
ALTER TABLE trade_order ADD COLUMN IF NOT EXISTS trade_at TIMESTAMPTZ;
ALTER TABLE trade_order ADD COLUMN IF NOT EXISTS commission NUMERIC(18, 4) DEFAULT 0;
ALTER TABLE trade_order ADD COLUMN IF NOT EXISTS slippage NUMERIC(18, 4) DEFAULT 0;

ALTER TABLE position_account ADD COLUMN IF NOT EXISTS available_quantity INTEGER;
```

- [ ] **Step 2: Add ORM models to quant_models.py**

Add the following models to `src/stock_service/db/models/quant_models.py`:

```python
class Strategy(Base):
    __tablename__ = "strategy"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(VARCHAR(64), nullable=False)
    type: Mapped[str] = mapped_column(VARCHAR(32), nullable=False)
    params: Mapped[Optional[dict]] = mapped_column(JSONB)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BacktestTrade(Base):
    __tablename__ = "backtest_trade"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    backtest_id: Mapped[int] = mapped_column(BIGINT, nullable=False)
    code: Mapped[str] = mapped_column(VARCHAR(16), nullable=False)
    side: Mapped[str] = mapped_column(VARCHAR(8), nullable=False)
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    quantity: Mapped[Optional[int]] = mapped_column(Integer)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    pnl: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    signal_source: Mapped[Optional[str]] = mapped_column(VARCHAR(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        _Index("idx_backtest_trade_backtest", "backtest_id", "trade_date"),
    )


class BacktestDailyNav(Base):
    __tablename__ = "backtest_daily_nav"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    backtest_id: Mapped[int] = mapped_column(BIGINT, nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    nav: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6))
    total_assets: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    cash: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    position_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    benchmark_nav: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("backtest_id", "trade_date", name="uq_backtest_daily_nav"),
    )


class SimAccount(Base):
    __tablename__ = "sim_account"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BIGINT, nullable=False)
    account_name: Mapped[str] = mapped_column(VARCHAR(64), nullable=False)
    initial_capital: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=1000000)
    current_capital: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    total_assets: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[str] = mapped_column(VARCHAR(16), default="active")
    strategy_id: Mapped[Optional[int]] = mapped_column(BIGINT)
    config: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        _Index("idx_sim_account_user", "user_id"),
    )


class PositionDailySnapshot(Base):
    __tablename__ = "position_daily_snapshot"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(BIGINT, nullable=False)
    code: Mapped[str] = mapped_column(VARCHAR(16), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    quantity: Mapped[Optional[int]] = mapped_column(Integer)
    available_quantity: Mapped[Optional[int]] = mapped_column(Integer)
    avg_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    close_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    market_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    pnl: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    pnl_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("account_id", "code", "trade_date", name="uq_position_snapshot"),
    )


class FeedbackLog(Base):
    __tablename__ = "feedback_log"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    backtest_id: Mapped[int] = mapped_column(BIGINT, nullable=False)
    strategy_id: Mapped[int] = mapped_column(BIGINT, nullable=False)
    feedback_type: Mapped[str] = mapped_column(VARCHAR(32), nullable=False)
    before_params: Mapped[Optional[dict]] = mapped_column(JSONB)
    after_params: Mapped[Optional[dict]] = mapped_column(JSONB)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(VARCHAR(16), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

Also add `JSONB` import and update `__all__`:

```python
from sqlalchemy.dialects.postgresql import BIGINT, JSONB, VARCHAR

__all__ = [
    "StockBasic", "StockDaily", "StockIndicator", "StrategyPick",
    "BacktestResult", "TradeOrder", "PositionAccount",
    "Strategy", "BacktestTrade", "BacktestDailyNav",
    "SimAccount", "PositionDailySnapshot", "FeedbackLog",
]
```

Also extend `TradeOrder` and `PositionAccount` with new columns:

```python
class TradeOrder(Base):
    __tablename__ = "trade_order"
    # ... existing columns ...
    strategy_id: Mapped[Optional[int]] = mapped_column(BIGINT)
    trade_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    commission: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), default=0)
    slippage: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), default=0)

class PositionAccount(Base):
    __tablename__ = "position_account"
    # ... existing columns ...
    available_quantity: Mapped[Optional[int]] = mapped_column(Integer)
```

- [ ] **Step 3: Commit**

```bash
git add schema_quant_v1.sql src/stock_service/db/models/quant_models.py
git commit -m "feat(quant): add schema and ORM models for quant module"
```

---

## Task 2: Quant CRUD Layer

**Files:**
- Modify: `src/stock_service/crud/quant_crud.py`

- [ ] **Step 1: Extend quant_crud.py with new CRUD operations**

Add to `src/stock_service/crud/quant_crud.py`:

```python
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from stock_service.db.models.quant_models import (
    Strategy, BacktestTrade, BacktestDailyNav,
    SimAccount, PositionDailySnapshot, FeedbackLog,
)


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


async def update_strategy(session: AsyncSession, strategy_id: int, data: dict) -> dict | None:
    strategy = await session.get(Strategy, strategy_id)
    if not strategy:
        return None
    for key, value in data.items():
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


async def list_backtest_results(
    session: AsyncSession, strategy_id: int | None = None
) -> list[dict]:
    stmt = select(BacktestResult)
    if strategy_id:
        stmt = stmt.where(BacktestResult.strategy_id == strategy_id)
    result = await session.execute(stmt.order_by(BacktestResult.created_at.desc()))
    return _rows_to_dicts(result.scalars().all())


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
        select(BacktestTrade)
        .where(BacktestTrade.backtest_id == backtest_id)
        .order_by(BacktestTrade.trade_date)
    )
    return _rows_to_dicts(result.scalars().all())


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


async def update_sim_account(session: AsyncSession, account_id: int, data: dict) -> dict | None:
    account = await session.get(SimAccount, account_id)
    if not account:
        return None
    for key, value in data.items():
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
```

- [ ] **Step 2: Commit**

```bash
git add src/stock_service/crud/quant_crud.py
git commit -m "feat(quant): extend quant CRUD with strategy, backtest, sim operations"
```

---

## Task 3: Domain Layer - Strategy Interface

**Files:**
- Create: `src/stock_service/quant/__init__.py`
- Create: `src/stock_service/quant/domain/__init__.py`
- Create: `src/stock_service/quant/domain/strategy_interface.py`

- [ ] **Step 1: Create package structure**

```bash
mkdir -p src/stock_service/quant/domain
mkdir -p src/stock_service/quant/application
mkdir -p src/stock_service/quant/infrastructure
mkdir -p src/stock_service/quant/crud
mkdir -p src/stock_service/quant/api/routes
```

- [ ] **Step 2: Create __init__.py files**

Create empty `__init__.py` in each new directory.

- [ ] **Step 3: Create strategy_interface.py**

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class SignalType(Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class Signal:
    code: str
    signal_type: SignalType
    score: float  # 0-1 signal strength
    reason: str
    target_price: float | None = None
    stop_loss: float | None = None


@dataclass
class StrategyContext:
    """Context passed to strategy for signal generation."""
    trade_date: date
    # Market data: code -> {open, high, low, close, volume, ...}
    market_data: dict[str, dict]
    # Indicators: code -> {ma5, ma20, rsi, macd, ...}
    indicators: dict[str, dict]
    # Analysis results: code -> {text_score, market_score, integrated_score, ...}
    analysis: dict[str, dict]
    # Popularity data: code -> {rank, score, is_new_entry, rank_change}
    popularity: dict[str, dict]
    # Current positions: code -> {quantity, avg_price, ...}
    positions: dict[str, dict]


class BaseStrategy(ABC):
    """Abstract base class for all strategies."""

    @abstractmethod
    async def generate_signals(
        self,
        stock_codes: list[str],
        context: StrategyContext,
    ) -> list[Signal]:
        """Generate trading signals for given stocks."""
        pass

    @abstractmethod
    def get_params(self) -> dict:
        """Return current strategy parameters."""
        pass

    @abstractmethod
    def set_params(self, params: dict) -> None:
        """Update strategy parameters."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Strategy display name."""
        pass

    @property
    @abstractmethod
    def strategy_type(self) -> str:
        """Strategy type identifier: popularity/sentiment/technical/multi_factor."""
        pass
```

- [ ] **Step 4: Commit**

```bash
git add src/stock_service/quant/
git commit -m "feat(quant): add strategy interface and package structure"
```

---

## Task 4: Technical Indicators

**Files:**
- Create: `src/stock_service/quant/domain/indicators.py`
- Create: `tests/quant/test_indicators.py`

- [ ] **Step 1: Write tests for indicators**

```python
# tests/quant/test_indicators.py
import pytest
import pandas as pd
import numpy as np
from stock_service.quant.domain.indicators import TechnicalIndicators


class TestRSI:
    def test_rsi_basic(self):
        """RSI should return values between 0 and 100."""
        prices = pd.Series([100, 102, 101, 103, 105, 104, 106, 108, 107, 110,
                            109, 111, 113, 112, 115, 114, 116, 118, 117, 120])
        rsi = TechnicalIndicators.rsi(prices, period=14)
        last_rsi = rsi.iloc[-1]
        assert 0 <= last_rsi <= 100

    def test_rsi_uptrend(self):
        """RSI should be high in a strong uptrend."""
        prices = pd.Series(range(100, 130))  # Steady climb
        rsi = TechnicalIndicators.rsi(prices, period=14)
        assert rsi.iloc[-1] > 70

    def test_rsi_downtrend(self):
        """RSI should be low in a strong downtrend."""
        prices = pd.Series(range(130, 100, -1))  # Steady decline
        rsi = TechnicalIndicators.rsi(prices, period=14)
        assert rsi.iloc[-1] < 30


class TestMACD:
    def test_macd_returns_three_series(self):
        prices = pd.Series(range(100, 150))
        macd_line, signal_line, histogram = TechnicalIndicators.macd(prices)
        assert len(macd_line) == len(prices)
        assert len(signal_line) == len(prices)
        assert len(histogram) == len(prices)

    def test_macd_histogram_is_difference(self):
        prices = pd.Series(range(100, 150))
        macd_line, signal_line, histogram = TechnicalIndicators.macd(prices)
        pd.testing.assert_series_equal(
            histogram, macd_line - signal_line, check_names=False
        )


class TestBollingerBands:
    def test_boll_returns_three_series(self):
        prices = pd.Series(range(100, 130))
        upper, middle, lower = TechnicalIndicators.bollinger_bands(prices)
        assert len(upper) == len(prices)

    def test_middle_is_moving_average(self):
        prices = pd.Series(range(100, 130))
        upper, middle, lower = TechnicalIndicators.bollinger_bands(prices, period=20)
        expected = prices.rolling(20).mean()
        pd.testing.assert_series_equal(middle, expected, check_names=False)

    def test_upper_above_middle_above_lower(self):
        prices = pd.Series(np.random.randn(50).cumsum() + 100)
        upper, middle, lower = TechnicalIndicators.bollinger_bands(prices, period=20)
        valid = middle.dropna().index
        assert (upper[valid] >= middle[valid]).all()
        assert (middle[valid] >= lower[valid]).all()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/fyq/Desktop/workshop/stock
python -m pytest tests/quant/test_indicators.py -v
```

Expected: FAIL (module not found)

- [ ] **Step 3: Implement TechnicalIndicators**

```python
# src/stock_service/quant/domain/indicators.py
import pandas as pd


class TechnicalIndicators:
    """Pure functions for technical indicator calculation."""

    @staticmethod
    def rsi(series: pd.Series, period: int = 14) -> pd.Series:
        delta = series.diff()
        gain = delta.where(delta > 0, 0).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def macd(
        series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        ema_fast = series.ewm(span=fast, adjust=False).mean()
        ema_slow = series.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram

    @staticmethod
    def bollinger_bands(
        series: pd.Series, period: int = 20, std_dev: int = 2
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        middle = series.rolling(window=period).mean()
        std = series.rolling(window=period).std()
        upper = middle + std_dev * std
        lower = middle - std_dev * std
        return upper, middle, lower

    @staticmethod
    def kdj(
        df: pd.DataFrame, n: int = 9, m1: int = 3, m2: int = 3
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        low_n = df["low"].rolling(window=n).min()
        high_n = df["high"].rolling(window=n).max()
        rsv = (df["close"] - low_n) / (high_n - low_n) * 100
        k = rsv.ewm(com=m1 - 1, adjust=False).mean()
        d = k.ewm(com=m2 - 1, adjust=False).mean()
        j = 3 * k - 2 * d
        return k, d, j

    @staticmethod
    def ma(series: pd.Series, period: int) -> pd.Series:
        return series.rolling(window=period).mean()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/quant/test_indicators.py -v
```

Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/stock_service/quant/domain/indicators.py tests/quant/test_indicators.py
git commit -m "feat(quant): add technical indicators (RSI, MACD, BOLL, KDJ, MA)"
```

---

## Task 5: Backtest Rules & Config

**Files:**
- Create: `src/stock_service/quant/domain/backtest_rules.py`
- Create: `tests/quant/test_backtest_rules.py`

- [ ] **Step 1: Write tests for backtest rules**

```python
# tests/quant/test_backtest_rules.py
import pytest
from stock_service.quant.domain.backtest_rules import BacktestConfig, BacktestRules


@pytest.fixture
def config():
    return BacktestConfig()


@pytest.fixture
def rules():
    return BacktestRules()


class TestBuyCost:
    def test_buy_cost_includes_commission_and_slippage(self, rules, config):
        cost = rules.calculate_buy_cost(price=10.0, quantity=1000, config=config)
        # price * (1 + slippage) * quantity + commission
        actual_price = 10.0 * (1 + 0.002)  # slippage
        amount = actual_price * 1000
        commission = max(amount * 0.0003, 5)
        expected = amount + commission
        assert abs(cost - expected) < 0.01

    def test_buy_cost_minimum_commission(self, rules, config):
        cost = rules.calculate_buy_cost(price=1.0, quantity=100, config=config)
        # Commission should be at least 5
        assert cost > 100  # At least the amount itself


class TestSellRevenue:
    def test_sell_revenue_deducts_fees(self, rules, config):
        revenue = rules.calculate_sell_revenue(price=10.0, quantity=1000, config=config)
        # price * (1 - slippage) * quantity - commission - stamp_tax
        actual_price = 10.0 * (1 - 0.002)
        amount = actual_price * 1000
        commission = max(amount * 0.0003, 5)
        stamp = amount * 0.001
        expected = amount - commission - stamp
        assert abs(revenue - expected) < 0.01


class TestPositionLimit:
    def test_reject_when_max_holdings_reached(self, rules, config):
        ok, msg = rules.check_position_limit(
            current_holdings=10, total_value=1000000,
            buy_amount=100000, config=config
        )
        assert not ok
        assert "持仓数量" in msg

    def test_reject_when_position_too_large(self, rules, config):
        ok, msg = rules.check_position_limit(
            current_holdings=5, total_value=1000000,
            buy_amount=300000, config=config  # 30% > 20% limit
        )
        assert not ok
        assert "仓位" in msg

    def test_accept_normal_trade(self, rules, config):
        ok, msg = rules.check_position_limit(
            current_holdings=5, total_value=1000000,
            buy_amount=100000, config=config
        )
        assert ok


class TestStopLoss:
    def test_trigger_stop_loss(self, rules, config):
        from stock_service.quant.domain.backtest_rules import Position
        pos = Position(
            code="000001.SZ", quantity=1000, avg_price=10.0,
            available_quantity=1000, market_value=9000, pnl=-1000, pnl_pct=-0.10
        )
        assert rules.check_stop_loss(pos, current_price=9.0, config=config)

    def test_no_stop_loss_within_threshold(self, rules, config):
        from stock_service.quant.domain.backtest_rules import Position
        pos = Position(
            code="000001.SZ", quantity=1000, avg_price=10.0,
            available_quantity=1000, market_value=9500, pnl=-500, pnl_pct=-0.05
        )
        assert not rules.check_stop_loss(pos, current_price=9.5, config=config)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/quant/test_backtest_rules.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement BacktestConfig and BacktestRules**

```python
# src/stock_service/quant/domain/backtest_rules.py
from dataclasses import dataclass


@dataclass
class BacktestConfig:
    initial_capital: float = 1_000_000.0
    commission_rate: float = 0.0003
    stamp_tax: float = 0.001
    slippage: float = 0.002
    max_position_pct: float = 0.2
    max_holdings: int = 10
    stop_loss_pct: float = -0.08
    t_plus_1: bool = True


@dataclass
class Position:
    code: str
    quantity: int
    avg_price: float
    available_quantity: int
    market_value: float
    pnl: float
    pnl_pct: float


class BacktestRules:
    """Backtest trading rules engine."""

    def calculate_buy_cost(
        self, price: float, quantity: int, config: BacktestConfig
    ) -> float:
        actual_price = price * (1 + config.slippage)
        amount = actual_price * quantity
        commission = max(amount * config.commission_rate, 5)
        return amount + commission

    def calculate_sell_revenue(
        self, price: float, quantity: int, config: BacktestConfig
    ) -> float:
        actual_price = price * (1 - config.slippage)
        amount = actual_price * quantity
        commission = max(amount * config.commission_rate, 5)
        stamp = amount * config.stamp_tax
        return amount - commission - stamp

    def check_position_limit(
        self,
        current_holdings: int,
        total_value: float,
        buy_amount: float,
        config: BacktestConfig,
    ) -> tuple[bool, str]:
        if current_holdings >= config.max_holdings:
            return False, "持仓数量已达上限"
        if total_value > 0 and buy_amount / total_value > config.max_position_pct:
            return False, "单只股票仓位超过限制"
        return True, ""

    def check_stop_loss(
        self, position: Position, current_price: float, config: BacktestConfig
    ) -> bool:
        pnl_pct = (current_price - position.avg_price) / position.avg_price
        return pnl_pct <= config.stop_loss_pct

    def update_available_quantity(self, positions: dict[str, Position]) -> None:
        for pos in positions.values():
            pos.available_quantity = pos.quantity
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/quant/test_backtest_rules.py -v
```

Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/stock_service/quant/domain/backtest_rules.py tests/quant/test_backtest_rules.py
git commit -m "feat(quant): add backtest rules and config"
```

---

## Task 6: Risk Manager

**Files:**
- Create: `src/stock_service/quant/domain/risk_manager.py`
- Create: `tests/quant/test_risk_manager.py`

- [ ] **Step 1: Write tests for risk manager**

```python
# tests/quant/test_risk_manager.py
import pytest
from stock_service.quant.domain.risk_manager import RiskManager
from stock_service.quant.domain.backtest_rules import BacktestConfig, Position


@pytest.fixture
def manager():
    return RiskManager()


@pytest.fixture
def config():
    return BacktestConfig(max_holdings=5, max_position_pct=0.3, stop_loss_pct=-0.08)


class TestFilterSignals:
    def test_reject_buy_when_max_holdings(self, manager, config):
        positions = {f"00000{i}.SZ": Position(f"00000{i}.SZ", 100, 10.0, 100, 1000, 0, 0) for i in range(5)}
        from stock_service.quant.domain.strategy_interface import Signal, SignalType
        signals = [Signal("000006.SZ", SignalType.BUY, 0.8, "test")]
        filtered = manager.filter_signals(signals, positions, total_assets=100000, config=config)
        assert len(filtered) == 0

    def test_allow_buy_when_below_limit(self, manager, config):
        positions = {f"00000{i}.SZ": Position(f"00000{i}.SZ", 100, 10.0, 100, 1000, 0, 0) for i in range(3)}
        from stock_service.quant.domain.strategy_interface import Signal, SignalType
        signals = [Signal("000006.SZ", SignalType.BUY, 0.8, "test")]
        filtered = manager.filter_signals(signals, positions, total_assets=100000, config=config)
        assert len(filtered) == 1

    def test_always_allow_sell_signals(self, manager, config):
        positions = {"000001.SZ": Position("000001.SZ", 100, 10.0, 100, 1000, 0, 0)}
        from stock_service.quant.domain.strategy_interface import Signal, SignalType
        signals = [Signal("000001.SZ", SignalType.SELL, 0.9, "test")]
        filtered = manager.filter_signals(signals, positions, total_assets=100000, config=config)
        assert len(filtered) == 1


class TestCalculateQuantity:
    def test_buy_quantity_rounded_to_100(self, manager, config):
        qty = manager.calculate_buy_quantity(
            price=10.0, available_cash=50000, total_assets=100000, config=config
        )
        assert qty % 100 == 0
        assert qty > 0

    def test_buy_quantity_respects_position_limit(self, manager, config):
        qty = manager.calculate_buy_quantity(
            price=10.0, available_cash=100000, total_assets=100000, config=config
        )
        # max_position_pct=0.3, so max buy = 30000 / 10.0 = 3000 shares
        assert qty <= 3000

    def test_buy_quantity_zero_when_no_cash(self, manager, config):
        qty = manager.calculate_buy_quantity(
            price=10.0, available_cash=0, total_assets=100000, config=config
        )
        assert qty == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/quant/test_risk_manager.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement RiskManager**

```python
# src/stock_service/quant/domain/risk_manager.py
from stock_service.quant.domain.backtest_rules import BacktestConfig, Position
from stock_service.quant.domain.strategy_interface import Signal, SignalType


class RiskManager:
    """Risk management for trading signals."""

    def filter_signals(
        self,
        signals: list[Signal],
        positions: dict[str, Position],
        total_assets: float,
        config: BacktestConfig,
    ) -> list[Signal]:
        filtered = []
        current_holdings = len(positions)

        for signal in signals:
            if signal.signal_type == SignalType.BUY:
                if current_holdings >= config.max_holdings:
                    continue
                if signal.code in positions:
                    continue
                filtered.append(signal)
                current_holdings += 1
            elif signal.signal_type == SignalType.SELL:
                if signal.code in positions:
                    filtered.append(signal)

        return filtered

    def calculate_buy_quantity(
        self,
        price: float,
        available_cash: float,
        total_assets: float,
        config: BacktestConfig,
    ) -> int:
        if available_cash <= 0 or price <= 0:
            return 0

        max_amount = min(
            available_cash * 0.99,  # Leave some buffer for fees
            total_assets * config.max_position_pct,
        )

        quantity = int(max_amount / price)
        quantity = (quantity // 100) * 100  # Round to 100 (A-share lot size)
        return max(quantity, 0)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/quant/test_risk_manager.py -v
```

Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/stock_service/quant/domain/risk_manager.py tests/quant/test_risk_manager.py
git commit -m "feat(quant): add risk manager with signal filtering and position sizing"
```

---

## Task 7: Strategy Engine & Built-in Strategies

**Files:**
- Create: `src/stock_service/quant/application/__init__.py`
- Create: `src/stock_service/quant/application/strategy_engine.py`
- Create: `tests/quant/test_strategy_engine.py`

- [ ] **Step 1: Write tests for strategy engine**

```python
# tests/quant/test_strategy_engine.py
import pytest
from datetime import date
from stock_service.quant.application.strategy_engine import (
    StrategyEngine, PopularityStrategy, SentimentStrategy,
)
from stock_service.quant.domain.strategy_interface import (
    SignalType, StrategyContext,
)


@pytest.fixture
def engine():
    eng = StrategyEngine()
    eng.register("popularity", PopularityStrategy())
    eng.register("sentiment", SentimentStrategy())
    return eng


@pytest.fixture
def context():
    return StrategyContext(
        trade_date=date(2026, 5, 23),
        market_data={
            "000001.SZ": {"close": 10.0, "pct_change": 2.0},
        },
        indicators={},
        analysis={
            "000001.SZ": {
                "text_score": 2.0, "market_score": 1.5,
                "integrated_score": 1.8, "behavior_label": "做多主导",
            }
        },
        popularity={
            "000001.SZ": {"rank": 10, "is_new_entry": True, "rank_change": -5}
        },
        positions={},
    )


class TestStrategyEngine:
    def test_registered_strategies(self, engine):
        assert "popularity" in engine.list_strategies()
        assert "sentiment" in engine.list_strategies()

    def test_run_unknown_strategy_raises(self, engine):
        with pytest.raises(ValueError, match="not found"):
            import asyncio
            asyncio.get_event_loop().run_until_complete(
                engine.run_strategy("unknown", [], StrategyContext(
                    trade_date=date.today(), market_data={}, indicators={},
                    analysis={}, popularity={}, positions={},
                ))
            )


class TestPopularityStrategy:
    def test_new_entry_generates_buy_signal(self, context):
        strategy = PopularityStrategy()
        import asyncio
        signals = asyncio.get_event_loop().run_until_complete(
            strategy.generate_signals(["000001.SZ"], context)
        )
        assert len(signals) > 0
        assert signals[0].signal_type == SignalType.BUY


class TestSentimentStrategy:
    def test_high_score_generates_buy_signal(self, context):
        strategy = SentimentStrategy()
        import asyncio
        signals = asyncio.get_event_loop().run_until_complete(
            strategy.generate_signals(["000001.SZ"], context)
        )
        assert len(signals) > 0
        assert signals[0].signal_type == SignalType.BUY
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/quant/test_strategy_engine.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement StrategyEngine and built-in strategies**

```python
# src/stock_service/quant/application/strategy_engine.py
from datetime import date
import logging

from stock_service.quant.domain.strategy_interface import (
    BaseStrategy, Signal, SignalType, StrategyContext,
)

logger = logging.getLogger(__name__)


class StrategyEngine:
    """Strategy dispatcher - manages and runs strategies."""

    def __init__(self):
        self._strategies: dict[str, BaseStrategy] = {}

    def register(self, name: str, strategy: BaseStrategy) -> None:
        self._strategies[name] = strategy

    def list_strategies(self) -> list[str]:
        return list(self._strategies.keys())

    async def run_strategy(
        self,
        strategy_name: str,
        stock_codes: list[str],
        context: StrategyContext,
    ) -> list[Signal]:
        strategy = self._strategies.get(strategy_name)
        if not strategy:
            raise ValueError(f"Strategy '{strategy_name}' not found")
        return await strategy.generate_signals(stock_codes, context)

    async def run_all(
        self,
        stock_codes: list[str],
        context: StrategyContext,
    ) -> dict[str, list[Signal]]:
        results = {}
        for name, strategy in self._strategies.items():
            try:
                results[name] = await strategy.generate_signals(stock_codes, context)
            except Exception as e:
                logger.error(f"Strategy {name} failed: {e}")
                results[name] = []
        return results


class PopularityStrategy(BaseStrategy):
    """Generate signals based on THS popularity ranking changes."""

    def __init__(self, params: dict | None = None):
        self._params = params or {
            "top_n": 50,
            "new_entry_score_boost": 1.2,
            "rank_drop_threshold": -20,
        }

    @property
    def name(self) -> str:
        return "人气榜策略"

    @property
    def strategy_type(self) -> str:
        return "popularity"

    def get_params(self) -> dict:
        return self._params.copy()

    def set_params(self, params: dict) -> None:
        self._params.update(params)

    async def generate_signals(
        self, stock_codes: list[str], context: StrategyContext
    ) -> list[Signal]:
        signals = []
        for code in stock_codes:
            pop = context.popularity.get(code)
            if not pop:
                continue

            rank = pop.get("rank", 999)
            if rank > self._params["top_n"]:
                continue

            is_new = pop.get("is_new_entry", False)
            rank_change = pop.get("rank_change", 0)

            if is_new:
                signals.append(Signal(
                    code=code, signal_type=SignalType.BUY,
                    score=min(1.0, 0.8 * self._params["new_entry_score_boost"]),
                    reason=f"新进入人气榜第{rank}名",
                ))
            elif rank_change <= self._params["rank_drop_threshold"]:
                signals.append(Signal(
                    code=code, signal_type=SignalType.BUY,
                    score=0.7,
                    reason=f"人气排名大幅下降{rank_change}位至第{rank}名",
                ))
            elif rank_change >= 30:
                signals.append(Signal(
                    code=code, signal_type=SignalType.SELL,
                    score=0.6,
                    reason=f"人气排名大幅上升{rank_change}位至第{rank}名，可能过热",
                ))

        return signals


class SentimentStrategy(BaseStrategy):
    """Generate signals based on text/market analysis scores."""

    def __init__(self, params: dict | None = None):
        self._params = params or {
            "text_weight": 0.55,
            "market_weight": 0.45,
            "buy_threshold": 2.0,
            "sell_threshold": -1.5,
        }

    @property
    def name(self) -> str:
        return "情绪驱动策略"

    @property
    def strategy_type(self) -> str:
        return "sentiment"

    def get_params(self) -> dict:
        return self._params.copy()

    def set_params(self, params: dict) -> None:
        self._params.update(params)

    async def generate_signals(
        self, stock_codes: list[str], context: StrategyContext
    ) -> list[Signal]:
        signals = []
        for code in stock_codes:
            analysis = context.analysis.get(code)
            if not analysis:
                continue

            text_score = analysis.get("text_score", 0) or 0
            market_score = analysis.get("market_score", 0) or 0
            integrated = (
                text_score * self._params["text_weight"]
                + market_score * self._params["market_weight"]
            )

            if integrated >= self._params["buy_threshold"]:
                signals.append(Signal(
                    code=code, signal_type=SignalType.BUY,
                    score=min(1.0, integrated / 5.0),
                    reason=f"综合情绪分 {integrated:.2f} >= {self._params['buy_threshold']}",
                ))
            elif integrated <= self._params["sell_threshold"]:
                signals.append(Signal(
                    code=code, signal_type=SignalType.SELL,
                    score=min(1.0, abs(integrated) / 5.0),
                    reason=f"综合情绪分 {integrated:.2f} <= {self._params['sell_threshold']}",
                ))

        return signals
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/quant/test_strategy_engine.py -v
```

Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/stock_service/quant/application/strategy_engine.py tests/quant/test_strategy_engine.py
git commit -m "feat(quant): add strategy engine with popularity and sentiment strategies"
```

---

## Task 8: Technical & MultiFactor Strategies

**Files:**
- Modify: `src/stock_service/quant/application/strategy_engine.py`
- Modify: `tests/quant/test_strategy_engine.py`

- [ ] **Step 1: Add tests for technical and multi-factor strategies**

Append to `tests/quant/test_strategy_engine.py`:

```python
from stock_service.quant.application.strategy_engine import (
    TechnicalStrategy, MultiFactorStrategy,
)


class TestTechnicalStrategy:
    def test_ma_crossover_generates_buy(self):
        strategy = TechnicalStrategy()
        context = StrategyContext(
            trade_date=date(2026, 5, 23),
            market_data={"000001.SZ": {"close": 10.0}},
            indicators={
                "000001.SZ": {
                    "ma5": 10.2, "ma20": 9.8, "rsi": 55.0,
                    "macd": 0.1, "macd_signal": 0.05, "macd_hist": 0.05,
                }
            },
            analysis={}, popularity={}, positions={},
        )
        import asyncio
        signals = asyncio.get_event_loop().run_until_complete(
            strategy.generate_signals(["000001.SZ"], context)
        )
        # MA5 > MA20 is a buy signal
        buy_signals = [s for s in signals if s.signal_type == SignalType.BUY]
        assert len(buy_signals) > 0

    def test_oversold_rsi_generates_buy(self):
        strategy = TechnicalStrategy()
        context = StrategyContext(
            trade_date=date(2026, 5, 23),
            market_data={"000001.SZ": {"close": 10.0}},
            indicators={
                "000001.SZ": {
                    "ma5": 9.5, "ma20": 10.0, "rsi": 25.0,
                    "macd": -0.1, "macd_signal": -0.05, "macd_hist": -0.05,
                }
            },
            analysis={}, popularity={}, positions={},
        )
        import asyncio
        signals = asyncio.get_event_loop().run_until_complete(
            strategy.generate_signals(["000001.SZ"], context)
        )
        buy_signals = [s for s in signals if s.signal_type == SignalType.BUY]
        assert len(buy_signals) > 0


class TestMultiFactorStrategy:
    def test_combined_signals(self):
        strategy = MultiFactorStrategy()
        context = StrategyContext(
            trade_date=date(2026, 5, 23),
            market_data={"000001.SZ": {"close": 10.0}},
            indicators={
                "000001.SZ": {"ma5": 10.2, "ma20": 9.8, "rsi": 55.0}
            },
            analysis={
                "000001.SZ": {"integrated_score": 2.5}
            },
            popularity={
                "000001.SZ": {"rank": 10, "is_new_entry": True, "rank_change": 0}
            },
            positions={},
        )
        import asyncio
        signals = asyncio.get_event_loop().run_until_complete(
            strategy.generate_signals(["000001.SZ"], context)
        )
        assert len(signals) > 0
```

- [ ] **Step 2: Implement TechnicalStrategy and MultiFactorStrategy**

Append to `src/stock_service/quant/application/strategy_engine.py`:

```python
class TechnicalStrategy(BaseStrategy):
    """Generate signals based on technical indicators."""

    def __init__(self, params: dict | None = None):
        self._params = params or {
            "ma_short": 5,
            "ma_long": 20,
            "rsi_overbought": 70,
            "rsi_oversold": 30,
        }

    @property
    def name(self) -> str:
        return "技术面策略"

    @property
    def strategy_type(self) -> str:
        return "technical"

    def get_params(self) -> dict:
        return self._params.copy()

    def set_params(self, params: dict) -> None:
        self._params.update(params)

    async def generate_signals(
        self, stock_codes: list[str], context: StrategyContext
    ) -> list[Signal]:
        signals = []
        for code in stock_codes:
            ind = context.indicators.get(code)
            if not ind:
                continue

            ma_short = ind.get(f"ma{self._params['ma_short']}")
            ma_long = ind.get(f"ma{self._params['ma_long']}")
            rsi = ind.get("rsi")
            macd = ind.get("macd")
            macd_signal = ind.get("macd_signal")

            reasons = []
            score = 0.0

            # MA crossover
            if ma_short and ma_long:
                if ma_short > ma_long:
                    score += 0.3
                    reasons.append(f"MA{self._params['ma_short']}上穿MA{self._params['ma_long']}")
                else:
                    score -= 0.3
                    reasons.append(f"MA{self._params['ma_short']}下穿MA{self._params['ma_long']}")

            # RSI
            if rsi is not None:
                if rsi <= self._params["rsi_oversold"]:
                    score += 0.3
                    reasons.append(f"RSI超卖({rsi:.1f})")
                elif rsi >= self._params["rsi_overbought"]:
                    score -= 0.3
                    reasons.append(f"RSI超买({rsi:.1f})")

            # MACD
            if macd is not None and macd_signal is not None:
                if macd > macd_signal:
                    score += 0.2
                    reasons.append("MACD金叉")
                else:
                    score -= 0.2
                    reasons.append("MACD死叉")

            if score > 0.3:
                signals.append(Signal(
                    code=code, signal_type=SignalType.BUY,
                    score=min(1.0, score), reason="; ".join(reasons),
                ))
            elif score < -0.3:
                signals.append(Signal(
                    code=code, signal_type=SignalType.SELL,
                    score=min(1.0, abs(score)), reason="; ".join(reasons),
                ))

        return signals


class MultiFactorStrategy(BaseStrategy):
    """Combine multiple signal sources with configurable weights."""

    def __init__(self, params: dict | None = None):
        self._params = params or {
            "weights": {
                "popularity": 0.25,
                "sentiment": 0.35,
                "technical": 0.40,
            },
            "buy_threshold": 0.6,
            "sell_threshold": -0.4,
        }
        self._sub_strategies = {
            "popularity": PopularityStrategy(),
            "sentiment": SentimentStrategy(),
            "technical": TechnicalStrategy(),
        }

    @property
    def name(self) -> str:
        return "多因子策略"

    @property
    def strategy_type(self) -> str:
        return "multi_factor"

    def get_params(self) -> dict:
        return self._params.copy()

    def set_params(self, params: dict) -> None:
        self._params.update(params)
        if "weights" in params:
            self._params["weights"] = params["weights"]

    async def generate_signals(
        self, stock_codes: list[str], context: StrategyContext
    ) -> list[Signal]:
        # Run all sub-strategies
        sub_signals: dict[str, dict[str, float]] = {}
        sub_reasons: dict[str, dict[str, str]] = {}

        for factor_name, strategy in self._sub_strategies.items():
            signals = await strategy.generate_signals(stock_codes, context)
            for sig in signals:
                if sig.code not in sub_signals:
                    sub_signals[sig.code] = {}
                    sub_reasons[sig.code] = {}
                direction = 1.0 if sig.signal_type == SignalType.BUY else -1.0
                sub_signals[sig.code][factor_name] = direction * sig.score
                sub_reasons[sig.code][factor_name] = sig.reason

        # Combine signals with weights
        weights = self._params["weights"]
        results = []
        for code, factor_scores in sub_signals.items():
            combined = sum(
                factor_scores.get(factor, 0) * weight
                for factor, weight in weights.items()
            )
            if combined >= self._params["buy_threshold"]:
                reasons = [sub_reasons[code].get(f, "") for f in weights if f in sub_reasons.get(code, {})]
                results.append(Signal(
                    code=code, signal_type=SignalType.BUY,
                    score=min(1.0, combined),
                    reason=f"多因子综合分{combined:.2f}: " + "; ".join(filter(None, reasons)),
                ))
            elif combined <= self._params["sell_threshold"]:
                reasons = [sub_reasons[code].get(f, "") for f in weights if f in sub_reasons.get(code, {})]
                results.append(Signal(
                    code=code, signal_type=SignalType.SELL,
                    score=min(1.0, abs(combined)),
                    reason=f"多因子综合分{combined:.2f}: " + "; ".join(filter(None, reasons)),
                ))

        return results
```

- [ ] **Step 3: Run tests**

```bash
python -m pytest tests/quant/test_strategy_engine.py -v
```

Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add src/stock_service/quant/application/strategy_engine.py tests/quant/test_strategy_engine.py
git commit -m "feat(quant): add technical and multi-factor strategies"
```

---

## Task 9: Infrastructure - Data Provider & Analysis Adapter

**Files:**
- Create: `src/stock_service/quant/infrastructure/__init__.py`
- Create: `src/stock_service/quant/infrastructure/data_provider.py`
- Create: `src/stock_service/quant/infrastructure/analysis_adapter.py`

- [ ] **Step 1: Create __init__.py**

Empty file.

- [ ] **Step 2: Implement QuantDataProvider**

```python
# src/stock_service/quant/infrastructure/data_provider.py
import logging
from datetime import date, timedelta

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from stock_service.crud import quant_crud

logger = logging.getLogger(__name__)


class QuantDataProvider:
    """Unified data provider for quant module."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def fetch_daily_kline(
        self, code: str, start_date: date, end_date: date
    ) -> pd.DataFrame:
        """Fetch daily kline data from DB, return as DataFrame."""
        rows = await quant_crud.get_stock_daily(
            self._session, code, start_date=start_date, end_date=end_date
        )
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        return df.sort_values("trade_date").reset_index(drop=True)

    async def fetch_kline_for_indicators(
        self, code: str, trade_date: date, lookback_days: int = 365
    ) -> pd.DataFrame:
        """Fetch enough history for indicator calculation."""
        start = trade_date - timedelta(days=lookback_days)
        return await self.fetch_daily_kline(code, start, trade_date)

    async def import_csv(self, file_path: str) -> int:
        """Import daily kline data from CSV file."""
        df = pd.read_csv(file_path)
        required_cols = {"code", "trade_date", "open", "high", "low", "close", "volume"}
        missing = required_cols - set(df.columns)
        if missing:
            raise ValueError(f"CSV missing columns: {missing}")

        records = df.to_dict("records")
        for row in records:
            row["trade_date"] = pd.to_datetime(row["trade_date"]).date()
        return await quant_crud.batch_upsert_stock_daily(self._session, records)

    async def get_indicators(self, code: str, trade_date: date) -> dict:
        """Get pre-computed indicators from stock_indicator table."""
        row = await quant_crud.get_stock_indicator(
            self._session, code, trade_date=trade_date
        )
        if not row:
            return {}
        return {
            "ma5": float(row["ma5"]) if row.get("ma5") else None,
            "ma20": float(row["ma20"]) if row.get("ma20") else None,
            "rsi": float(row["rsi"]) if row.get("rsi") else None,
            "macd": float(row["macd"]) if row.get("macd") else None,
        }

    async def batch_import_from_akshare(
        self, codes: list[str], start_date: date, end_date: date
    ) -> int:
        """Fetch and import daily data from akshare for multiple stocks."""
        import asyncio
        import akshare as ak

        total = 0
        for code in codes:
            try:
                symbol = code.split(".")[0]
                df = await asyncio.to_thread(
                    ak.stock_zh_a_hist,
                    symbol=symbol,
                    period="daily",
                    start_date=start_date.strftime("%Y%m%d"),
                    end_date=end_date.strftime("%Y%m%d"),
                    adjust="qfq",
                )
                if df.empty:
                    continue

                df = df.rename(columns={
                    "日期": "trade_date", "开盘": "open", "最高": "high",
                    "最低": "low", "收盘": "close", "成交量": "volume",
                    "成交额": "amount",
                })
                df["code"] = code
                df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date

                records = df[["code", "trade_date", "open", "high", "low", "close", "volume", "amount"]].to_dict("records")
                await quant_crud.batch_upsert_stock_daily(self._session, records)
                total += len(records)
            except Exception as e:
                logger.warning(f"Failed to fetch {code}: {e}")

        return total
```

- [ ] **Step 3: Implement AnalysisAdapter**

```python
# src/stock_service/quant/infrastructure/analysis_adapter.py
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from stock_service.crud import v2_crud


class AnalysisAdapter:
    """Adapter to read analysis results from v2 tables for quant strategies."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_analysis_signals(self, codes: list[str]) -> dict[str, dict]:
        """Get latest analysis results for given stock codes."""
        result = {}
        for code in codes:
            analysis = await v2_crud.get_latest_stock_analysis(self._session, code)
            if analysis:
                result[code] = {
                    "text_score": float(analysis.get("text_score", 0) or 0),
                    "market_score": float(analysis.get("market_score", 0) or 0),
                    "integrated_score": float(analysis.get("integrated_score", 0) or 0),
                    "behavior_label": analysis.get("behavior_label", ""),
                    "decision": analysis.get("decision", ""),
                }
        return result

    async def get_popularity_data(self, codes: list[str], trade_date: date | None = None) -> dict[str, dict]:
        """Get popularity ranking data for given stock codes."""
        result = {}
        for code in codes:
            snapshot = await v2_crud.get_latest_popularity_by_code(self._session, code)
            if snapshot:
                result[code] = {
                    "rank": snapshot.get("popularity_rank", 999),
                    "score": float(snapshot.get("popularity_score", 0) or 0),
                    "is_new_entry": snapshot.get("is_new_entry", False),
                    "rank_change": snapshot.get("rank_change", 0) or 0,
                }
        return result

    async def get_latest_popularity_codes(self, limit: int = 200) -> list[str]:
        """Get latest popularity ranking stock codes."""
        snapshots = await v2_crud.get_latest_popularity(self._session, limit=limit)
        return [s["stock_code"] for s in snapshots]
```

- [ ] **Step 4: Commit**

```bash
git add src/stock_service/quant/infrastructure/
git commit -m "feat(quant): add data provider and analysis adapter"
```

---

## Task 10: Pydantic Schemas

**Files:**
- Create: `src/stock_service/quant/schemas.py`

- [ ] **Step 1: Create quant schemas**

```python
# src/stock_service/quant/schemas.py
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


# ── Strategy ──

class StrategyCreate(BaseModel):
    name: str
    type: Literal["popularity", "sentiment", "technical", "multi_factor"]
    params: dict = {}
    description: str | None = None


class StrategyUpdate(BaseModel):
    name: str | None = None
    params: dict | None = None
    description: str | None = None
    is_active: bool | None = None


class StrategyResponse(BaseModel):
    id: int
    name: str
    type: str
    params: dict | None
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ── Backtest ──

class BacktestRequest(BaseModel):
    strategy_id: int
    start_date: date
    end_date: date
    initial_capital: float = 1_000_000.0
    commission_rate: float = 0.0003
    stamp_tax: float = 0.001
    slippage: float = 0.002
    max_position_pct: float = 0.2
    max_holdings: int = 10
    stop_loss_pct: float = -0.08
    stock_codes: list[str] | None = None


class BacktestResponse(BaseModel):
    id: int
    strategy_id: int
    start_date: date
    end_date: date
    total_return: float | None
    annual_return: float | None
    max_drawdown: float | None
    sharpe_ratio: float | None
    win_rate: float | None
    total_trades: int | None
    created_at: datetime


class BacktestTradeResponse(BaseModel):
    code: str
    side: str
    price: float | None
    quantity: int | None
    trade_date: date
    pnl: float | None
    signal_source: str | None


class BacktestNavResponse(BaseModel):
    trade_date: date
    nav: float | None
    total_assets: float | None
    cash: float | None
    position_value: float | None
    benchmark_nav: float | None


# ── Sim Trading ──

class SimAccountCreate(BaseModel):
    account_name: str
    initial_capital: float = 1_000_000.0
    strategy_id: int | None = None
    config: dict | None = None


class SimAccountResponse(BaseModel):
    id: int
    user_id: int
    account_name: str
    initial_capital: float
    current_capital: float
    total_assets: float
    status: str
    strategy_id: int | None
    created_at: datetime


class TradeRequest(BaseModel):
    account_id: int
    code: str
    side: Literal["buy", "sell"]
    quantity: int
    price: float | None = None


class PositionResponse(BaseModel):
    code: str
    quantity: int
    available_quantity: int | None
    avg_price: float
    current_price: float | None
    market_value: float | None
    pnl: float | None
    pnl_pct: float | None


class TradeOrderResponse(BaseModel):
    id: int
    code: str
    side: str
    price: float | None
    quantity: int | None
    status: str | None
    commission: float | None
    created_at: datetime


# ── Feedback ──

class FeedbackInsightResponse(BaseModel):
    overall: dict
    by_signal: dict
    suggestions: list[str]


class WeightAdjustmentRequest(BaseModel):
    strategy_id: int
    adjustments: dict[str, float]
    reason: str
```

- [ ] **Step 2: Commit**

```bash
git add src/stock_service/quant/schemas.py
git commit -m "feat(quant): add Pydantic schemas for quant module"
```

---

## Task 11: Backtest Engine

**Files:**
- Create: `src/stock_service/quant/application/backtest_engine.py`
- Create: `tests/quant/test_backtest_engine.py`

- [ ] **Step 1: Write tests for backtest engine**

```python
# tests/quant/test_backtest_engine.py
import pytest
from datetime import date
from decimal import Decimal
from stock_service.quant.application.backtest_engine import BacktestEngine
from stock_service.quant.domain.backtest_rules import BacktestConfig


class TestBacktestMetrics:
    def test_calculate_metrics_basic(self):
        engine = BacktestEngine.__new__(BacktestEngine)
        nav_series = [
            {"trade_date": date(2026, 1, 1), "total_assets": 1000000},
            {"trade_date": date(2026, 1, 2), "total_assets": 1010000},
            {"trade_date": date(2026, 1, 3), "total_assets": 1005000},
            {"trade_date": date(2026, 1, 4), "total_assets": 1020000},
        ]
        trades = [
            {"pnl": 10000, "side": "sell"},
            {"pnl": -5000, "side": "sell"},
        ]
        metrics = engine._calculate_metrics(
            nav_series=nav_series,
            trades=trades,
            initial_capital=1000000,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 4),
        )
        assert metrics["total_return"] == 0.02  # 2%
        assert metrics["win_rate"] == 0.5
        assert metrics["total_trades"] == 2
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/quant/test_backtest_engine.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement BacktestEngine**

```python
# src/stock_service/quant/application/backtest_engine.py
import logging
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from stock_service.crud import quant_crud, v2_crud
from stock_service.quant.application.strategy_engine import StrategyEngine
from stock_service.quant.domain.backtest_rules import (
    BacktestConfig, BacktestRules, Position,
)
from stock_service.quant.domain.risk_manager import RiskManager
from stock_service.quant.domain.strategy_interface import (
    SignalType, StrategyContext,
)
from stock_service.quant.infrastructure.analysis_adapter import AnalysisAdapter

logger = logging.getLogger(__name__)


class BacktestEngine:
    """Backtesting engine - runs strategies against historical data."""

    def __init__(self, session: AsyncSession):
        self._session = session
        self._rules = BacktestRules()
        self._risk = RiskManager()

    async def run(
        self,
        strategy_id: int,
        stock_codes: list[str],
        start_date: date,
        end_date: date,
        config: BacktestConfig,
        strategy_engine: StrategyEngine,
    ) -> dict:
        """Run backtest and return results."""
        # Get strategy
        strategy = await quant_crud.get_strategy(self._session, strategy_id)
        if not strategy:
            raise ValueError(f"Strategy {strategy_id} not found")

        strategy_name = strategy["type"]
        strategy_engine._strategies[strategy_name].set_params(strategy.get("params") or {})

        analysis_adapter = AnalysisAdapter(self._session)

        # Initialize state
        cash = config.initial_capital
        positions: dict[str, Position] = {}
        nav_series = []
        trades = []

        # Get trading dates (from stock_daily)
        trading_dates = await self._get_trading_dates(
            stock_codes[0] if stock_codes else None, start_date, end_date
        )

        for trade_date in trading_dates:
            # 1. Update T+1 available quantities
            self._rules.update_available_quantity(positions)

            # 2. Build context
            context = await self._build_context(
                stock_codes, trade_date, positions, analysis_adapter
            )

            # 3. Generate signals
            signals = await strategy_engine.run_strategy(
                strategy_name, stock_codes, context
            )

            # 4. Filter signals (risk management)
            filtered = self._risk.filter_signals(
                signals, positions, cash + sum(
                    p.market_value for p in positions.values()
                ), config
            )

            # 5. Execute trades
            for signal in filtered:
                market_data = context.market_data.get(signal.code, {})
                price = market_data.get("close", 0)
                if price <= 0:
                    continue

                if signal.signal_type == SignalType.BUY:
                    total_assets = cash + sum(p.market_value for p in positions.values())
                    qty = self._risk.calculate_buy_quantity(
                        price, cash, total_assets, config
                    )
                    if qty <= 0:
                        continue

                    cost = self._rules.calculate_buy_cost(price, qty, config)
                    if cost > cash:
                        continue

                    cash -= cost
                    positions[signal.code] = Position(
                        code=signal.code, quantity=qty, avg_price=price,
                        available_quantity=0,  # T+1
                        market_value=price * qty,
                        pnl=0, pnl_pct=0,
                    )
                    trades.append({
                        "code": signal.code, "side": "buy",
                        "price": price, "quantity": qty,
                        "trade_date": trade_date,
                        "pnl": 0, "signal_source": strategy_name,
                    })

                elif signal.signal_type == SignalType.SELL:
                    pos = positions.get(signal.code)
                    if not pos or pos.available_quantity <= 0:
                        continue

                    revenue = self._rules.calculate_sell_revenue(
                        price, pos.quantity, config
                    )
                    pnl = revenue - (pos.avg_price * pos.quantity)
                    cash += revenue
                    del positions[signal.code]
                    trades.append({
                        "code": signal.code, "side": "sell",
                        "price": price, "quantity": pos.quantity,
                        "trade_date": trade_date,
                        "pnl": round(pnl, 2), "signal_source": strategy_name,
                    })

            # 6. Update positions market value
            for code, pos in positions.items():
                price = context.market_data.get(code, {}).get("close", pos.avg_price)
                pos.market_value = price * pos.quantity
                pos.pnl = (price - pos.avg_price) * pos.quantity
                pos.pnl_pct = (price - pos.avg_price) / pos.avg_price if pos.avg_price else 0

            # 7. Record daily NAV
            position_value = sum(p.market_value for p in positions.values())
            total_assets = cash + position_value
            nav_series.append({
                "trade_date": trade_date,
                "nav": total_assets / config.initial_capital,
                "total_assets": total_assets,
                "cash": cash,
                "position_value": position_value,
                "benchmark_nav": None,
            })

        # Calculate metrics
        metrics = self._calculate_metrics(
            nav_series, trades, config.initial_capital, start_date, end_date
        )

        # Save results
        backtest_result = await quant_crud.create_backtest_result(self._session, {
            "strategy_id": strategy_id,
            "start_date": start_date,
            "end_date": end_date,
            "annual_return": metrics.get("annual_return"),
            "max_drawdown": metrics.get("max_drawdown"),
            "sharpe": metrics.get("sharpe_ratio"),
            "win_rate": metrics.get("win_rate"),
        })

        # Save trades
        for trade in trades:
            trade["backtest_id"] = backtest_result["id"]
        await quant_crud.batch_insert_backtest_trades(self._session, trades)

        # Save NAV
        for nav in nav_series:
            nav["backtest_id"] = backtest_result["id"]
        await quant_crud.batch_insert_backtest_nav(self._session, nav_series)

        return {
            "backtest_id": backtest_result["id"],
            "metrics": metrics,
            "trade_count": len(trades),
            "nav_count": len(nav_series),
        }

    async def _get_trading_dates(
        self, code: str | None, start_date: date, end_date: date
    ) -> list[date]:
        if not code:
            return []
        rows = await quant_crud.get_stock_daily(
            self._session, code, start_date=start_date, end_date=end_date
        )
        return sorted(set(r["trade_date"] for r in rows))

    async def _build_context(
        self, stock_codes: list[str], trade_date: date,
        positions: dict[str, Position], analysis_adapter: AnalysisAdapter,
    ) -> StrategyContext:
        market_data = {}
        indicators = {}
        for code in stock_codes:
            daily = await quant_crud.get_stock_daily(
                self._session, code, start_date=trade_date, end_date=trade_date
            )
            if daily:
                market_data[code] = daily[0]

            ind = await quant_crud.get_stock_indicator(
                self._session, code, trade_date=trade_date
            )
            if ind:
                indicators[code] = {k: float(v) for k, v in ind.items() if isinstance(v, (int, float, Decimal)) and k not in ("id",)}

        analysis = await analysis_adapter.get_analysis_signals(stock_codes)
        popularity = await analysis_adapter.get_popularity_data(stock_codes, trade_date)

        return StrategyContext(
            trade_date=trade_date,
            market_data=market_data,
            indicators=indicators,
            analysis=analysis,
            popularity=popularity,
            positions={c: {"quantity": p.quantity, "avg_price": p.avg_price} for c, p in positions.items()},
        )

    def _calculate_metrics(
        self, nav_series: list[dict], trades: list[dict],
        initial_capital: float, start_date: date, end_date: date,
    ) -> dict:
        if not nav_series:
            return {}

        final_assets = nav_series[-1]["total_assets"]
        total_return = (final_assets - initial_capital) / initial_capital

        # Max drawdown
        peak = initial_capital
        max_dd = 0
        for nav in nav_series:
            ta = nav["total_assets"]
            if ta > peak:
                peak = ta
            dd = (peak - ta) / peak
            if dd > max_dd:
                max_dd = dd

        # Win rate
        sell_trades = [t for t in trades if t["side"] == "sell"]
        wins = len([t for t in sell_trades if t.get("pnl", 0) > 0])
        win_rate = wins / len(sell_trades) if sell_trades else 0

        # Annualized return
        days = (end_date - start_date).days
        annual_return = ((1 + total_return) ** (365 / max(days, 1))) - 1 if days > 0 else 0

        # Sharpe ratio (simplified)
        if len(nav_series) > 1:
            returns = []
            for i in range(1, len(nav_series)):
                prev = nav_series[i - 1]["total_assets"]
                curr = nav_series[i]["total_assets"]
                returns.append((curr - prev) / prev if prev else 0)
            import statistics
            mean_ret = statistics.mean(returns)
            std_ret = statistics.stdev(returns) if len(returns) > 1 else 1
            sharpe = (mean_ret * 252 - 0.03) / (std_ret * (252 ** 0.5)) if std_ret > 0 else 0
        else:
            sharpe = 0

        return {
            "total_return": round(total_return, 4),
            "annual_return": round(annual_return, 4),
            "max_drawdown": round(max_dd, 4),
            "sharpe_ratio": round(sharpe, 4),
            "win_rate": round(win_rate, 4),
            "total_trades": len(trades),
        }
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/quant/test_backtest_engine.py -v
```

Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/stock_service/quant/application/backtest_engine.py tests/quant/test_backtest_engine.py
git commit -m "feat(quant): add backtest engine"
```

---

## Task 12: Sim Trading Engine

**Files:**
- Create: `src/stock_service/quant/application/sim_trading_engine.py`
- Create: `tests/quant/test_sim_trading_engine.py`

- [ ] **Step 1: Write tests**

```python
# tests/quant/test_sim_trading_engine.py
import pytest
from stock_service.quant.application.sim_trading_engine import SimTradingEngine


class TestCalculateBuyCost:
    def test_basic_buy_cost(self):
        engine = SimTradingEngine.__new__(SimTradingEngine)
        cost = engine._calculate_buy_cost(10.0, 1000, 0.0003, 0.002)
        expected_price = 10.0 * 1.002
        expected_amount = expected_price * 1000
        expected_commission = max(expected_amount * 0.0003, 5)
        assert abs(cost - (expected_amount + expected_commission)) < 0.01


class TestCalculateSellRevenue:
    def test_basic_sell_revenue(self):
        engine = SimTradingEngine.__new__(SimTradingEngine)
        revenue = engine._calculate_sell_revenue(10.0, 1000, 0.0003, 0.001, 0.002)
        expected_price = 10.0 * 0.998
        expected_amount = expected_price * 1000
        expected_commission = max(expected_amount * 0.0003, 5)
        expected_stamp = expected_amount * 0.001
        assert abs(revenue - (expected_amount - expected_commission - expected_stamp)) < 0.01
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/quant/test_sim_trading_engine.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement SimTradingEngine**

```python
# src/stock_service/quant/application/sim_trading_engine.py
import logging
from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from stock_service.crud import quant_crud

logger = logging.getLogger(__name__)


class SimTradingEngine:
    """Simulated trading engine with T+1 and risk management."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def create_account(
        self, user_id: int, account_name: str,
        initial_capital: float, strategy_id: int | None = None,
        config: dict | None = None,
    ) -> dict:
        """Create a new simulated trading account."""
        default_config = {
            "commission_rate": 0.0003,
            "stamp_tax": 0.001,
            "slippage": 0.002,
            "max_position_pct": 0.2,
            "max_holdings": 10,
            "stop_loss_pct": -0.08,
        }
        if config:
            default_config.update(config)

        return await quant_crud.create_sim_account(self._session, {
            "user_id": user_id,
            "account_name": account_name,
            "initial_capital": Decimal(str(initial_capital)),
            "current_capital": Decimal(str(initial_capital)),
            "total_assets": Decimal(str(initial_capital)),
            "strategy_id": strategy_id,
            "config": default_config,
        })

    async def verify_ownership(self, user_id: int, account_id: int) -> bool:
        """Verify account belongs to user."""
        account = await quant_crud.get_sim_account(self._session, account_id)
        return account is not None and account["user_id"] == user_id

    async def buy(
        self, account_id: int, code: str, quantity: int,
        price: float, current_price: float | None = None,
    ) -> dict:
        """Execute a buy order."""
        account = await quant_crud.get_sim_account(self._session, account_id)
        if not account:
            raise ValueError("Account not found")
        if account["status"] != "active":
            raise ValueError("Account is not active")

        config = account.get("config") or {}
        exec_price = current_price or price
        cost = self._calculate_buy_cost(
            exec_price, quantity,
            config.get("commission_rate", 0.0003),
            config.get("slippage", 0.002),
        )

        if cost > float(account["current_capital"]):
            raise ValueError(f"Insufficient capital: need {cost}, have {account['current_capital']}")

        # Deduct capital
        new_capital = float(account["current_capital"]) - cost
        await quant_crud.update_sim_account(self._session, account_id, {
            "current_capital": Decimal(str(round(new_capital, 2))),
        })

        # Create/update position (T+1: available_quantity = 0)
        existing = await quant_crud.get_position(self._session, account_id, code)
        if existing:
            new_qty = existing["quantity"] + quantity
            new_avg = (
                (float(existing["avg_price"]) * existing["quantity"] + exec_price * quantity)
                / new_qty
            )
            await quant_crud.update_position(self._session, account_id, code, {
                "quantity": new_qty,
                "avg_price": Decimal(str(round(new_avg, 4))),
                # available_quantity stays same (new shares not sellable today)
            })
        else:
            await quant_crud.create_position(self._session, {
                "account_id": account_id,
                "code": code,
                "quantity": quantity,
                "avg_price": Decimal(str(round(exec_price, 4))),
                "available_quantity": 0,  # T+1
            })

        # Record order
        order = await quant_crud.create_trade_order(self._session, {
            "account_id": account_id,
            "code": code,
            "side": "buy",
            "price": Decimal(str(round(exec_price, 4))),
            "quantity": quantity,
            "status": "filled",
            "commission": Decimal(str(round(cost - exec_price * quantity, 4))),
            "slippage": Decimal(str(round((exec_price - price) * quantity, 4))),
        })

        await self._update_total_assets(account_id)
        return order

    async def sell(
        self, account_id: int, code: str, quantity: int,
        price: float, current_price: float | None = None,
    ) -> dict:
        """Execute a sell order."""
        account = await quant_crud.get_sim_account(self._session, account_id)
        if not account:
            raise ValueError("Account not found")

        position = await quant_crud.get_position(self._session, account_id, code)
        if not position:
            raise ValueError(f"No position for {code}")
        if quantity > position["available_quantity"]:
            raise ValueError(
                f"Insufficient available quantity: {position['available_quantity']} (T+1)"
            )

        config = account.get("config") or {}
        exec_price = current_price or price
        revenue = self._calculate_sell_revenue(
            exec_price, quantity,
            config.get("commission_rate", 0.0003),
            config.get("stamp_tax", 0.001),
            config.get("slippage", 0.002),
        )

        # Add capital
        new_capital = float(account["current_capital"]) + revenue
        await quant_crud.update_sim_account(self._session, account_id, {
            "current_capital": Decimal(str(round(new_capital, 2))),
        })

        # Calculate PnL
        pnl = revenue - (float(position["avg_price"]) * quantity)

        # Update position
        new_qty = position["quantity"] - quantity
        if new_qty <= 0:
            await quant_crud.delete_position(self._session, account_id, code)
        else:
            await quant_crud.update_position(self._session, account_id, code, {
                "quantity": new_qty,
                "available_quantity": position["available_quantity"] - quantity,
            })

        # Record order
        order = await quant_crud.create_trade_order(self._session, {
            "account_id": account_id,
            "code": code,
            "side": "sell",
            "price": Decimal(str(round(exec_price, 4))),
            "quantity": quantity,
            "status": "filled",
            "commission": Decimal(str(round(
                exec_price * quantity * config.get("commission_rate", 0.0003), 4
            ))),
        })

        await self._update_total_assets(account_id)
        return {**order, "pnl": round(pnl, 2)}

    async def daily_settlement(self, account_id: int, trade_date: date) -> list[dict]:
        """Daily settlement: update T+1 quantities and check stop loss."""
        positions = await quant_crud.get_positions(self._session, account_id)
        account = await quant_crud.get_sim_account(self._session, account_id)
        config = account.get("config") or {}
        stop_loss_pct = config.get("stop_loss_pct", -0.08)

        snapshots = []
        triggered_stop_loss = []

        for pos in positions:
            # T+1: make all shares available
            await quant_crud.update_position(self._session, account_id, pos["code"], {
                "available_quantity": pos["quantity"],
            })

            # Get current price (from stock_daily)
            daily = await quant_crud.get_stock_daily(
                self._session, pos["code"],
                start_date=trade_date, end_date=trade_date,
            )
            close_price = float(daily[0]["close"]) if daily else float(pos["avg_price"])

            market_value = close_price * pos["quantity"]
            pnl = (close_price - float(pos["avg_price"])) * pos["quantity"]
            pnl_pct = (close_price - float(pos["avg_price"])) / float(pos["avg_price"]) if pos["avg_price"] else 0

            snapshots.append({
                "account_id": account_id,
                "code": pos["code"],
                "trade_date": trade_date,
                "quantity": pos["quantity"],
                "available_quantity": pos["quantity"],
                "avg_price": pos["avg_price"],
                "close_price": Decimal(str(round(close_price, 4))),
                "market_value": Decimal(str(round(market_value, 2))),
                "pnl": Decimal(str(round(pnl, 2))),
                "pnl_pct": Decimal(str(round(pnl_pct, 4))),
            })

            # Check stop loss
            if pnl_pct <= stop_loss_pct:
                triggered_stop_loss.append(pos["code"])

        # Save snapshots
        if snapshots:
            await quant_crud.batch_insert_position_snapshots(self._session, snapshots)

        # Update total assets
        await self._update_total_assets(account_id)

        return triggered_stop_loss

    async def _update_total_assets(self, account_id: int) -> None:
        """Recalculate and update account total assets."""
        account = await quant_crud.get_sim_account(self._session, account_id)
        positions = await quant_crud.get_positions(self._session, account_id)
        position_value = sum(
            float(p.get("avg_price", 0)) * p["quantity"] for p in positions
        )
        total = float(account["current_capital"]) + position_value
        await quant_crud.update_sim_account(self._session, account_id, {
            "total_assets": Decimal(str(round(total, 2))),
        })

    def _calculate_buy_cost(
        self, price: float, quantity: int,
        commission_rate: float, slippage: float,
    ) -> float:
        actual_price = price * (1 + slippage)
        amount = actual_price * quantity
        commission = max(amount * commission_rate, 5)
        return amount + commission

    def _calculate_sell_revenue(
        self, price: float, quantity: int,
        commission_rate: float, stamp_tax: float, slippage: float,
    ) -> float:
        actual_price = price * (1 - slippage)
        amount = actual_price * quantity
        commission = max(amount * commission_rate, 5)
        stamp = amount * stamp_tax
        return amount - commission - stamp
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/quant/test_sim_trading_engine.py -v
```

Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/stock_service/quant/application/sim_trading_engine.py tests/quant/test_sim_trading_engine.py
git commit -m "feat(quant): add simulated trading engine with T+1 and stop loss"
```

---

## Task 13: Feedback Service

**Files:**
- Create: `src/stock_service/quant/application/feedback_service.py`

- [ ] **Step 1: Implement FeedbackService**

```python
# src/stock_service/quant/application/feedback_service.py
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from stock_service.crud import quant_crud

logger = logging.getLogger(__name__)


class FeedbackService:
    """Closed-loop feedback: analyze backtest results and suggest optimizations."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def analyze_backtest_insights(self, backtest_id: int) -> dict:
        """Analyze backtest results and extract optimization suggestions."""
        trades = await quant_crud.get_backtest_trades(self._session, backtest_id)
        result = await quant_crud.get_backtest_result(self._session, backtest_id)

        if not result:
            raise ValueError(f"Backtest {backtest_id} not found")

        # Group by signal source
        signal_stats = {}
        for trade in trades:
            source = trade.get("signal_source", "unknown")
            if source not in signal_stats:
                signal_stats[source] = {"wins": 0, "losses": 0, "total_pnl": 0, "trades": 0}

            signal_stats[source]["trades"] += 1
            pnl = float(trade.get("pnl", 0) or 0)
            signal_stats[source]["total_pnl"] += pnl
            if pnl > 0:
                signal_stats[source]["wins"] += 1
            elif pnl < 0:
                signal_stats[source]["losses"] += 1

        # Calculate win rates
        for source, stats in signal_stats.items():
            total = stats["wins"] + stats["losses"]
            stats["win_rate"] = round(stats["wins"] / total, 4) if total > 0 else 0
            stats["total_pnl"] = round(stats["total_pnl"], 2)

        # Generate suggestions
        suggestions = self._generate_suggestions(signal_stats)

        return {
            "overall": {
                "win_rate": result.get("win_rate"),
                "sharpe": result.get("sharpe"),
                "max_drawdown": result.get("max_drawdown"),
                "annual_return": result.get("annual_return"),
            },
            "by_signal": signal_stats,
            "suggestions": suggestions,
        }

    def _generate_suggestions(self, signal_stats: dict) -> list[str]:
        suggestions = []
        for source, stats in signal_stats.items():
            if stats["trades"] < 5:
                continue
            if stats["win_rate"] > 0.6:
                suggestions.append(
                    f"{source} 信号胜率 {stats['win_rate']:.1%}，"
                    f"建议提高该信号权重"
                )
            elif stats["win_rate"] < 0.4:
                suggestions.append(
                    f"{source} 信号胜率 {stats['win_rate']:.1%}，"
                    f"建议降低该信号权重或优化规则"
                )
        return suggestions

    async def suggest_weight_adjustment(self, backtest_id: int) -> dict:
        """Suggest weight adjustments for multi-factor strategy."""
        insights = await self.analyze_backtest_insights(backtest_id)
        signal_stats = insights["by_signal"]

        if not signal_stats:
            return {"adjustments": {}, "reason": "Insufficient data"}

        # Find best and worst performing signal
        valid_sources = {k: v for k, v in signal_stats.items() if v["trades"] >= 3}
        if not valid_sources:
            return {"adjustments": {}, "reason": "Insufficient trades per signal"}

        best = max(valid_sources.items(), key=lambda x: x[1]["win_rate"])
        worst = min(valid_sources.items(), key=lambda x: x[1]["win_rate"])

        adjustments = {}
        reasons = []

        if best[1]["win_rate"] > 0.55:
            adjustments[best[0]] = 0.05  # Increase by 5%
            reasons.append(f"{best[0]} 胜率高({best[1]['win_rate']:.1%})，建议加权")

        if worst[1]["win_rate"] < 0.45:
            adjustments[worst[0]] = -0.05  # Decrease by 5%
            reasons.append(f"{worst[0]} 胜率低({worst[1]['win_rate']:.1%})，建议减权")

        return {
            "adjustments": adjustments,
            "reason": "; ".join(reasons) if reasons else "No significant adjustment needed",
            "insights": insights,
        }

    async def log_feedback(
        self, backtest_id: int, strategy_id: int,
        feedback_type: str, before_params: dict,
        after_params: dict, reason: str,
    ) -> dict:
        """Log a feedback action."""
        return await quant_crud.create_feedback_log(self._session, {
            "backtest_id": backtest_id,
            "strategy_id": strategy_id,
            "feedback_type": feedback_type,
            "before_params": before_params,
            "after_params": after_params,
            "reason": reason,
        })
```

- [ ] **Step 2: Commit**

```bash
git add src/stock_service/quant/application/feedback_service.py
git commit -m "feat(quant): add feedback service for closed-loop optimization"
```

---

## Task 14: API Routes

**Files:**
- Create: `src/stock_service/quant/api/__init__.py`
- Create: `src/stock_service/quant/api/routes/__init__.py`
- Create: `src/stock_service/quant/api/routes/strategies.py`
- Create: `src/stock_service/quant/api/routes/backtest.py`
- Create: `src/stock_service/quant/api/routes/sim_trading.py`
- Create: `src/stock_service/quant/api/routes/feedback.py`
- Modify: `src/stock_service/api/app.py`

- [ ] **Step 1: Create __init__.py files**

Empty files for `quant/api/` and `quant/api/routes/`.

- [ ] **Step 2: Create strategies route**

```python
# src/stock_service/quant/api/routes/strategies.py
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
```

- [ ] **Step 3: Create backtest route**

```python
# src/stock_service/quant/api/routes/backtest.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from stock_service.api.dependencies import get_current_user, get_session
from stock_service.crud import quant_crud, v2_crud
from stock_service.quant.application.backtest_engine import BacktestEngine
from stock_service.quant.application.strategy_engine import StrategyEngine
from stock_service.quant.domain.backtest_rules import BacktestConfig
from stock_service.quant.schemas import BacktestRequest, BacktestResponse
from stock_service.schemas.responses import ApiResponse

router = APIRouter(prefix="/api/quant/backtest", tags=["quant-backtest"])

# Shared strategy engine instance
_strategy_engine = StrategyEngine()


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
        snapshots = await v2_crud.get_latest_popularity(session, limit=200)
        codes = [s["stock_code"] for s in snapshots]

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
```

- [ ] **Step 4: Create sim_trading route**

```python
# src/stock_service/quant/api/routes/sim_trading.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from stock_service.api.dependencies import get_current_user, get_session
from stock_service.crud import quant_crud
from stock_service.quant.application.sim_trading_engine import SimTradingEngine
from stock_service.quant.schemas import (
    SimAccountCreate, SimAccountResponse,
    TradeRequest, PositionResponse, TradeOrderResponse,
)
from stock_service.schemas.responses import ApiResponse

router = APIRouter(prefix="/api/quant/sim", tags=["quant-sim"])


@router.get("/accounts", response_model=ApiResponse)
async def list_accounts(
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    accounts = await quant_crud.list_sim_accounts(session, current_user["id"])
    return ApiResponse(code=0, msg="ok", data=accounts)


@router.post("/accounts", response_model=ApiResponse)
async def create_account(
    req: SimAccountCreate,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    engine = SimTradingEngine(session)
    account = await engine.create_account(
        user_id=current_user["id"],
        account_name=req.account_name,
        initial_capital=req.initial_capital,
        strategy_id=req.strategy_id,
        config=req.config,
    )
    return ApiResponse(code=0, msg="ok", data=account)


@router.get("/accounts/{account_id}", response_model=ApiResponse)
async def get_account(
    account_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    engine = SimTradingEngine(session)
    if not await engine.verify_ownership(current_user["id"], account_id):
        raise HTTPException(403, "Not your account")
    account = await quant_crud.get_sim_account(session, account_id)
    return ApiResponse(code=0, msg="ok", data=account)


@router.get("/accounts/{account_id}/positions", response_model=ApiResponse)
async def get_positions(
    account_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    engine = SimTradingEngine(session)
    if not await engine.verify_ownership(current_user["id"], account_id):
        raise HTTPException(403, "Not your account")
    positions = await quant_crud.get_positions(session, account_id)
    return ApiResponse(code=0, msg="ok", data=positions)


@router.get("/accounts/{account_id}/orders", response_model=ApiResponse)
async def get_orders(
    account_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    engine = SimTradingEngine(session)
    if not await engine.verify_ownership(current_user["id"], account_id):
        raise HTTPException(403, "Not your account")
    orders = await quant_crud.list_trade_orders(session, account_id)
    return ApiResponse(code=0, msg="ok", data=orders)


@router.post("/trade", response_model=ApiResponse)
async def execute_trade(
    req: TradeRequest,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    engine = SimTradingEngine(session)
    if not await engine.verify_ownership(current_user["id"], req.account_id):
        raise HTTPException(403, "Not your account")

    try:
        if req.side == "buy":
            result = await engine.buy(
                req.account_id, req.code, req.quantity, req.price, req.price,
            )
        else:
            result = await engine.sell(
                req.account_id, req.code, req.quantity, req.price, req.price,
            )
        return ApiResponse(code=0, msg="ok", data=result)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/settlement", response_model=ApiResponse)
async def daily_settlement(
    account_id: int,
    trade_date: str,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    from datetime import date as date_type
    engine = SimTradingEngine(session)
    if not await engine.verify_ownership(current_user["id"], account_id):
        raise HTTPException(403, "Not your account")

    dt = date_type.fromisoformat(trade_date)
    triggered = await engine.daily_settlement(account_id, dt)
    return ApiResponse(code=0, msg="ok", data={"stop_loss_triggered": triggered})
```

- [ ] **Step 5: Create feedback route**

```python
# src/stock_service/quant/api/routes/feedback.py
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
```

- [ ] **Step 6: Register routes in app.py**

Add to `src/stock_service/api/app.py`:

```python
from stock_service.quant.api.routes import strategies, backtest, sim_trading, feedback

# In the app setup, add:
app.include_router(strategies.router)
app.include_router(backtest.router)
app.include_router(sim_trading.router)
app.include_router(feedback.router)
```

- [ ] **Step 7: Commit**

```bash
git add src/stock_service/quant/api/ src/stock_service/api/app.py
git commit -m "feat(quant): add API routes for strategies, backtest, sim trading, feedback"
```

---

## Task 15: CRUD Extensions for Sim Trading

**Files:**
- Modify: `src/stock_service/crud/quant_crud.py`

- [ ] **Step 1: Add missing CRUD functions for sim trading**

Append to `src/stock_service/crud/quant_crud.py`:

```python
# ── Position (for sim trading) ──

async def create_position(session: AsyncSession, data: dict) -> dict:
    position = PositionAccount(**data)
    session.add(position)
    await session.flush()
    return _rows_to_dicts([position])[0]


async def get_position(
    session: AsyncSession, account_id: int, code: str
) -> dict | None:
    result = await session.execute(
        select(PositionAccount).where(
            PositionAccount.account_id == account_id,
            PositionAccount.code == code,
        )
    )
    row = result.scalars().first()
    return _rows_to_dicts([row])[0] if row else None


async def get_positions(
    session: AsyncSession, account_id: int
) -> list[dict]:
    result = await session.execute(
        select(PositionAccount).where(PositionAccount.account_id == account_id)
    )
    return _rows_to_dicts(result.scalars().all())


async def update_position(
    session: AsyncSession, account_id: int, code: str, data: dict
) -> dict | None:
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
        setattr(position, key, value)
    await session.flush()
    return _rows_to_dicts([position])[0]


async def delete_position(
    session: AsyncSession, account_id: int, code: str
) -> bool:
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


# ── TradeOrder (extended) ──

async def create_trade_order(session: AsyncSession, data: dict) -> dict:
    order = TradeOrder(**data)
    session.add(order)
    await session.flush()
    return _rows_to_dicts([order])[0]


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


# ── V2 CRUD extensions ──

async def get_latest_popularity(
    session: AsyncSession, limit: int = 200
) -> list[dict]:
    """Get latest popularity snapshots."""
    from stock_service.db.models.v2_models import PopularitySnapshot, StockMaster
    result = await session.execute(
        select(PopularitySnapshot, StockMaster.stock_code)
        .join(StockMaster, PopularitySnapshot.stock_id == StockMaster.id)
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
        .join(StockMaster, PopularitySnapshot.stock_id == StockMaster.id)
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
        .join(StockMaster, StockAnalysisSnapshot.stock_id == StockMaster.id)
        .where(StockMaster.stock_code == code)
        .order_by(StockAnalysisSnapshot.analyzed_at.desc())
        .limit(1)
    )
    row = result.scalars().first()
    if not row:
        return None
    return _rows_to_dicts([row])[0]
```

Also add the missing imports at the top of quant_crud.py:

```python
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import func
```

- [ ] **Step 2: Commit**

```bash
git add src/stock_service/crud/quant_crud.py
git commit -m "feat(quant): add CRUD functions for positions, orders, daily upsert"
```

---

## Task 16: Integration & Final Wiring

**Files:**
- Modify: `src/stock_service/crud/__init__.py` (if needed)
- Verify: All imports work correctly

- [ ] **Step 1: Verify all imports**

```bash
cd /Users/fyq/Desktop/workshop/stock
python -c "from stock_service.quant.domain.strategy_interface import BaseStrategy, Signal, SignalType; print('OK')"
python -c "from stock_service.quant.domain.backtest_rules import BacktestConfig, BacktestRules; print('OK')"
python -c "from stock_service.quant.domain.risk_manager import RiskManager; print('OK')"
python -c "from stock_service.quant.domain.indicators import TechnicalIndicators; print('OK')"
python -c "from stock_service.quant.application.strategy_engine import StrategyEngine; print('OK')"
python -c "from stock_service.quant.application.backtest_engine import BacktestEngine; print('OK')"
python -c "from stock_service.quant.application.sim_trading_engine import SimTradingEngine; print('OK')"
python -c "from stock_service.quant.application.feedback_service import FeedbackService; print('OK')"
```

Expected: All print "OK"

- [ ] **Step 2: Run all tests**

```bash
python -m pytest tests/quant/ -v
```

Expected: ALL PASS

- [ ] **Step 3: Commit final integration**

```bash
git add -A
git commit -m "feat(quant): complete quant trading module integration"
```

---

## Summary

| Task | Component | Key Files |
|------|-----------|-----------|
| 1 | Schema & ORM | `schema_quant_v1.sql`, `quant_models.py` |
| 2 | CRUD Layer | `quant_crud.py` |
| 3 | Strategy Interface | `strategy_interface.py` |
| 4 | Technical Indicators | `indicators.py` |
| 5 | Backtest Rules | `backtest_rules.py` |
| 6 | Risk Manager | `risk_manager.py` |
| 7 | Strategy Engine + 2 strategies | `strategy_engine.py` |
| 8 | Tech + MultiFactor strategies | `strategy_engine.py` |
| 9 | Infrastructure | `data_provider.py`, `analysis_adapter.py` |
| 10 | Schemas | `schemas.py` |
| 11 | Backtest Engine | `backtest_engine.py` |
| 12 | Sim Trading Engine | `sim_trading_engine.py` |
| 13 | Feedback Service | `feedback_service.py` |
| 14 | API Routes | `routes/*.py`, `app.py` |
| 15 | CRUD Extensions | `quant_crud.py` |
| 16 | Integration | Final wiring & verification |
