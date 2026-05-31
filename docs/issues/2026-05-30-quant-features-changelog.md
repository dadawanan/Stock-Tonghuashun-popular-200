# 量化交易系统功能更新日志 (2026-05-30)

---

## 一、策略信号预览修复

### 问题
调用 `POST /api/quant/strategies/signals/preview` 返回 500，大部分策略无信号。

### 修复内容

| 问题 | 修复 |
|------|------|
| `strategy_engine` 是模块不是实例 | 在 `strategy_engine.py` 末尾创建全局 `engine` 实例 |
| `date.today()` 查不到数据 | 改为查人气榜覆盖最多的交易日 |
| `stock_indicator` 从未写入 | 新增 `compute_and_store_indicators()` |
| 缺少实时行情字段 | 从 `market_snapshot` 补充 pct_change/volume_ratio/main_net_inflow |
| 500 错误无详细信息 | 添加全局异常处理器（dev 返回 traceback） |

### 使用
```
POST /api/quant/strategies/signals/preview
Body: {"strategy_ids": [7], "max_stocks": 50}
```

---

## 二、ATR 止损

### 实现
在 `BacktestConfig` 中已有 `atr_stop_multiplier` 字段但从未使用。现在完整实现了 ATR 止损逻辑。

### 改动文件
- `quant/domain/indicators.py` — 新增 `atr()` 方法（14 日 ATR）
- `db/models/quant_models.py` — `StockIndicator` 新增 `atr` 字段
- `crud/quant_crud.py` — upsert 加入 `atr` 字段
- `application/services/market_data_service.py` — 指标计算包含 ATR
- `quant/domain/backtest_rules.py` — `check_stop_loss()` 新增 ATR 止损
- `quant/application/backtest_engine.py` — 回测传入 ATR
- `quant/application/sim_trading_engine.py` — 模拟盘结算传入 ATR

### 止损逻辑（按优先级）
1. **固定止损** — 亏损超过 `stop_loss_pct`（默认 -8%）
2. **ATR 止损** — 价格跌破 `买入价 - N倍 ATR`（`atr_stop_multiplier=2.0`）
3. **移动止损** — 从最高点回撤超过 `trailing_stop_pct`

### 使用
```python
config = BacktestConfig(atr_stop_multiplier=2.0)  # 2倍ATR止损
# 止损线 = 买入价 - 2.0 × ATR(14)
# 例：买入价10元，ATR=0.5 → 止损线=9.0元
```

### 注意
需要先运行"计算指标"生成 ATR 数据。`atr_stop_multiplier=0` 则禁用 ATR 止损。

---

## 三、最大回撤强制执行

### 之前
回撤超限只打日志，不暂停交易。

### 现在
- **买入检查** — `buy()` 方法中，回撤超限抛出 `ValueError` 拒绝交易
- **每日结算** — 回撤超限时将账户状态改为 `drawdown_halt`

### 效果
账户状态变为 `drawdown_halt` 后：
- 手动交易被拒绝
- 自动交易跳过该账户
- 需要手动将状态改回 `active` 才能恢复

### 配置
```python
# 在账户 config 中设置
config = {"max_drawdown_pct": -0.20}  # 最大回撤 -20%
```

---

## 四、市场环境识别

### 实现
基于沪深 300 指数的 MA50/MA200 判断市场环境。

### 判断规则
| 环境 | 条件 | 策略调整 |
|------|------|----------|
| 🐂 牛市 | MA50 > MA200 × 1.02 | 买入门槛降低 20% |
| 🐻 熊市 | MA50 < MA200 × 0.98 | 买入门槛提高 50%，卖出门槛降低 20% |
| ➡️ 震荡 | 其他 | 不变 |

### 改动文件
- `quant/domain/strategy_interface.py` — 新增 `MarketRegime` 枚举
- `quant/domain/market_regime.py` — **新建**，`detect_market_regime()` 函数
- `quant/api/routes/strategies.py` — 信号预览注入环境
- `quant/application/backtest_engine.py` — 回测注入环境
- `quant/application/strategy_engine.py` — `TechnicalStrategy` 和 `MomentumStrategy` 根据环境调整阈值

### 效果
- 牛市中更容易产生买入信号（追涨）
- 熊市中更难买入、更容易卖出（防守）
- 当前实时检测结果可通过信号预览接口查看

---

## 五、波动率调整仓位

### 实现
根据 ATR/价格 计算波动率，自动调整仓位大小。

### 公式
```
调整后仓位 = 基础仓位 × clamp(目标波动率 / 实际波动率, 0.5, 1.5)
目标波动率 = 3%（中等波动基准）
```

### 效果示例
| 股票波动率 | ATR/价格 | 仓位调整 | 效果 |
|-----------|---------|---------|------|
| 低（1%） | 0.5/50 | ×1.5 | 加仓到 30% |
| 中（3%） | 1.5/50 | ×1.0 | 不变 20% |
| 高（6%） | 3.0/50 | ×0.5 | 减仓到 10% |

