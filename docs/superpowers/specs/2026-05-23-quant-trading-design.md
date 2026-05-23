# 量化交易模块设计文档

> 日期: 2026-05-23
> 状态: 已确认
> 方案: 渐进式集成（方案 A）

---

## 1. 概述

### 1.1 目标

基于现有股票分析流水线，构建量化交易模块，覆盖：
- **策略研究**：可插拔策略架构，支持多种策略类型
- **历史回测**：含交易成本、风控约束的真实回测
- **模拟盘**：用户隔离、T+1 规则的模拟交易系统
- **闭环反馈**：回测结果反向优化分析规则权重

### 1.2 范围

- 暂不接入实盘，但架构预留实盘接口
- 复用现有 `schema_quant_v1.sql` 基础表，按需扩展

---

## 2. 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                    API Routes                           │
│  /quant/strategies  /quant/backtest  /quant/sim         │
└───────────────┬─────────────────────────────────────────┘
                │
┌───────────────▼─────────────────────────────────────────┐
│              Application Services                       │
│  StrategyService  BacktestService  SimTradingService    │
└───────┬───────────────┬───────────────┬─────────────────┘
        │               │               │
┌───────▼───────┐ ┌─────▼─────┐ ┌───────▼───────┐
│ Strategy      │ │ Backtest  │ │ Sim Trading   │
│ Engine        │ │ Engine    │ │ Engine        │
│ (Domain)      │ │ (Domain)  │ │ (Domain)      │
└───────────────┘ └───────────┘ └───────────────┘
        │               │               │
┌───────▼───────────────▼───────────────▼─────────────────┐
│              Infrastructure                             │
│  DataProvider(akshare/CSV)  AnalysisResultAdapter       │
└─────────────────────────────────────────────────────────┘
```

### 2.1 核心数据流

```
分析流水线 → stock_analysis_snapshot
                    ↓
            Strategy Signal (买入/卖出/持有)
                    ↓
    ┌───────────────┼───────────────┐
    ↓               ↓               ↓
  回测引擎      模拟盘引擎      闭环反馈
    ↓               ↓               ↓
  回测报告      持仓/交易记录    分析权重调整
```

### 2.2 文件结构

```
src/stock_service/
  quant/
    __init__.py
    domain/
      __init__.py
      strategy_interface.py    # 策略抽象基类
      backtest_rules.py        # 回测规则（滑点、手续费、T+1）
      risk_manager.py          # 风控逻辑
      indicators.py            # 技术指标计算
    application/
      __init__.py
      strategy_engine.py       # 策略调度器
      backtest_engine.py       # 回测引擎
      sim_trading_engine.py    # 模拟盘引擎
      feedback_service.py      # 闭环反馈服务
    infrastructure/
      __init__.py
      data_provider.py         # akshare/CSV 数据适配
      analysis_adapter.py      # 分析结果适配器
    crud/
      __init__.py
      quant_crud.py            # 量化 CRUD（扩展现有）
    schemas.py                 # Pydantic 模型
    api/
      __init__.py
      routes/
        strategies.py          # 策略管理接口
        data.py                # 数据管理接口
        backtest.py            # 回测接口
        sim_trading.py         # 模拟盘接口
        feedback.py            # 反馈接口
