# 测试账号 2/3/4/5 未执行交易 — 排查报告

> 日期：2026-06-01
> 用户：dadawanan（user_id=45）
> 问题：2点半定时触发后，测试账号2/3/4/5 均未执行任何交易，测试账户1和测试账号6正常

---

## 一、排查过程

### 1.1 定位用户和账户

**查 users 表**，确认用户存在：

```sql
SELECT id, username FROM users WHERE username = 'dadawanan';
-- 结果：id=45
```

**查 sim_account 表**，拉出该用户所有模拟账户：

```sql
SELECT id, account_name, status, strategy_id, strategy_ids, total_assets, config
FROM sim_account WHERE user_id = 45 ORDER BY id;
```

| id | account_name | status | strategy_id | strategy_ids | total_assets |
|----|-------------|--------|-------------|--------------|-------------|
| 1 | 测试账户 | active | 5 | [5] | 1,007,263 |
| 2 | 测试账号2 | active | 8 | [8] | 1,000,000 |
| 3 | 测试账号3 | active | 7 | NULL | 1,000,000 |
| 4 | 测试账号4 | active | 9 | NULL | 1,000,000 |
| 5 | 测试账号5 | active | 11 | NULL | 1,000,000 |
| 6 | 测试账号6 | active | 6 | NULL | 999,159 |

结论：6 个账户全部 `active`，每个都配置了策略 ID。排除"账户未激活"和"未配置策略"的可能。

### 1.2 查策略定义

**查 strategy 表**，确认策略存在且激活：

```sql
SELECT id, name, type, is_active FROM strategy ORDER BY id;
```

| id | name | type | is_active |
|----|------|------|-----------|
| 5 | 人气榜策略 | popularity | true |
| 6 | 情绪驱动策略 | sentiment | true |
| 7 | 技术面策略 | technical | true |
| 8 | 多因子策略 | multi_factor | true |
| 9 | 量价策略 | volume_price | true |
| 11 | 均值回归策略 | mean_reversion | true |

结论：所有策略均为 `is_active=true`。排除"策略未激活"的可能。

### 1.3 查交易记录

**查 trade_order 表**，确认哪些账户实际产生了交易：

```sql
SELECT to2.id, sa.account_name, sa.strategy_id, to2.code, to2.side,
       to2.price, to2.quantity, to2.status, to2.created_at
FROM trade_order to2
JOIN sim_account sa ON to2.account_id = sa.id
ORDER BY to2.created_at DESC;
```

| account_name | strategy_id | 交易笔数 | 最近交易时间 |
|-------------|-------------|---------|------------|
| 测试账户 | 5 (popularity) | 8 笔 | 2026-06-01 06:33 UTC |
| 测试账号6 | 6 (sentiment) | 4 笔 | 2026-06-01 06:33 UTC |
| **测试账号2** | **8 (multi_factor)** | **0 笔** | **无** |
| **测试账号3** | **7 (technical)** | **0 笔** | **无** |
| **测试账号4** | **9 (volume_price)** | **0 笔** | **无** |
| **测试账号5** | **11 (mean_reversion)** | **0 笔** | **无** |

结论：只有 popularity 和 sentiment 策略产生了交易，其余 4 个策略零交易。

### 1.4 查挂单记录

**查 pending_order 表**，确认是否走了挂单路径但未成交：

```sql
SELECT po.id, sa.account_name, po.code, po.side, po.status
FROM pending_order po
JOIN sim_account sa ON po.account_id = sa.id
WHERE po.account_id IN (2, 3, 4, 5);
-- 结果：0 行
```

结论：不是"挂单未成交"的问题，而是根本没有产生交易信号。

### 1.5 查策略选股记录

**查 strategy_pick 表**：

```sql
SELECT count(*) FROM strategy_pick;
-- 结果：0 行
```

结论：整个 strategy_pick 表为空，说明策略信号从未落库（代码中未实现写入逻辑）。

