# SQLAlchemy 数据对象设计

## 目标

为项目全部 14 张数据库表创建 SQLAlchemy 2.0 ORM 模型类，用于后续逐步替换现有 asyncpg 原生 SQL 方案。

## 目录结构

```
src/stock_service/db/models/
├── __init__.py        # Base + 统一导出
├── v2_models.py       # schema_v2.sql 7 张表
└── quant_models.py    # schema_quant_v1.sql 7 张表
```

## 约束

- 使用 SQLAlchemy 2.0 `DeclarativeBase` + `AsyncAttrs` 混入
- 列类型严格对标现有 SQL DDL（`TIMESTAMPTZ` → `DateTime(timezone=True)`，`JSONB` → `postgresql.JSONB`，`TEXT[]` → `ARRAY(String)`，`NUMERIC(p,s)` → `Numeric(p,s)`）
- 模型类 `PascalCase`，`__tablename__` 直接映射表名
- `__table_args__` 包含现有索引和约束
- 不强加 `relationship()`（后续按需添加）
- 不改变 `VARCHAR(1)`/`BOOLEAN` 规则 — 模型匹配现有表结构
- 时间字段显示声明 `timezone=True`

## 模型清单

### v2_models.py

| 表名 | 模型类 | 主键 |
|------|--------|------|
| `pipeline_run` | `PipelineRun` | `id` (BIGSERIAL) |
| `stock_master` | `StockMaster` | `stock_code` (VARCHAR(10)) |
| `popularity_snapshot` | `PopularitySnapshot` | `id` (BIGSERIAL) |
| `news_article` | `NewsArticle` | `id` (BIGSERIAL) |
| `market_snapshot` | `MarketSnapshot` | `id` (BIGSERIAL) |
| `news_analysis` | `NewsAnalysis` | `id` (BIGSERIAL) |
| `stock_analysis_snapshot` | `StockAnalysisSnapshot` | `id` (BIGSERIAL) |

### quant_models.py

| 表名 | 模型类 | 主键 |
|------|--------|------|
| `stock_basic` | `StockBasic` | `id` (BIGSERIAL) |
| `stock_daily` | `StockDaily` | `id` (BIGSERIAL) |
| `stock_indicator` | `StockIndicator` | `id` (BIGSERIAL) |
| `strategy_pick` | `StrategyPick` | `id` (BIGSERIAL) |
| `backtest_result` | `BacktestResult` | `id` (BIGSERIAL) |
| `trade_order` | `TradeOrder` | `id` (BIGSERIAL) |
| `position_account` | `PositionAccount` | `id` (BIGSERIAL) |