```

---

## 3. 数据库设计

### 3.1 新增表

#### strategy（策略定义表）

```sql
CREATE TABLE IF NOT EXISTS strategy (
    id          BIGSERIAL PRIMARY KEY,
    name        VARCHAR(64) NOT NULL,
    type        VARCHAR(32) NOT NULL,  -- popularity/sentiment/technical/multi_factor
    params      JSONB,                 -- 策略参数（如阈值、权重等）
    description TEXT,
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

#### backtest_trade（回测交易明细表）

```sql
CREATE TABLE IF NOT EXISTS backtest_trade (
    id              BIGSERIAL PRIMARY KEY,
    backtest_id     BIGINT NOT NULL REFERENCES backtest_result(id),
    code            VARCHAR(16) NOT NULL,
    side            VARCHAR(8) NOT NULL,   -- buy/sell
    price           NUMERIC(18, 4),
    quantity        INTEGER,
    trade_date      DATE NOT NULL,
    pnl             NUMERIC(18, 4),        -- 单笔盈亏
    signal_source   VARCHAR(32),           -- 信号来源策略
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

#### backtest_daily_nav（回测每日净值表）

```sql
CREATE TABLE IF NOT EXISTS backtest_daily_nav (
    id              BIGSERIAL PRIMARY KEY,
    backtest_id     BIGINT NOT NULL REFERENCES backtest_result(id),
    trade_date      DATE NOT NULL,
    nav             NUMERIC(18, 6),  -- 单位净值
    total_assets    NUMERIC(18, 2),  -- 总资产
    cash            NUMERIC(18, 2),  -- 现金
    position_value  NUMERIC(18, 2),  -- 持仓市值
    benchmark_nav   NUMERIC(18, 6),  -- 基准净值
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_backtest_daily_nav UNIQUE (backtest_id, trade_date)
);
```

#### sim_account（模拟账户表）

```sql
CREATE TABLE IF NOT EXISTS sim_account (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES users(id),
    account_name    VARCHAR(64) NOT NULL,
    initial_capital NUMERIC(18, 2) NOT NULL DEFAULT 1000000.00,
    current_capital NUMERIC(18, 2) NOT NULL,
    total_assets    NUMERIC(18, 2) NOT NULL,
    status          VARCHAR(16) DEFAULT 'active',  -- active/frozen/closed
    strategy_id     BIGINT REFERENCES strategy(id),
    config          JSONB,                          -- 手续费率、风控规则等
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

#### position_daily_snapshot（持仓每日快照表）

```sql
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
```

#### feedback_log（反馈日志表）

```sql
CREATE TABLE IF NOT EXISTS feedback_log (
    id              BIGSERIAL PRIMARY KEY,
    backtest_id     BIGINT NOT NULL REFERENCES backtest_result(id),
    strategy_id     BIGINT NOT NULL REFERENCES strategy(id),
    feedback_type   VARCHAR(32) NOT NULL,  -- weight_adjustment / rule_suggestion
    before_params   JSONB,
    after_params    JSONB,
    reason          TEXT,
    status          VARCHAR(16) DEFAULT 'pending',  -- pending / applied / rejected
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 3.2 扩展表

#### trade_order（扩展字段）

```sql
ALTER TABLE trade_order
    ADD COLUMN strategy_id BIGINT,
    ADD COLUMN trade_at TIMESTAMPTZ,
    ADD COLUMN commission NUMERIC(18, 4) DEFAULT 0,
    ADD COLUMN slippage NUMERIC(18, 4) DEFAULT 0;
```

#### position_account（扩展字段）

```sql
ALTER TABLE position_account
    ADD COLUMN available_quantity INTEGER;  -- 可卖数量（T+1）
```

---

## 4. 策略引擎设计

### 4.1 策略接口

```python
class SignalType(Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"

@dataclass
class Signal:
    code: str
    signal_type: SignalType
    score: float           # 信号强度 (0-1)
    reason: str            # 触发原因
    target_price: float | None = None
    stop_loss: float | None = None

class BaseStrategy(ABC):
    @abstractmethod
    async def generate_signals(
        self,
        trade_date: date,
        stock_codes: list[str],
        context: dict
    ) -> list[Signal]:
        pass

    @abstractmethod
    def get_params(self) -> dict:
        pass

    @abstractmethod
    def set_params(self, params: dict):
        pass
```

### 4.2 四种内置策略

| 策略 | 信号源 | 核心参数 |
|------|--------|----------|
| **PopularityStrategy** | 人气排名、排名变化、新增/退出 | top_n, rank_drop_threshold, rank_rise_threshold |
| **SentimentStrategy** | text_score, market_score, integrated_score | text_weight, market_weight, buy_threshold, sell_threshold |
| **TechnicalStrategy** | MA, RSI, MACD, KDJ, BOLL | ma_short, ma_long, rsi_overbought, rsi_oversold |
| **MultiFactorStrategy** | 所有信号加权组合 | weights (popularity/sentiment/technical), buy_threshold |

### 4.3 策略调度器

```python
class StrategyEngine:
    def __init__(self):
        self._strategies: dict[str, BaseStrategy] = {}

    def register(self, name: str, strategy: BaseStrategy):
        self._strategies[name] = strategy

    async def run_strategy(
        self, strategy_name: str, trade_date: date,
        stock_codes: list[str], context: dict
    ) -> list[Signal]:
        strategy = self._strategies.get(strategy_name)
        if not strategy:
            raise ValueError(f"Strategy '{strategy_name}' not found")
        return await strategy.generate_signals(trade_date, stock_codes, context)
```

---

## 5. 回测引擎设计

### 5.1 回测配置

```python
@dataclass
class BacktestConfig:
    initial_capital: float = 1000000.0
    commission_rate: float = 0.0003      # 万三手续费
    stamp_tax: float = 0.001             # 千一印花税（仅卖出）
    slippage: float = 0.002              # 0.2% 滑点
    max_position_pct: float = 0.2        # 单只最大仓位 20%
    max_holdings: int = 10               # 最大持仓 10 只
    stop_loss_pct: float = -0.08         # 止损线 -8%
    t_plus_1: bool = True                # T+1 限制
```

### 5.2 回测流程

```
for each trade_date in [start_date, end_date]:
    1. 获取当日行情数据 (stock_daily + stock_indicator)
    2. 获取当日分析结果 (stock_analysis_snapshot)
    3. 构建 context (行情 + 分析 + 持仓)
    4. 调用策略生成信号
    5. 信号过滤 (风控规则)
    6. 执行交易 (计算手续费、滑点、T+1)
    7. 更新持仓
    8. 记录每日净值
```

### 5.3 回测结果指标

```python
@dataclass
class BacktestMetrics:
    # 收益指标
    total_return: float          # 总收益率
    annual_return: float         # 年化收益率
    benchmark_return: float      # 基准收益率（沪深300）
    excess_return: float         # 超额收益

    # 风险指标
    max_drawdown: float          # 最大回撤
    max_drawdown_duration: int   # 最大回撤持续天数
    sharpe_ratio: float          # 夏普比率
    sortino_ratio: float         # 索提诺比率
    volatility: float            # 波动率

    # 交易指标
    total_trades: int            # 总交易次数
    win_rate: float              # 胜率
    profit_loss_ratio: float     # 盈亏比
    avg_holding_days: float      # 平均持仓天数
    max_consecutive_wins: int    # 最大连续盈利次数
    max_consecutive_losses: int  # 最大连续亏损次数
```

---

## 6. 模拟盘引擎设计

### 6.1 账户体系

```
users (现有)
    │
    ▼
sim_account (新增)
├── user_id → users.id
├── account_name
├── initial_capital / current_capital / total_assets
├── status (active/frozen/closed)
├── strategy_id (可选)
└── config (JSONB: 手续费率、风控规则等)

    ├─── 1:N ───→ trade_order (通过 account_id 关联)
    └─── 1:N ───→ position_account (通过 account_id 关联)
```

### 6.2 用户隔离

每个操作都验证 `account_id` 归属当前用户：

```python
async def verify_account_ownership(
    session: AsyncSession, user_id: int, account_id: int
) -> bool:
    result = await session.execute(
        select(SimAccount).where(
            SimAccount.id == account_id,
            SimAccount.user_id == user_id
        )
    )
    return result.scalars().first() is not None
```

### 6.3 T+1 处理机制

- 买入时 `available_quantity = 0`（当日不可卖）
- 每日结算时 `available_quantity = quantity`（昨日持仓今日可卖）

### 6.4 自动止损

每日结算前检查所有持仓，触发止损线自动卖出。

---

## 7. 数据层设计

### 7.1 数据源架构

```
QuantDataProvider (统一入口)
├── AkshareAdapter   # 日线行情、实时行情
├── CSVAdapter       # 本地 CSV 导入
└── DBAdapter        # 从现有表读取
```

### 7.2 数据采集策略

1. 优先从 `stock_daily` 表读取已有数据
2. 计算缺失日期范围
3. 从 akshare 补充缺失数据
4. 支持本地 CSV 导入覆盖

### 7.3 技术指标计算

在 `quant/domain/indicators.py` 中实现纯函数计算：
- MA (移动平均线)
- RSI (相对强弱指标)
- MACD (指数平滑异同移动平均线)
- KDJ (随机指标)
- BOLL (布林带)

---

## 8. 闭环反馈设计

### 8.1 反馈流程

```
分析流水线 (信号产出)
    ↓
量化策略 (信号消费)
    ↓
回测验证 (效果评估)
    ↓
反馈调整分析权重
```

### 8.2 反馈机制

1. **回测洞察分析**：按信号来源分组统计胜率、盈亏
2. **权重调整建议**：基于各信号表现建议调整 MultiFactor 权重
3. **规则优化建议**：分析失败交易，建议调整分析规则关键词

### 8.3 反馈数据表

`feedback_log` 记录每次反馈的调整前后参数、原因、状态（pending/applied/rejected）。

---

## 9. API 设计

### 9.1 路由结构

```
/api/quant/
├── /strategies              # 策略管理 (CRUD)
├── /data                    # 数据管理 (采集、导入、查询)
├── /backtest                # 回测 (运行、结果、对比)
├── /sim                     # 模拟盘 (账户、持仓、下单)
└── /feedback                # 反馈 (洞察、建议)
```

### 9.2 认证

所有接口复用现有 JWT 鉴权（`get_current_user` 依赖）。

---

## 10. 实现阶段

### Phase 1: 基础设施（数据层 + 策略接口）
- 扩展 schema，新增表
- 实现数据采集服务
- 实现策略接口和内置策略

### Phase 2: 回测引擎
- 实现回测规则引擎
- 实现回测结果计算
- API 接口

### Phase 3: 模拟盘
- 实现账户管理
- 实现交易引擎
- 实现 T+1 和止损

### Phase 4: 闭环反馈
- 实现回测分析
- 实现权重调整建议
- API 接口
