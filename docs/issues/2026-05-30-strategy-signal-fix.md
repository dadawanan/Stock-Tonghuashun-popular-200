# 策略信号预览修复记录 (2026-05-30)

## 一、问题现象

调用 `POST /api/quant/strategies/signals/preview` 时：
- 技术面、量价、动量、均值回归、资金流、突破、多因子策略**全部无信号**
- 请求返回 `500 Internal Server Error`（无详细错误信息）

## 二、根因分析

### 2.1 500 错误 — `strategy_engine` 是模块不是实例

**文件**: `src/stock_service/quant/api/routes/strategies.py:151`

```python
# 错误代码
strategy = strategy_engine._strategies.get(strat_type)
```

`strategy_engine` 是 `stock_service.quant.application.strategy_engine` **模块对象**，不是 `StrategyEngine` 类的实例。模块没有 `_strategies` 属性，抛出 `AttributeError` → 500。

**修复**: 在 `strategy_engine.py` 末尾创建全局 `engine` 实例并注册所有 10 种策略，`strategies.py` 改用 `strategy_engine.engine._strategies`。

### 2.2 无信号 — 三重数据缺失

| 层级 | 问题 | 影响范围 |
|------|------|----------|
| `stock_daily` | 人气榜 200 只中仅 78 只有行情数据（`LIMIT 50` 限制） | 量价/动量/资金流/均值回归/突破/网格策略 |
| `stock_indicator` | 表从未被写入（有模型、有读函数、**无写函数**） | 技术面/多因子/均值回归/突破/网格策略 |
| `date.today()` | 代码用当天日期查数据，但数据库最新是 5/28 | 所有策略 |

### 2.3 500 错误无详细信息

默认 FastAPI 对未处理异常只返回 `Internal Server Error`，不暴露具体错误。

**修复**: 添加全局异常处理器，返回具体错误信息和 traceback。

---

## 三、补全数据反复失败的详细复盘（核心问题）

### 3.1 问题描述

点击前端"补全数据"按钮调用 `POST /api/quant/daily/backfill`，从腾讯行情拉取人气榜股票的 K 线数据写入 `stock_daily` 表，但每次都在 INSERT 时报错：

```
InvalidColumnReferenceError: there is no unique or exclusion constraint matching the ON CONFLICT specification
```

### 3.2 失败过程（4 轮）

| 轮次 | 尝试的方案 | 报错 | 当时的判断 |
|------|-----------|------|-----------|
| 1 | Scheduler 原始 SQL `ON CONFLICT (code, trade_date)` | `InvalidColumnReferenceError` | 远程库缺约束，改用 ORM |
| 2 | ORM `constraint="uq_stock_daily_code_date"` | `UndefinedObjectError` | 远程库约束名不存在，改用 `index_elements` |
| 3 | ORM `index_elements=["code", "trade_date"]` | `InvalidColumnReferenceError` | 以为是 SQLAlchemy 版本问题，改用原始 SQL |
| 4 | 原始 SQL + `psql` 直接查本地库 | **本地库约束不存在** | 终于找到真正原因 |

### 3.3 为什么前 3 轮都没修好

**核心原因：每次"本地测试"都在测错的目标。**

#### 第 1 轮：原始 SQL 报约束不存在

Scheduler 用原始 SQL `ON CONFLICT (code, trade_date)` 写入，报约束不存在。

**当时的做法**：判断是远程库（`101.35.255.200`）缺约束，改为 ORM 方式。

**问题**：没有确认 PM2 实际连的是哪个库。

#### 第 2 轮：ORM `constraint=` 参数报约束名不存在

改用 `pg_insert` + `constraint="uq_stock_daily_code_date"`，报 `UndefinedObjectError`。

**当时的做法**：判断约束名在远程库不存在，改为 `index_elements` 让 SQLAlchemy 自动匹配。

**问题**：仍然假设问题在远程库。

#### 第 3 轮：`index_elements` 也报约束不存在

改用 `index_elements=["code", "trade_date"]`，仍然报 `InvalidColumnReferenceError`。

**当时的做法**：加了 `/api/health` 端点确认 PM2 连的是 `localhost:5432/stock_db_test`，用 Python 脚本测试 `ON CONFLICT` 也通过了，认为是 SQLAlchemy ORM 兼容性问题，改用原始 SQL。

**问题**：Python 脚本的"测试通过"是假阳性。

#### 第 4 轮：`psql` 直接查本地库，发现约束根本不存在

直接用 `psql` 连接 `stock_db_test` 查询：

```sql
SELECT conname FROM pg_constraint 
WHERE conrelid = 'stock_daily'::regclass AND contype = 'u';
-- 结果: (0 rows)
```