### 1.6 查 Pipeline 执行情况

**查 pipeline_run 表**，确认 14:30 是否触发了流水线：

```sql
SELECT id, run_type, trade_date, stock_count, news_count, market_count,
       analysis_count, status, started_at, finished_at
FROM pipeline_run WHERE started_at >= '2026-06-01' ORDER BY started_at;
```

| id | run_type | stock_count | news_count | market_count | analysis_count |
|----|----------|------------|------------|--------------|----------------|
| 313 | fetch | 4 | 0 | 0 | 0 |
| 314 | fetch | 0 | 221 | 42 | 0 |
| 315 | analyze | 0 | 0 | 0 | 42 |

结论：流水线执行成功，抓取了 4 只新入场股票、221 条新闻、42 条行情、42 条分析。Pipeline 本身没有报错。

### 1.7 查新入场股票的日线数据

**查 stock_daily 表**，验证策略依赖的数据是否存在：

```sql
-- 新入场股票
SELECT code, trade_date, open, close, volume
FROM stock_daily
WHERE code IN ('603890.SH', '002456.SZ', '605277.SH', '002806.SZ')
  AND trade_date >= '2026-05-30';
-- 结果：0 行
```

```sql
-- 今天全市场
SELECT code, trade_date FROM stock_daily WHERE trade_date = '2026-06-01';
-- 结果：0 行
```

结论：**stock_daily 表中没有 2026-06-01 的任何数据**。

### 1.8 查技术指标数据

**查 stock_indicator 表**：

```sql
SELECT code, trade_date, ma5, ma20, rsi, macd, atr
FROM stock_indicator
WHERE code IN ('603890.SH', '002456.SZ', '605277.SH', '002806.SZ')
  AND trade_date >= '2026-05-30';
-- 结果：0 行
```

结论：**stock_indicator 表中也没有今天的数据**。

### 1.9 对比：有交易的股票数据情况

```sql
-- 测试账户1 买入了 002456.SZ
SELECT code, trade_date, open, close, volume
FROM stock_daily WHERE code = '002456.SZ' ORDER BY trade_date DESC LIMIT 5;
```

| code | trade_date | open | close | volume |
|------|-----------|------|-------|--------|
| 002456.SZ | 2026-05-29 | 9.51 | 8.96 | NULL |
| 002456.SZ | 2026-05-28 | 9.38 | 9.62 | NULL |
| ... | ... | ... | ... | ... |

结论：002456.SZ 有历史日线数据（到 05-29），但**没有 06-01 的数据**。popularity 策略不需要 stock_daily，所以能正常交易。

---

## 二、根因分析

### 2.1 代码流程还原

`run_pipeline()` 函数（scheduler.py:75-109）的执行流程：

```
run_pipeline()
  │
  ├─ async with AsyncSessionFactory() as session:    ← Session A 创建
  │   ├─ run_popularity_pipeline(session)             ← Session A 写入 popularity_snapshot
  │   ├─ run_fetch_pipeline_for_rows(session, ...)    ← Session A 写入 news_article, market_snapshot
  │   ├─ run_and_store(session, ...)                  ← Session A 写入 stock_analysis_snapshot
  │   └─ session.commit()                             ← Session A 提交 ✅
  │
  ├─ update_popularity_daily_data()                   ← 内部创建 Session B，写入 stock_daily，Session B 提交 ✅
  │
  ├─ async with AsyncSessionFactory() as session:    ← Session C 创建
  │   └─ compute_and_store_indicators(session)        ← Session C 写入 stock_indicator，Session C 提交 ✅
  │
  └─ auto_trade_for_accounts(session, new_entries)    ← ⚠️ 用 Session A 读数据！
```

### 2.2 问题本质：PostgreSQL MVCC 事务隔离

PostgreSQL 默认使用 **Read Committed** 隔离级别。每个事务在 `BEGIN` 时创建一个**快照**，只能看到该快照之前已提交的数据。

