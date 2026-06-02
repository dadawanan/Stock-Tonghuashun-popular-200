# 故障排查记录：T+1 解锁失效 & 日线数据停更

**日期**: 2026-06-02
**报告人**: dadawanan
**影响范围**: 模拟交易系统全部策略账户
**严重程度**: 高 — 导致策略账户无法正常交易

---

## 1. 故障现象

用户报告测试账户（dadawanan）的 002456.SZ 持仓状态异常：
- 昨天（6月1日）买入的股票，今天（6月2日）应可卖出，但显示不可卖
- 账户 2-5 配置了策略，但今天 9:25 未执行任何交易

---

## 2. 排查过程

### 2.1 查询 002456.SZ 持仓状态

通过远程数据库（`101.35.255.200:55443/stock_db`）直接查询：

```sql
-- 持仓状态
SELECT code, quantity, available_quantity, avg_price, updated_at
FROM position_account WHERE code = '002456.SZ';
-- 结果: quantity=19800, available_quantity=0, updated_at=2026-06-01 14:33

-- 交易记录
SELECT side, price, quantity, created_at
FROM trade_order WHERE code = '002456.SZ' ORDER BY created_at DESC LIMIT 5;
-- 结果: buy 9.68 19800 @ 2026-06-01 14:33

-- 每日结算快照
SELECT * FROM position_daily_snapshot WHERE code = '002456.SZ';
-- 结果: 空
```

**发现**: 002456.SZ 于 6月1日 14:33 买入，`available_quantity=0`，但 6月1日的结算快照不存在。

### 2.2 定位每日结算缺失

```sql
-- 查看最近的结算日期
SELECT trade_date, COUNT(*) FROM position_daily_snapshot
GROUP BY trade_date ORDER BY trade_date DESC LIMIT 10;
-- 结果: 最新为 2026-05-30，之后无数据
```

**确认**: `daily_settlement()` 在 6月1日 15:05 未执行。调度器是内存长驻进程，若进程当时未运行，结算任务丢失且无补偿机制。

### 2.3 立即修复 — 手动解锁被锁持仓

```sql
UPDATE position_account
SET available_quantity = quantity
WHERE available_quantity = 0
  AND updated_at >= '2026-06-01'
  AND updated_at < '2026-06-02';
-- 影响 5 行: 002456.SZ, 603598.SH, 300792.SZ, 300170.SZ, 601918.SH
```

### 2.4 排查账户 2-5 未交易

查询账户配置：

| 账户 | 策略 | 策略类型 |
|------|------|---------|
| 1 | 人气榜策略 | popularity |
| 2 | 多因子策略 | multi_factor |
| 3 | 技术面策略 | technical |
| 4 | 量价策略 | volume_price |
| 5 | 均值回归策略 | mean_reversion |
| 6 | 情绪驱动策略 | sentiment |

查询今日交易：

```sql
-- 今日交易记录
SELECT account_id, code, side, created_at FROM trade_order
WHERE created_at >= '2026-06-02';
-- 结果: 账户1和6有交易，账户2-5无任何交易
```

### 2.5 分析策略数据依赖

逐一阅读策略实现代码（`strategy_engine.py`）：

| 策略 | 依赖的数据 | 数据来源表 |
|------|-----------|-----------|
| **popularity** | 人气排名 | `popularity_snapshot` ✅ |
| **sentiment** | 情绪分析分数 | `stock_analysis_snapshot` ✅ |
| **technical** | MA/RSI/MACD 指标 | `stock_indicator` ❌ |
| **multi_factor** | 人气 + 情绪 + **指标** | `stock_indicator` ❌ |
| **volume_price** | 量价日线数据 | `stock_daily` ❌ |
| **mean_reversion** | MA 均线 | `stock_daily` ❌ |

```sql
-- 检查数据表最新日期
SELECT MAX(trade_date) FROM stock_daily;     -- 2026-05-30
SELECT MAX(trate_date) FROM stock_indicator; -- 2026-05-30
```

**确认**: `stock_daily` 和 `stock_indicator` 从 5月30日起停更，导致依赖市场数据的策略无法生成信号。

### 2.6 追踪日线数据更新链路

`run_pipeline()` 的执行流程：

```
1. run_popularity_pipeline()       → 获取人气榜 200 只股票
2. run_fetch_pipeline_for_rows()   → 抓取新闻/行情
3. run_and_store()                 → 生成分析结果
4. update_popularity_daily_data()  → ❌ 更新日线数据（失败点）
5. compute_and_store_indicators()  → ❌ 依赖步骤4
6. auto_trade_for_accounts()       → ❌ 依赖步骤4/5
```

### 2.7 逐步测试各组件

**测试 `fetch_kline_tx`**（腾讯行情 API）:

```python
df = fetch_kline_tx('002579.SZ', '20250601', '20260602')
# 结果: 242 行数据，API 正常工作
```

**测试 `batch_upsert_stock_daily`**（数据库写入）:

```python
count = await quant_crud.batch_upsert_stock_daily(session, records)
await session.commit()
# 结果: 写入成功
```

**测试 `compute_and_store_indicators`**（指标计算）:

```python
count = await compute_and_store_indicators(session)
# 结果: 计算了 373 只股票的指标
```

所有组件单独测试均正常。**问题出在调用链路上。**

### 2.8 定位 `get_missing_popularity_codes` 的 SQL 错误

模拟执行 `update_popularity_daily_data()` 时，`get_missing_popularity_codes()` 抛出异常：

```
sqlalchemy.exc.ProgrammingError:
  operator does not exist: timestamp with time zone - integer
HINT: No operator matches the given name and argument types.
```

对应的 SQL：

```sql
SELECT DISTINCT stock_daily.code
FROM stock_daily
WHERE stock_daily.trade_date >= now() - $1::INTEGER  -- ❌ 错误！
```

**PostgreSQL 不支持 `timestamp with time zone - integer` 运算。**

---

## 3. 根因

`quant_crud.py:856`：

```python
# ❌ 错误写法
StockDaily.trade_date >= func.now() - 3
# func.now() 返回 timestamp with time zone
# PostgreSQL 不支持 timestamp - integer，抛出 ProgrammingError
```

异常被 `update_popularity_daily_data()` 的外层 `try/except` 捕获，静默记录日志后返回。函数从未成功执行过，`stock_daily` 自 5月30日起停止更新。

### 影响链路

```
get_missing_popularity_codes() 抛异常
  → update_popularity_daily_data() 静默失败
    → stock_daily 停在 2026-05-30
      → compute_and_store_indicators() 无数据可算
        → stock_indicator 停在 2026-05-30
          → technical / multi_factor / volume_price / mean_reversion 策略无法生成信号
            → 账户 2-5 永远不会交易
```

同时，每日结算（daily settlement）也因调度器进程不在运行而未执行，导致 T+1 锁定不释放。

---

## 4. 修复措施

### 4.1 立即修复（数据层）

手动解锁 6月1日买入的 5 个被锁持仓：

```sql
UPDATE position_account
SET available_quantity = quantity
WHERE available_quantity = 0
  AND updated_at >= '2026-06-01'
  AND updated_at < '2026-06-02';
```

### 4.2 根因修复（代码层）

**修复 `get_missing_popularity_codes` 的 SQL 类型错误**：

```diff
# quant_crud.py:856
- .where(StockDaily.trade_date >= func.now() - 3)
+ .where(StockDaily.trade_date >= func.current_date() - 3)
```

- `func.now()` → 返回 `timestamp with time zone`，不支持 `- integer`
- `func.current_date()` → 返回 `date` 类型，支持 `- integer`（减天数）

### 4.3 防御性修复（调度器层）

**给调度器增加启动时补结算机制**（`scheduler.py`）：

```python
async def run_catch_up_settlement() -> None:
    """启动时补执行遗漏的每日结算"""
    last_settlement = await get_latest_settlement_date()
    today = date.today()
    missed_days = get_missed_trading_days(last_settlement, today)
    for missed_date in missed_days:
        for account in accounts:
            await sim_engine.daily_settlement(account["id"], missed_date)
```

在 `scheduler_loop()` 启动时调用，确保即使进程重启也能补上遗漏的结算。

---

## 5. 验证结果

修复后逐一验证：

| 组件 | 验证结果 |
|------|---------|
| `get_missing_popularity_codes()` | ✅ 正确返回 199 个缺失代码 |
| `fetch_kline_tx()` | ✅ 正常获取日线数据 |
| `batch_upsert_stock_daily()` | ✅ 正确写入数据库 |
| `compute_and_store_indicators()` | ✅ 计算了 373 只股票的指标 |
| 002579.SZ 6月1日指标 | ✅ atr=1.0779, rsi=76.9, macd=1.214 |
| 002456.SZ 可卖数量 | ✅ 19,800 股（已解锁） |

---

## 6. 涉及文件

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `src/stock_service/crud/quant_crud.py` | Bug 修复 | `func.now()` → `func.current_date()` |
| `src/stock_service/scheduler.py` | 功能增强 | 新增 `run_catch_up_settlement()` 启动补结算 |

---

## 7. 经验教训

1. **PostgreSQL 类型系统严格**: `timestamp - integer` 不合法，必须使用 `date - integer` 或 `timestamp - interval`。ORM 的 `func.now()` 返回 `timestamp`，不等同于 `CURRENT_DATE`。

2. **静默异常吞噬问题**: `update_popularity_daily_data()` 的 `try/except` 捕获了所有异常但仅记录日志，导致关键功能失败数周未被发现。建议对核心数据管道增加监控告警。

3. **调度器需补执行机制**: 内存长驻进程的定时任务在进程重启后会丢失，需要在启动时检查并补偿遗漏的任务。

4. **数据依赖链需端到端测试**: `stock_daily` → `stock_indicator` → 策略信号 → 交易执行，任何一环断裂都会导致下游全部失效。
