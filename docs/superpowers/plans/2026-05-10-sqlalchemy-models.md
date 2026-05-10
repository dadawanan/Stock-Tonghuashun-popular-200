# SQLAlchemy 模型实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) for syntax tracking.

**Goal:** 为全部 14 张数据库表创建 SQLAlchemy 2.0 ORM 模型类

**Architecture:** 在 `src/stock_service/db/models/` 下创建 `__init__.py`（Base + 统一导出）+ `v2_models.py`（7 张主表）+ `quant_models.py`（7 张量化表）。模型使用 `DeclarativeBase` + `AsyncAttrs`，列类型严格对标现有 SQL DDL。

**Tech Stack:** Python 3.12+, SQLAlchemy 2.0+ with asyncpg

---

### Task 1: 创建 Base 和 `__init__.py`

**Files:**
- Create: `src/stock_service/db/models/__init__.py`

- [ ] **Step 1: 创建 `__init__.py`**

```python
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase


class Base(AsyncAttrs, DeclarativeBase):
    pass


__all__ = ["Base"]
```

- [ ] **Step 2: Commit**

```bash
git add src/stock_service/db/models/__init__.py
git commit -m "feat(db): add SQLAlchemy Base class"
```

---

### Task 2: 创建 `v2_models.py`（7 张主表）

**Files:**
- Create: `src/stock_service/db/models/v2_models.py`
- Modify: `src/stock_service/db/models/__init__.py`（追加导出）

- [ ] **Step 1: 写入 PipelineRun**

```python
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    CheckConstraint, Date, DateTime, Index, Integer, Numeric, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, BIGINT, JSONB, TEXT, TIMESTAMPTZ, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class PipelineRun(Base):
    __tablename__ = "pipeline_run"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    run_type: Mapped[str] = mapped_column(VARCHAR(32), nullable=False)
    source: Mapped[Optional[str]] = mapped_column(VARCHAR(32))
    trade_date: Mapped[Optional[date]] = mapped_column(Date)
    snapshot_time: Mapped[Optional[datetime]] = mapped_column(TIMESTAMPTZ)
    stock_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    news_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    market_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    analysis_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(VARCHAR(16), nullable=False, default="running")
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMPTZ)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)

    __table_args__ = (
        CheckConstraint("run_type IN ('fetch', 'analyze', 'run_all', 'backfill', 'manual')", name="chk_pipeline_run_type"),
        CheckConstraint("status IN ('running', 'success', 'failed', 'partial')", name="chk_pipeline_status"),
        Index("idx_pipeline_run_trade_date", "trade_date"),
        Index("idx_pipeline_run_status_started", "status", "started_at"),
    )
```

- [ ] **Step 2: 写入 StockMaster**

```python
class StockMaster(Base):
    __tablename__ = "stock_master"

    stock_code: Mapped[str] = mapped_column(VARCHAR(10), primary_key=True)
    stock_name: Mapped[str] = mapped_column(VARCHAR(64), nullable=False)
    market: Mapped[str] = mapped_column(VARCHAR(8), nullable=False)
    market_code: Mapped[Optional[str]] = mapped_column(VARCHAR(16))
    code_digits: Mapped[Optional[str]] = mapped_column(VARCHAR(6))
    industry_name: Mapped[Optional[str]] = mapped_column(VARCHAR(128))
    concept_tags: Mapped[Optional[list[str]]] = mapped_column(ARRAY(TEXT))
    is_st: Mapped[bool] = mapped_column(nullable=False, default=False)
    listed_date: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[str] = mapped_column(VARCHAR(16), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)

    __table_args__ = (
        CheckConstraint("market IN ('SH', 'SZ', 'BJ')", name="chk_stock_market"),
        CheckConstraint("status IN ('active', 'delisted', 'suspended')", name="chk_stock_status"),
        Index("idx_stock_master_market", "market", "stock_code"),
        Index("idx_stock_master_name", "stock_name"),
    )
```

- [ ] **Step 3: 写入 PopularitySnapshot**

