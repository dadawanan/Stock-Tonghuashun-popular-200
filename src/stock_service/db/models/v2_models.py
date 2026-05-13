from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy import Index as _Index
from sqlalchemy.dialects.postgresql import ARRAY, BIGINT, JSONB, TEXT, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class PipelineRun(Base):
    __tablename__ = "pipeline_run"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    run_type: Mapped[str] = mapped_column(VARCHAR(32), nullable=False)
    source: Mapped[Optional[str]] = mapped_column(VARCHAR(32))
    trade_date: Mapped[Optional[date]] = mapped_column(Date)
    snapshot_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    stock_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    news_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    market_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    analysis_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(VARCHAR(16), nullable=False, default="running")
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())

    __table_args__ = (
        CheckConstraint(
            "run_type IN ('fetch', 'analyze', 'run_all', 'backfill', 'manual')",
            name="chk_pipeline_run_type",
        ),
        CheckConstraint(
            "status IN ('running', 'success', 'failed', 'partial')",
            name="chk_pipeline_status",
        ),
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())

    __table_args__ = (
        CheckConstraint("market IN ('SH', 'SZ', 'BJ')", name="chk_stock_market"),
        CheckConstraint("status IN ('active', 'delisted', 'suspended')", name="chk_stock_status"),
        _Index("idx_stock_master_market", "market", "stock_code"),
        _Index("idx_stock_master_name", "stock_name"),
    )


class PopularitySnapshot(Base):
    __tablename__ = "popularity_snapshot"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    run_id: Mapped[Optional[int]] = mapped_column(BIGINT)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    snapshot_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())

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
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSONB)
    content_hash: Mapped[Optional[str]] = mapped_column(VARCHAR(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())

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
    snapshot_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())

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
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())

    __table_args__ = (
        CheckConstraint("analyzer_type IN ('rule', 'llm', 'hybrid')", name="chk_news_analysis_type"),
        _Index(
            "uq_news_analysis_article_analyzer",
            "article_id", "analyzer_type", "model_name", "prompt_version",
            unique=True,
            postgresql_where=text("COALESCE(model_name, '') IS NOT NULL AND COALESCE(prompt_version, '') IS NOT NULL"),
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
    snapshot_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
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
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())

    __table_args__ = (
        _Index("uq_stock_analysis_snapshot_run_stock", "run_id", "stock_code", unique=True, postgresql_where=text("run_id IS NOT NULL")),
        _Index("idx_stock_analysis_snapshot_score", "integrated_score"),
        _Index("idx_stock_analysis_snapshot_stock_time", "stock_code", "analyzed_at"),
        _Index("idx_stock_analysis_snapshot_trade_date", "trade_date", "stock_code"),
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(VARCHAR(64), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(VARCHAR(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BIGINT, nullable=False)
    token_hash: Mapped[str] = mapped_column(VARCHAR(128), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())

    __table_args__ = (
        _Index("idx_refresh_tokens_user_id", "user_id"),
        _Index("idx_refresh_tokens_expires_at", "expires_at"),
    )


__all__ = [
    "PipelineRun",
    "StockMaster",
    "PopularitySnapshot",
    "NewsArticle",
    "MarketSnapshot",
    "NewsAnalysis",
    "StockAnalysisSnapshot",
    "User",
    "RefreshToken",
]
