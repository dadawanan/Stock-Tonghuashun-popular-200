# 定时任务 9:25 流水线详解

> 文件：`src/stock_service/scheduler.py` → `run_pipeline()`

---

## 触发条件

- **时间**：每个交易日（周一至周五）9:25（开盘前 5 分钟）
- **精度**：±2 分钟内匹配
- **去重**：每天同一时间只触发一次，日期变更后重置

---

## 执行流程

```
9:25 触发
    │
    ▼
┌─────────────────────────────────────────────┐
│ Step 1: 采集人气榜 (run_popularity_pipeline) │
│   - 调用同花顺 pywencai 获取 Top 200         │
│   - 与上次榜单对比，识别新增股票              │
│   - 写入 popularity_snapshot 表               │
│   - 写入 pipeline_run 审计记录                │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│ Step 2: 抓取新增股票数据 (仅新增股票)         │
│   条件：new_entries 不为空                    │
│                                              │
│   2a. 新闻+行情抓取 (run_fetch_pipeline_for_rows) │
│     - 并发抓取新闻 (同花顺)                   │
│     - 并发抓取实时行情 (东方财富/腾讯)        │
│     - 并发抓取资金流数据                      │
│     - 写入 news_article 表                    │
│     - 写入 market_snapshot 表                 │
│                                              │
│   2b. 分析 (run_and_store)                    │
│     - 文本情绪分析 (规则引擎)                 │
│     - 市场行为分析 (量价/资金流)              │
│     - 综合评分 + 决策建议                     │
│     - 写入 stock_analysis_snapshot 表         │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│ Step 3: 补全日线数据 (update_popularity_daily_data) │
│   - 查找人气榜中缺少近 3 天日线数据的股票     │
│   - 从腾讯行情拉取最近 1 年 K 线             │
│   - 写入 stock_daily 表 (OHLCV)              │
│   - 连续失败 3 次自动停止                     │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│ Step 4: 计算技术指标 (compute_and_store_indicators) │
│   - 从 stock_daily 计算：                     │
│     MA5, MA20, RSI, MACD, 布林带上下轨       │
│   - 写入 stock_indicator 表                   │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│ Step 5: 自动交易 (auto_trade_for_accounts)    │
│   条件：存在配置了策略的模拟账户              │
│                                              │
│   5a. 获取账户策略配置                        │
│   5b. 填充策略上下文数据                      │
│     - market_data (stock_daily + market_snapshot) │
│     - indicators (stock_indicator)            │
│     - analysis (stock_analysis_snapshot)      │
│     - popularity (popularity_snapshot)        │
│   5c. 运行所有策略，收集信号                  │
│   5d. 多策略共识过滤                          │
│     - 只有所有策略方向一致才执行              │
│   5e. 执行交易                                │
│     - 交易时间内 → 直接执行                   │
│     - 非交易时间 → 创建挂单                   │
└─────────────────────────────────────────────┘
```

---

## 涉及的数据库表

| 步骤 | 写入表 | 说明 |
|------|--------|------|
| Step 1 | `pipeline_run` | 流水线审计记录 |
| Step 1 | `popularity_snapshot` | 人气榜快照 |
| Step 1 | `stock_master` | 股票主数据（新增股票） |
| Step 2a | `news_article` | 新闻文章 |
| Step 2a | `market_snapshot` | 实时行情快照 |
| Step 2b | `stock_analysis_snapshot` | 分析结果 |
| Step 3 | `stock_daily` | 日线 OHLCV |
| Step 4 | `stock_indicator` | 技术指标 |
| Step 5 | `trade_order` | 交易订单 |
| Step 5 | `pending_order` | 挂单 |

---

## 涉及的外部 API

| 步骤 | API | 用途 |
|------|-----|------|
| Step 1 | 同花顺 pywencai | 获取人气榜 Top 200 |
| Step 2a | 同花顺 | 抓取新闻 |
| Step 2a | 东方财富/腾讯 | 实时行情、资金流 |
| Step 3 | 腾讯行情 | 历史 K 线 |
| Step 5 | 腾讯行情 | 实时价格（用于交易） |

---

## 数据流向图

```
同花顺 API
    │
    ▼
popularity_snapshot ──→ 对比上次 ──→ new_entries
    │                                    │
    │                                    ▼
    │                          news_article + market_snapshot
    │                                    │
    │                                    ▼
    │                          stock_analysis_snapshot
    │
    ▼
腾讯 K 线 API ──→ stock_daily ──→ stock_indicator
                                        │
                                        ▼
                              策略引擎 (10 种策略)
                                        │
                                        ▼
                              多策略共识 ──→ 交易/挂单
```

---

## 同时 14:30 也会触发

14:30 执行的逻辑与 9:25 **完全相同**（`run_pipeline()`），目的是在下午盘前更新数据。

---

## 15:05 触发每日结算

- 对所有活跃模拟账户执行 `daily_settlement()`
- 更新持仓市值、盈亏
- 触发止损检查
- 取消当天未成交的挂单

---

## 交易时间内的额外任务

每 60 秒执行一次 `check_pending_orders()`：
- 获取所有 pending 状态的挂单
- 检查实时价格是否满足成交条件
- 满足则执行成交，更新挂单状态为 filled