```python
class PopularitySnapshot(Base):
    __tablename__ = "popularity_snapshot"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    run_id: Mapped[Optional[int]] = mapped_column(BIGINT)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    snapshot_time: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    source: Mapped[str] = mapped_column(VARCHAR(32), nullable=False, default="ths_pywencai")
    stock_code: Mapped[str] = mapped_column(VARCHAR(10), nullable=False)
    stock_name: Mapped[str] = mapped_column(VARCHAR(64), nullable=False)
    popularity_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    popularity_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    latest_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4))
    latest_pct_change: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    is_new_entry: Mapped[bool] = mapped_column(nullable=False, default=False)
    previous_rank: Mapped[Optional[int]] = mapped_column(Integer)
    rank_change: Mapped[Optional[int]] = mapped_column(Integer)
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)

    __table_args__ = (
        UniqueConstraint("trade_date", "snapshot_time", "stock_code", "source", name="uq_popularity_snapshot"),
        Index("idx_popularity_snapshot_trade_rank", "trade_date", "popularity_rank"),
        Index("idx_popularity_snapshot_stock_time", "stock_code", "snapshot_time"),
        Index("idx_popularity_snapshot_new_entry", "trade_date", "is_new_entry"),
    )
```

- [ ] **Step 4: 写入 NewsArticle**

```python
class NewsArticle(Base):
    __tablename__ = "news_article"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    run_id: Mapped[Optional[int]] = mapped_column(BIGINT)
    stock_code: Mapped[str] = mapped_column(VARCHAR(10), nullable=False)
    stock_name: Mapped[Optional[str]] = mapped_column(VARCHAR(64))
    source: Mapped[Optional[str]] = mapped_column(VARCHAR(64))
    keyword: Mapped[Optional[str]] = mapped_column(VARCHAR(64))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    url: Mapped[Optional[str]] = mapped_column(Text)
    published_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMPTZ)
    fetched_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSONB)
    content_hash: Mapped[Optional[str]] = mapped_column(VARCHAR(64))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)

    __table_args__ = (
        Index("uq_news_article_stock_url", "stock_code", "url", postgresql_where=url is not None, unique=True),
        Index("uq_news_article_hash", "stock_code", "content_hash", postgresql_where=content_hash is not None, unique=True),
        Index("idx_news_article_stock_published", "stock_code", "published_at"),
        Index("idx_news_article_fetched_at", "fetched_at"),
    )
```

**Issues with conditional unique indexes:** SQLAlchemy `postgresql_where` on `Index` with `unique=True` requires the column objects used in the condition. But at class definition time, `url` and `content_hash` are `Mapped` attributes. We need to handle this differently. Let me use `__table_args__` with raw SQL expressions via `text()`.

修正为:

```python
from sqlalchemy import text

class NewsArticle(Base):
    __tablename__ = "news_article"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    run_id: Mapped[Optional[int]] = mapped_column(BIGINT)
    stock_code: Mapped[str] = mapped_column(VARCHAR(10), nullable=False)
    stock_name: Mapped[Optional[str]] = mapped_column(VARCHAR(64))
    source: Mapped[Optional[str]] = mapped_column(VARCHAR(64))
    keyword: Mapped[Optional[str]] = mapped_column(VARCHAR(64))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    url: Mapped[Optional[str]] = mapped_column(Text)
    published_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMPTZ)
    fetched_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSONB)
    content_hash: Mapped[Optional[str]] = mapped_column(VARCHAR(64))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)

    __table_args__ = (
        Index("uq_news_article_stock_url", "stock_code", "url", unique=True, postgresql_where=text("url IS NOT NULL")),
        Index("uq_news_article_hash", "stock_code", "content_hash", unique=True, postgresql_where=text("content_hash IS NOT NULL")),
        Index("idx_news_article_stock_published", "stock_code", "published_at"),
        Index("idx_news_article_fetched_at", "fetched_at"),
    )
```

- [ ] **Step 5: 写入 MarketSnapshot**