**本地 `stock_db_test` 的 `stock_daily` 表从未建过唯一约束。**

### 3.4 为什么"本地测试通过"是假阳性

之前的"本地测试"代码：

```python
import asyncio
from stock_service.db.database import AsyncSessionFactory
from sqlalchemy import text

async def test():
    async with AsyncSessionFactory() as session:
        await session.execute(text("INSERT INTO stock_daily ... ON CONFLICT (code, trade_date) ..."))
        print("Works!")  # 确实打印了
```

**问题在于 `AsyncSessionFactory` 使用的引擎在模块加载时就已经创建好了。**

数据库连接链路：

```
database.py 模块加载
  → import settings → _load_dotenv() + _resolve_db_env()
  → DATABASE_CONFIG = {host: ..., port: ..., database: ...}
  → create_async_engine(DATABASE_URL)
  → AsyncSessionFactory = async_sessionmaker(bind=engine)
```

`_resolve_db_env()` 在 `settings.py` 模块加载时执行一次，根据 `APP_ENV` 决定连本地还是远程。

**关键问题**：在交互式 Python 中，`settings` 模块可能在设置 `APP_ENV=dev` 之前就被其他 import 链加载了。例如：

```python
import os
os.environ['APP_ENV'] = 'dev'  # 期望覆盖

# 但 stock_service.db.database 在导入时已经触发了 settings.py 的加载
# 如果此时 APP_ENV 还不是 dev，_resolve_db_env() 已经以 prod 执行完毕
from stock_service.db.database import AsyncSessionFactory
```

Python 的模块缓存机制意味着 `settings.py` 只执行一次。后续的 `os.environ['APP_ENV'] = 'dev'` 不会重新触发 `_resolve_db_env()`。

**结果**：测试脚本实际连的是远程库（`101.35.255.200`），远程库有约束所以通过了。但 PM2 进程连的是本地测试库（`localhost:5432/stock_db_test`），本地库没有约束所以失败。

### 3.5 最终修复

```sql
-- 本地测试库
ALTER TABLE stock_daily ADD CONSTRAINT uq_stock_daily_code_date UNIQUE (code, trade_date);
ALTER TABLE stock_indicator ADD CONSTRAINT uq_stock_indicator_code_date UNIQUE (code, trade_date);
```

同时将 ORM upsert 改为原始 SQL，避免 SQLAlchemy 版本兼容性问题。

---

## 四、所有改动文件

| 文件 | 改动 |
|------|------|
| `src/stock_service/quant/application/strategy_engine.py` | 末尾添加全局 `engine` 实例，注册 10 种策略 |
| `src/stock_service/quant/api/routes/strategies.py` | `strategy_engine.engine._strategies`；`date.today()` → `MAX(trade_date)` |
| `src/stock_service/crud/quant_crud.py` | 新增 `batch_upsert_stock_indicator()`；两个 upsert 改用原始 SQL + `created_at/updated_at` 默认值 |
| `src/stock_service/application/services/market_data_service.py` | 新增 `compute_and_store_indicators()`；`fetch_market_to_db`/`fetch_news_to_db` 改为顺序执行 + 连续失败保护 |
| `src/stock_service/scheduler.py` | `LIMIT 50` → `LIMIT 200`；集成指标计算；连续失败 3 次停止 |
| `src/stock_service/api/app.py` | 全局异常处理器，返回详细错误信息 |
| `src/stock_service/api/routes/analysis.py` | 新增 `/api/quant/indicators/compute` 和 `/api/quant/daily/backfill` 端点 |
| `src/stock_service/api/routes/health.py` | 返回实际数据库连接信息 |
| `src/stock_service/db/database.py` | 启动时打印数据库连接地址 |
| `web-ui/src/utils/api.ts` | 新增 `backfillDaily`、`computeIndicators` API |
| `web-ui/src/pages/quant/strategies.tsx` | 新增"补全数据"、"计算指标"按钮 |

---

## 五、教训

1. **验证假设要直接查目标库**：不要用 ORM session 间接测试，直接 `psql` 连目标库执行 SQL。
2. **PM2 环境和本地 shell 环境不同**：PM2 的 `cwd`、环境变量、Python 模块缓存都可能和本地不同。
3. **`_load_dotenv()` + `_resolve_db_env()` 的时序问题**：如果模块在 `APP_ENV` 设置前被 import，`_resolve_db_env()` 会以错误的 `APP_ENV` 执行，且不会重新执行。
4. **测试数据库的 schema 要和生产保持同步**：`stock_db_test` 缺少约束是因为建表脚本（`schema_quant_v1.sql`）没有在测试库上执行过。
5. **连续失败保护很重要**：没有这个机制时，200 只股票逐个失败会浪费大量时间。