### 改动文件
- `quant/domain/risk_manager.py` — `calculate_buy_quantity()` 新增 `atr_value` 参数
- `quant/application/backtest_engine.py` — 回测买入时传入 ATR
- `scheduler.py` — 自动交易（挂单+直接交易）传入 ATR

### 注意
需要先运行"计算指标"生成 ATR 数据。

---

## 六、更多绩效指标

### 新增指标（回测结果中）

| 指标 | 说明 | 公式 |
|------|------|------|
| **Sortino** | Sortino 比率 | (年化收益 - 无风险) / 下行波动率 |
| **Calmar** | Calmar 比率 | 年化收益 / 最大回撤 |
| **Alpha** | 超额收益 | 年化收益 - (无风险 + β × 基准超额) |
| **Beta** | 系统性风险 | Cov(组合, 基准) / Var(基准) |
| **信息比率** | 信息比率 | 超额收益 / 跟踪误差 |
| **回撤天数** | 回撤持续天数 | 从回撤到恢复的最长天数 |
| **月度收益** | 月度收益分解 | {月份: 收益率} |

### 前端展示
回测结果页面新增 7 个指标卡片：Sortino、Calmar、Alpha（带红绿色）、Beta、信息比率、回撤天数。

---

## 七、滚动前进优化（Walk-Forward）

### 问题
网格搜索在同一时间段训练+测试，容易过拟合。

### 解决方案
将历史数据分成多个滚动窗口：

```
窗口1: |---训练180天---|---测试60天---|
窗口2:     |---训练180天---|---测试60天---|
窗口3:         |---训练180天---|---测试60天---|
```

每个窗口在训练期找最优参数，在测试期验证。最终取各窗口测试结果的平均值。

### 使用方式

**API**：
```
POST /api/quant/optimizer/walk-forward
{
  "strategy_id": 7,
  "param_grid": {"buy_threshold": [0.2, 0.3, 0.4], "sell_threshold": [-0.4, -0.3, -0.2]},
  "start_date": "2025-06-01",
  "end_date": "2026-05-30",
  "train_days": 180,
  "test_days": 60,
  "step_days": 60,
  "metric": "sharpe_ratio"
}
```

**前端**：参数优化页面 → "滚动前进优化" Tab

### 返回结果
```json
{
  "windows": [
    {"window_id": 1, "train_period": "...", "test_period": "...", "best_params": {...}, "test_metrics": {...}},
    ...
  ],
  "avg_test_metrics": {"avg_total_return": 0.15, "avg_sharpe_ratio": 1.2, ...},
  "best_params_per_window": [...],
  "stability_score": 0.75
}
```

### 参数稳定性解读
| 稳定性 | 含义 |
|--------|------|
| ≥70% | 参数稳健，不同时期都适用 |
| 40%-70% | 一般，部分参数随市场变化 |
| <40% | 不稳定，可能过拟合 |

---

## 八、代码质量改进

| 改动 | 说明 |
|------|------|
| `print()` → `logging` | 12 处改为 logger |
| bare `except:` | 改为 `except (ValueError, TypeError)` |
| `normalize_stock_code` 导入统一 | 全部从 `domain.services.stock_utils` 导入 |
| 错误响应格式统一 | `HTTPException` 统一返回 `{"code": ..., "msg": ..., "data": null}` |
| `_rows_to_dicts` 去重 | 提取到 `crud/utils.py` |
| StrategyEngine 注册去重 | 统一使用 `strategy_engine.py` 的全局 `engine` |
| 原始 SQL 清理 | CRUD 层和路由中的原始 SQL 全部迁回 ORM |
| settings 惰性化 | `import settings` 不再触发 `.env` 读取 |
| 空目录清理 | 删除 `quant/crud/`、`infrastructure/db/repositories/` |
| CORS 默认值 | 移除硬编码的生产 IP |
| Alembic 引入 | 数据库 schema 版本管理 |
| 分析规则配置化 | 规则移至 `config/analysis_rules.yaml` |
| docker-compose | 移除废弃的 `version` 键 |
| pyproject.toml | 补全项目描述 |

---

## 九、数据维护工具

| 端点 | 功能 |
|------|------|
| `POST /api/quant/daily/backfill` | 从腾讯行情补全人气榜股票的日线 K 线 |
| `POST /api/quant/indicators/compute` | 从 stock_daily 计算技术指标 |

**前端入口**：策略管理页面 → "补全数据"、"计算指标"按钮

**建议执行顺序**：
1. 补全数据 — 拉取最近一年 K 线
2. 计算指标 — 计算 MA/RSI/MACD/布林带/ATR
3. 信号预览 — 查看策略信号