```python
class MarketSnapshot(Base):
    __tablename__ = "market_snapshot"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    run_id: Mapped[Optional[int]] = mapped_column(BIGINT)
    stock_code: Mapped[str] = mapped_column(VARCHAR(10), nullable=False)
    stock_name: Mapped[Optional[str]] = mapped_column(VARCHAR(64))
    trade_date: Mapped[Optional[date]] = mapped_column(Date)
    snapshot_time: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    source: Mapped[str] = mapped_column(VARCHAR(32), nullable=False, default="eastmoney")
    latest_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4))
    pct_change: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    change_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4))
    open_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4))
    high_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4))
    low_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4))
    prev_close: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4))
    volume: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))
    volume_ratio: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    turnover_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    amplitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    main_net_inflow: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))
    main_net_inflow_ratio: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    fund_flow_date: Mapped[Optional[date]] = mapped_column(Date)
    benchmark_code: Mapped[Optional[str]] = mapped_column(VARCHAR(16))
    benchmark_name: Mapped[Optional[str]] = mapped_column(VARCHAR(32))
    benchmark_pct_change: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    relative_strength_vs_index: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    source_latest_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4))
    source_pct_change: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)

    __table_args__ = (
        Index("idx_market_snapshot_stock_time", "stock_code", "snapshot_time"),
        Index("idx_market_snapshot_trade_date", "trade_date", "stock_code"),
        Index("idx_market_snapshot_fund_flow_date", "fund_flow_date", "stock_code"),
    )
```

- [ ] **Step 6: 写入 NewsAnalysis**

```python
class NewsAnalysis(Base):
    __tablename__ = "news_analysis"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    run_id: Mapped[Optional[int]] = mapped_column(BIGINT)
    article_id: Mapped[int] = mapped_column(BIGINT, nullable=False)
    stock_code: Mapped[str] = mapped_column(VARCHAR(10), nullable=False)
    analyzer_type: Mapped[str] = mapped_column(VARCHAR(16), nullable=False, default="rule")
    model_name: Mapped[Optional[str]] = mapped_column(VARCHAR(64))
    model_version: Mapped[Optional[str]] = mapped_column(VARCHAR(64))
    prompt_version: Mapped[Optional[str]] = mapped_column(VARCHAR(64))
    event_type: Mapped[Optional[str]] = mapped_column(VARCHAR(64))
    event_label: Mapped[str] = mapped_column(VARCHAR(16), nullable=False, default="中性")
    event_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    sentiment_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    sentiment_strength: Mapped[Optional[str]] = mapped_column(VARCHAR(16))
    duration_tag: Mapped[Optional[str]] = mapped_column(VARCHAR(16))
    fact_support: Mapped[Optional[str]] = mapped_column(VARCHAR(16))
    impact_scope: Mapped[Optional[str]] = mapped_column(VARCHAR(32))
    impact_direction: Mapped[Optional[str]] = mapped_column(VARCHAR(16))
    impact_path: Mapped[Optional[str]] = mapped_column(Text)
    bullish_logic: Mapped[Optional[str]] = mapped_column(Text)
    bearish_logic: Mapped[Optional[str]] = mapped_column(Text)
    extracted_entities: Mapped[Optional[dict]] = mapped_column(JSONB)
    analysis_json: Mapped[Optional[dict]] = mapped_column(JSONB)
    analyzed_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)

    __table_args__ = (
        CheckConstraint("analyzer_type IN ('rule', 'llm', 'hybrid')", name="chk_news_analysis_type"),
        Index(
            "uq_news_analysis_article_analyzer",
            "article_id", "analyzer_type",
            unique=True,
            postgresql_where=text("COALESCE(model_name, '') IS NOT NULL"),
        ),
        Index("idx_news_analysis_stock_time", "stock_code", "analyzed_at"),
        Index("idx_news_analysis_event_type", "event_type", "event_label"),
    )
```

Wait, the unique index on `news_analysis` uses `COALESCE(model_name, '')` and `COALESCE(prompt_version, '')`. Let me fix this:

```python
    __table_args__ = (
        CheckConstraint("analyzer_type IN ('rule', 'llm', 'hybrid')", name="chk_news_analysis_type"),
        Index(
            "uq_news_analysis_article_analyzer",
            "article_id", "analyzer_type", "model_name", "prompt_version",
            unique=True,
            postgresql_where=text("COALESCE(model_name, '') IS NOT NULL AND COALESCE(prompt_version, '') IS NOT NULL"),
        ),
        Index("idx_news_analysis_stock_time", "stock_code", "analyzed_at"),
        Index("idx_news_analysis_event_type", "event_type", "event_label"),
    )
```

- [ ] **Step 7: 写入 StockAnalysisSnapshot**

```python
class StockAnalysisSnapshot(Base):
    __tablename__ = "stock_analysis_snapshot"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    run_id: Mapped[Optional[int]] = mapped_column(BIGINT)
    stock_code: Mapped[str] = mapped_column(VARCHAR(10), nullable=False)
    stock_name: Mapped[Optional[str]] = mapped_column(VARCHAR(64))
    trade_date: Mapped[Optional[date]] = mapped_column(Date)
    snapshot_time: Mapped[Optional[datetime]] = mapped_column(TIMESTAMPTZ)
    event_types: Mapped[Optional[str]] = mapped_column(Text)
    text_event_label: Mapped[str] = mapped_column(VARCHAR(16), nullable=False, default="中性")
    text_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    sentiment_strength: Mapped[Optional[str]] = mapped_column(VARCHAR(16))
    duration_tag: Mapped[Optional[str]] = mapped_column(VARCHAR(16))
    fact_support: Mapped[Optional[str]] = mapped_column(VARCHAR(16))
    bullish_logic: Mapped[Optional[str]] = mapped_column(Text)
    bearish_logic: Mapped[Optional[str]] = mapped_column(Text)
    news_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    price_volume_signal: Mapped[str] = mapped_column(VARCHAR(32), nullable=False, default="数据不足")
    fund_flow_signal: Mapped[str] = mapped_column(VARCHAR(32), nullable=False, default="资金观望")
    behavior_label: Mapped[str] = mapped_column(VARCHAR(32), nullable=False, default="中性")
    market_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    integrated_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    decision: Mapped[Optional[str]] = mapped_column(Text)
    reasoning_json: Mapped[Optional[dict]] = mapped_column(JSONB)
    analyzed_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)

    __table_args__ = (
        Index("uq_stock_analysis_snapshot_run_stock", "run_id", "stock_code", unique=True, postgresql_where=text("run_id IS NOT NULL")),
        Index("idx_stock_analysis_snapshot_score", "integrated_score"),
        Index("idx_stock_analysis_snapshot_stock_time", "stock_code", "analyzed_at"),
        Index("idx_stock_analysis_snapshot_trade_date", "trade_date", "stock_code"),
    )
```

- [ ] **Step 8: 组装 v2_models.py 完整文件**

合并以上所有 model class，确保 import 完整。完整文件内容如下：