- Session A 在 `commit()` 后，其事务上下文已结束
- 后续 `auto_trade_for_accounts(session, ...)` 虽然传入了同一个 `session` 对象，但该 session 的事务快照是在 commit 之前创建的
- Session B/C 写入的 `stock_daily` 和 `stock_indicator` 数据在 Session A 的快照中**不可见**

### 2.3 各策略的数据依赖与失败原因

`auto_trade_for_accounts` 构建 `StrategyContext` 时（scheduler.py:196-236）：

```python
# 1. 获取日线数据 → 用 session 查询 → 看不到 Session B 写入的数据
daily = await quant_crud.get_stock_daily(session, code, start_date=trade_date, end_date=trade_date)
# → 返回空列表 → market_data[code] 不存在

# 2. 获取技术指标 → 用 session 查询 → 看不到 Session C 写入的数据
ind = await quant_crud.get_stock_indicator(session, code, trade_date=trade_date)
# → 返回 None → indicators[code] 不存在

# 3. 获取分析结果 → 由 AnalysisAdapter 查询 stock_analysis_snapshot
analysis = await adapter.get_analysis_signals(stock_codes)
# → Session A 中已写入 → 能正常获取 ✅

# 4. 获取人气榜数据 → 由 get_latest_popularity_data 查询
popularity_data = await quant_crud.get_latest_popularity_data(session)
# → Session A 中已写入 → 能正常获取 ✅
```

各策略对 Context 的依赖：

| 策略 | 依赖字段 | 数据来源 | 是否可见 | 结果 |
|------|---------|---------|---------|------|
| **popularity** | `context.popularity` | Session A 写入 | ✅ 可见 | 能产生信号 |
| **sentiment** | `context.analysis` | Session A 写入 | ✅ 可见 | 能产生信号 |
| **technical** | `context.indicators` | Session C 写入 | ❌ 不可见 | 无信号 |
| **multi_factor** | popularity + sentiment + technical | 混合 | 部分不可见 | 综合分不够阈值 |
| **volume_price** | `context.market_data` | Session B 写入 | ❌ 不可见 | 无信号 |
| **mean_reversion** | `context.indicators` + `context.market_data` | Session B/C 写入 | ❌ 不可见 | 无信号 |

### 2.4 为什么是"2点半"触发的

调度器在 `scheduler_loop()` 中定义了三个触发时间（scheduler.py:531-535）：

```python
trigger_times = [
    time(9, 25),   # 开盘前
    time(14, 30),  # 下午盘 ← 2点半
    time(15, 5),   # 收盘后
]
```

14:30 触发时调用 `run_pipeline()`，其中包含 `auto_trade_for_accounts()`，所以问题在 14:30 暴露。

---

## 三、修复方案

### 方案：auto_trade_for_accounts 使用独立的新 Session

将 `auto_trade_for_accounts` 改为在新的 Session 中执行，确保能看到 Session B/C 已提交的数据。

**修改文件**：`src/stock_service/scheduler.py`

**修改前**（第 108-109 行）：

```python
            # 自动执行模拟盘交易
            await auto_trade_for_accounts(session, new_entries)
```

**修改后**：

```python
            # 自动执行模拟盘交易（使用新 session，确保能读取到 daily/indicator 数据）
            async with AsyncSessionFactory() as trade_session:
                await auto_trade_for_accounts(trade_session, new_entries)
```

### 验证方法

修复后，需要验证以下几点：

1. **technical 策略**（测试账号3）：检查 `context.indicators` 是否有数据
2. **volume_price 策略**（测试账号4）：检查 `context.market_data` 是否有数据
3. **mean_reversion 策略**（测试账号5）：检查 `context.indicators` 和 `context.market_data` 是否有数据
4. **multi_factor 策略**（测试账号2）：检查综合分是否达到阈值

建议在下一个交易日（周一）14:30 触发后，检查 `trade_order` 表是否新增了测试账号 2-5 的交易记录。