```python
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    Date,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, BIGINT, JSONB, TEXT, TIMESTAMPTZ, VARCHAR
from sqlalchemy import Index as _Index
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class PipelineRun(Base):
    __tablename__ = "pipeline_run"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    run_type: Mapped[str] = mapped_column(VARCHAR(32), nullable=False)
    source: Mapped[Optional[str]] = mapped_column(VARCHAR(32))
    trade_date: Mapped[Optional[date]] = mapped_column(Date)
    snapshot_time: Mapped[Optional[datetime]] = mapped_column(TIMESTAMPTZ)
    stock_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    news_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    market_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    analysis_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(VARCHAR(16), nullable=False, default="running")
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMPTZ)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)

    __table_args__ = (
        CheckConstraint("run_type IN ('fetch', 'analyze', 'run_all', 'backfill', 'manual')", name="chk_pipeline_run_type"),
        CheckConstraint("status IN ('running', 'success', 'failed', 'partial')", name="chk_pipeline_status"),
        _Index("idx_pipeline_run_trade_date", "trade_date"),
        _Index("idx_pipeline_run_status_started", "status", "started_at"),
    )


class StockMaster(Base):
    __tablename__ = "stock_master"

    stock_code: Mapped[str] = mapped_column(VARCHAR(10), primary_key=True)
    stock_name: Mapped[str] = mapped_column(VARCHAR(64), nullable=False)
    market: Mapped[str] = mapped_column(VARCHAR(8), nullable=False)
    market_code: Mapped[Optional[str]] = mapped_column(VARCHAR(16))
    code_digits: Mapped[Optional[str]] = mapped_column(VARCHAR(6))
    industry_name: Mapped[Optional[str]] = mapped_column(VARCHAR(128))
    concept_tags: Mapped[Optional[list[str]]] = mapped_column(ARRAY(TEXT))
    is_st: Mapped[bool] = mapped_column(nullable=False, default=False)
    listed_date: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[str] = mapped_column(VARCHAR(16), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)

    __table_args__ = (
        CheckConstraint("market IN ('SH', 'SZ', 'BJ')", name="chk_stock_market"),
        CheckConstraint("status IN ('active', 'delisted', 'suspended')", name="chk_stock_status"),
        _Index("idx_stock_master_market", "market", "stock_code"),
        _Index("idx_stock_master_name", "stock_name"),
    )

    def __repr__(self) -> str:
        return f"<StockMaster {self.stock_code} {self.stock_name}>"


class PopularitySnapshot(Base):
    __tablename__ = "popularity_snapshot"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    run_id: Mapped[Optional[int]] = mapped_column(BIGINT)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    snapshot_time: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    source: Mapped[str] = mapped_column(VARCHAR(32), nullable=False, default="ths_pywencai")
    stock_code: Mapped[str] = mapped_column(VARCHAR(10), nullable=False)
    stock_name: Mapped[str] = mapped_column(VARCHAR(64), nullable=False)
    popularity_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    popularity_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    latest_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4))
    latest_pct_change: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    is_new_entry: Mapped[bool] = mapped_column(nullable=False, default=False)
    previous_rank: Mapped[Optional[int]] = mapped_column(Integer)
    rank_change: Mapped[Optional[int]] = mapped_column(Integer)
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)

    __table_args__ = (
        UniqueConstraint("trade_date", "snapshot_time", "stock_code", "source", name="uq_popularity_snapshot"),
        _Index("idx_popularity_snapshot_trade_rank", "trade_date", "popularity_rank"),
        _Index("idx_popularity_snapshot_stock_time", "stock_code", "snapshot_time"),
        _Index("idx_popularity_snapshot_new_entry", "trade_date", "is_new_entry"),
    )


class NewsArticle(Base):
    __tablename__ = "news_article"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    run_id: Mapped[Optional[int]] = mapped_column(BIGINT)
    stock_code: Mapped[str] = mapped_column(VARCHAR(10), nullable=False)
    stock_name: Mapped[Optional[str]] = mapped_column(VARCHAR(64))
    source: Mapped[Optional[str]] = mapped_column(VARCHAR(64))
    keyword: Mapped[Optional[str]] = mapped_column(VARCHAR(64))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    url: Mapped[Optional[str]] = mapped_column(Text)
    published_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMPTZ)
    fetched_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSONB)
    content_hash: Mapped[Optional[str]] = mapped_column(VARCHAR(64))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)

    __table_args__ = (
        _Index("uq_news_article_stock_url", "stock_code", "url", unique=True, postgresql_where=text("url IS NOT NULL")),
        _Index("uq_news_article_hash", "stock_code", "content_hash", unique=True, postgresql_where=text("content_hash IS NOT NULL")),
        _Index("idx_news_article_stock_published", "stock_code", "published_at"),
        _Index("idx_news_article_fetched_at", "fetched_at"),
    )


class MarketSnapshot(Base):
    __tablename__ = "market_snapshot"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    run_id: Mapped[Optional[int]] = mapped_column(BIGINT)
    stock_code: Mapped[str] = mapped_column(VARCHAR(10), nullable=False)
    stock_name: Mapped[Optional[str]] = mapped_column(VARCHAR(64))
    trade_date: Mapped[Optional[date]] = mapped_column(Date)
    snapshot_time: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    source: Mapped[str] = mapped_column(VARCHAR(32), nullable=False, default="eastmoney")
    latest_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4))
    pct_change: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    change_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4))
    open_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4))
    high_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4))
    low_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4))
    prev_close: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4))
    volume: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))
    volume_ratio: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    turnover_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    amplitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    main_net_inflow: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))
    main_net_inflow_ratio: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    fund_flow_date: Mapped[Optional[date]] = mapped_column(Date)
    benchmark_code: Mapped[Optional[str]] = mapped_column(VARCHAR(16))
    benchmark_name: Mapped[Optional[str]] = mapped_column(VARCHAR(32))
    benchmark_pct_change: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    relative_strength_vs_index: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    source_latest_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4))
    source_pct_change: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)

    __table_args__ = (
        _Index("idx_market_snapshot_stock_time", "stock_code", "snapshot_time"),
        _Index("idx_market_snapshot_trade_date", "trade_date", "stock_code"),
        _Index("idx_market_snapshot_fund_flow_date", "fund_flow_date", "stock_code"),
    )


class NewsAnalysis(Base):
    __tablename__ = "news_analysis"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    run_id: Mapped[Optional[int]] = mapped_column(BIGINT)
    article_id: Mapped[int] = mapped_column(BIGINT, nullable=False)
    stock_code: Mapped[str] = mapped_column(VARCHAR(10), nullable=False)
    analyzer_type: Mapped[str] = mapped_column(VARCHAR(16), nullable=False, default="rule")
    model_name: Mapped[Optional[str]] = mapped_column(VARCHAR(64))
    model_version: Mapped[Optional[str]] = mapped_column(VARCHAR(64))
    prompt_version: Mapped[Optional[str]] = mapped_column(VARCHAR(64))
    event_type: Mapped[Optional[str]] = mapped_column(VARCHAR(64))
    event_label: Mapped[str] = mapped_column(VARCHAR(16), nullable=False, default="中性")
    event_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    sentiment_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    sentiment_strength: Mapped[Optional[str]] = mapped_column(VARCHAR(16))
    duration_tag: Mapped[Optional[str]] = mapped_column(VARCHAR(16))
    fact_support: Mapped[Optional[str]] = mapped_column(VARCHAR(16))
    impact_scope: Mapped[Optional[str]] = mapped_column(VARCHAR(32))
    impact_direction: Mapped[Optional[str]] = mapped_column(VARCHAR(16))
    impact_path: Mapped[Optional[str]] = mapped_column(Text)
    bullish_logic: Mapped[Optional[str]] = mapped_column(Text)
    bearish_logic: Mapped[Optional[str]] = mapped_column(Text)
    extracted_entities: Mapped[Optional[dict]] = mapped_column(JSONB)
    analysis_json: Mapped[Optional[dict]] = mapped_column(JSONB)
    analyzed_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)

    __table_args__ = (
        CheckConstraint("analyzer_type IN ('rule', 'llm', 'hybrid')", name="chk_news_analysis_type"),
        _Index(
            "uq_news_analysis_article_analyzer",
            "article_id", "analyzer_type",
            unique=True,
            postgresql_where=text("COALESCE(model_name, '') IS NOT NULL"),
        ),
        _Index("idx_news_analysis_stock_time", "stock_code", "analyzed_at"),
        _Index("idx_news_analysis_event_type", "event_type", "event_label"),
    )


class StockAnalysisSnapshot(Base):
    __tablename__ = "stock_analysis_snapshot"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    run_id: Mapped[Optional[int]] = mapped_column(BIGINT)
    stock_code: Mapped[str] = mapped_column(VARCHAR(10), nullable=False)
    stock_name: Mapped[Optional[str]] = mapped_column(VARCHAR(64))
    trade_date: Mapped[Optional[date]] = mapped_column(Date)
    snapshot_time: Mapped[Optional[datetime]] = mapped_column(TIMESTAMPTZ)
    event_types: Mapped[Optional[str]] = mapped_column(Text)
    text_event_label: Mapped[str] = mapped_column(VARCHAR(16), nullable=False, default="中性")
    text_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    sentiment_strength: Mapped[Optional[str]] = mapped_column(VARCHAR(16))
    duration_tag: Mapped[Optional[str]] = mapped_column(VARCHAR(16))
    fact_support: Mapped[Optional[str]] = mapped_column(VARCHAR(16))
    bullish_logic: Mapped[Optional[str]] = mapped_column(Text)
    bearish_logic: Mapped[Optional[str]] = mapped_column(Text)
    news_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    price_volume_signal: Mapped[str] = mapped_column(VARCHAR(32), nullable=False, default="数据不足")
    fund_flow_signal: Mapped[str] = mapped_column(VARCHAR(32), nullable=False, default="资金观望")
    behavior_label: Mapped[str] = mapped_column(VARCHAR(32), nullable=False, default="中性")
    market_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    integrated_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    decision: Mapped[Optional[str]] = mapped_column(Text)
    reasoning_json: Mapped[Optional[dict]] = mapped_column(JSONB)
    analyzed_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)

    __table_args__ = (
        _Index("uq_stock_analysis_snapshot_run_stock", "run_id", "stock_code", unique=True, postgresql_where=text("run_id IS NOT NULL")),
        _Index("idx_stock_analysis_snapshot_score", "integrated_score"),
        _Index("idx_stock_analysis_snapshot_stock_time", "stock_code", "analyzed_at"),
        _Index("idx_stock_analysis_snapshot_trade_date", "trade_date", "stock_code"),
    )


__all__ = [
    "PipelineRun",
    "StockMaster",
    "PopularitySnapshot",
    "NewsArticle",
    "MarketSnapshot",
    "NewsAnalysis",
    "StockAnalysisSnapshot",
]
```

- [ ] **Step 9: 更新 `__init__.py` 导入 v2_models**

```python
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase


class Base(AsyncAttrs, DeclarativeBase):
    pass
```

改为：

```python
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase


class Base(AsyncAttrs, DeclarativeBase):
    pass


# 触发 model 注册
from . import v2_models  # noqa: F401, E402


__all__ = ["Base", "v2_models"]
```

- [ ] **Step 10: 验证语法正确**

```bash
cd /Users/a/jkm/llm/Stock-Tonghuashun-popular-200 && python -c "from src.stock_service.db.models import Base; print(Base.metadata.tables.keys())"
```

Expected: 包含 `pipeline_run`, `stock_master`, `popularity_snapshot`, `news_article`, `market_snapshot`, `news_analysis`, `stock_analysis_snapshot`

- [ ] **Step 11: Commit**

```bash
git add src/stock_service/db/models/__init__.py src/stock_service/db/models/v2_models.py
git commit -m "feat(db): add SQLAlchemy models for schema_v2 tables"
```

---

### Task 3: 创建 `quant_models.py`（7 张量化表）

**Files:**
- Create: `src/stock_service/db/models/quant_models.py`
- Modify: `src/stock_service/db/models/__init__.py`（追加导出）

- [ ] **Step 1: 写入 quant_models.py 完整文件**

```python
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Date,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import BIGINT, TIMESTAMPTZ, VARCHAR
from sqlalchemy import Index as _Index
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class StockBasic(Base):
    __tablename__ = "stock_basic"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(VARCHAR(16), nullable=False, unique=True)
    name: Mapped[Optional[str]] = mapped_column(VARCHAR(64))
    market: Mapped[Optional[str]] = mapped_column(VARCHAR(16))
    industry: Mapped[Optional[str]] = mapped_column(VARCHAR(64))
    list_date: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[Optional[str]] = mapped_column(VARCHAR(16))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)

    __table_args__ = (
        _Index("idx_stock_basic_market", "market"),
    )


class StockDaily(Base):
    __tablename__ = "stock_daily"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(VARCHAR(16), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    high: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    low: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    close: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    volume: Mapped[Optional[int]] = mapped_column(BIGINT)
    amount: Mapped[Optional[int]] = mapped_column(BIGINT)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)

    __table_args__ = (
        UniqueConstraint("code", "trade_date", name="uq_stock_daily_code_date"),
        _Index("idx_stock_daily_code_date", "code", "trade_date"),
    )


class StockIndicator(Base):
    __tablename__ = "stock_indicator"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(VARCHAR(16), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    ma5: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    ma20: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    rsi: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    macd: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)

    __table_args__ = (
        UniqueConstraint("code", "trade_date", name="uq_stock_indicator_code_date"),
        _Index("idx_stock_indicator_code_date", "code", "trade_date"),
    )


class StrategyPick(Base):
    __tablename__ = "strategy_pick"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    strategy_id: Mapped[int] = mapped_column(BIGINT, nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    code: Mapped[str] = mapped_column(VARCHAR(16), nullable=False)
    score: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    reason: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)

    __table_args__ = (
        _Index("idx_strategy_pick_strategy_date", "strategy_id", "trade_date"),
        _Index("idx_strategy_pick_code", "code"),
    )


class BacktestResult(Base):
    __tablename__ = "backtest_result"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    strategy_id: Mapped[int] = mapped_column(BIGINT, nullable=False)
    start_date: Mapped[Optional[date]] = mapped_column(Date)
    end_date: Mapped[Optional[date]] = mapped_column(Date)
    annual_return: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    max_drawdown: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    sharpe: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    win_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)

    __table_args__ = (
        _Index("idx_backtest_result_strategy", "strategy_id", "created_at"),
    )


class TradeOrder(Base):
    __tablename__ = "trade_order"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(BIGINT, nullable=False)
    code: Mapped[str] = mapped_column(VARCHAR(16), nullable=False)
    side: Mapped[str] = mapped_column(VARCHAR(8), nullable=False)
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    quantity: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[Optional[str]] = mapped_column(VARCHAR(16))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)

    __table_args__ = (
        _Index("idx_trade_order_account_time", "account_id", "created_at"),
        _Index("idx_trade_order_code", "code"),
    )


class PositionAccount(Base):
    __tablename__ = "position_account"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(BIGINT, nullable=False)
    code: Mapped[str] = mapped_column(VARCHAR(16), nullable=False)
    quantity: Mapped[Optional[int]] = mapped_column(Integer)
    avg_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)

    __table_args__ = (
        UniqueConstraint("account_id", "code", name="uq_position_account"),
        _Index("idx_position_account_id", "account_id"),
    )


__all__ = [
    "StockBasic",
    "StockDaily",
    "StockIndicator",
    "StrategyPick",
    "BacktestResult",
    "TradeOrder",
    "PositionAccount",
]
```

- [ ] **Step 2: 更新 `__init__.py` 导入 quant_models**

```python
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase


class Base(AsyncAttrs, DeclarativeBase):
    pass


# 触发 model 注册
from . import v2_models  # noqa: F401, E402
from . import quant_models  # noqa: F401, E402


__all__ = ["Base", "v2_models", "quant_models"]
```

- [ ] **Step 3: 验证全部 14 张表已注册**

```bash
cd /Users/a/jkm/llm/Stock-Tonghuashun-popular-200 && python -c "
from src.stock_service.db.models import Base
for name, table in sorted(Base.metadata.tables.items()):
    print(f'  {name}: {len(table.columns)} columns')
print(f'Total: {len(Base.metadata.tables)} tables')
"
```

Expected: 输出 14 张表，每张表列数正确。

- [ ] **Step 4: Commit**

```bash
git add src/stock_service/db/models/quant_models.py src/stock_service/db/models/__init__.py
git commit -m "feat(db): add SQLAlchemy models for quant schema tables"
```
