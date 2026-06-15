# Stock 量化交易平台 - 项目文档

## 项目概览

**项目名称**: A股量化交易平台 (Stock Service)
**项目版本**: 0.1.0
**Python版本**: >=3.12
**许可证**: Private

### 核心功能

#### 1. 数据采集
- **同花顺人气榜**: 自动采集 Top 200 热门股票（交易日 9:25 / 14:30）
- **新闻数据**: 从东方财富、同花顺等多源抓取股票相关新闻
- **行情数据**: 实时行情、日线数据、资金流向
- **技术指标**: 自动计算 MA/RSI/MACD/BOLL/ATR 等指标

#### 2. 股票分析
- **新闻情绪分析**: 6种事件模式（利好/利空/中性等）+ 正负面词统计
- **市场行为分析**: 量价信号（放量上涨/下跌）+ 资金流信号（主力净流入/流出）
- **综合评分**: 文本分 × 0.55 + 市场分 × 0.45

#### 3. 量化交易
- **10种内置策略**: 人气榜、情绪驱动、技术面、多因子、量价、动量、均值回归、资金流、突破、网格
- **回测系统**: 含交易成本、T+1、滑点、多策略对比、沪深300基准对比
- **模拟盘**: 市价单/限价单、止损止盈（固定+移动）、账户回撤限制、多策略共识
- **参数优化**: 网格搜索最优策略参数
- **闭环反馈**: 回测结果反向优化策略权重

#### 4. 定时任务
- **自动采集**: 交易日 9:25 / 14:30 自动触发
- **自动交易**: 根据策略信号自动执行模拟交易
- **每日结算**: 15:05 执行 T+1 解锁、止损检查
- **挂单检查**: 交易时间内每60秒检查挂单成交

### 项目目标
为A股投资者提供一个完整的量化交易平台，支持数据采集、分析、策略回测和模拟交易。

---

## 项目架构

### 整体架构图
```
┌─────────────────────────────────────────────────────────────────┐
│                        前端 (UmiJS + Ant Design)                │
│                     http://localhost:8001                        │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API层 (FastAPI)                            │
│                     http://localhost:8000                        │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐  │
│  │ health  │ │  auth   │ │popularity│ │analysis │ │  chat   │  │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘  │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐  │
│  │strategies│ │backtest │ │sim_trade│ │pending  │ │ market  │  │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    应用服务层 (Application)                      │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐   │
│  │popularity_service│ │market_data_svc  │ │analysis_service │   │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘   │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐   │
│  │pipeline_service │ │  auth_service   │ │  chat_service   │   │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      领域层 (Domain)                             │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐   │
│  │ analysis_rules  │ │  stock_utils    │ │strategy_interface│   │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘   │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐   │
│  │  indicators     │ │ risk_manager    │ │ backtest_rules  │   │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘   │
│  ┌─────────────────┐ ┌─────────────────┐                       │
│  │trading_calendar │ │ pending_order   │                       │
│  └─────────────────┘ └─────────────────┘                       │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                  基础设施层 (Infrastructure)                     │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐   │
│  │  akshare_provider│ │eastmoney_provider│ │  sina_provider  │   │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘   │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐   │
│  │tencent_provider │ │  ths_provider   │ │mootdx_provider  │   │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘   │
│  ┌─────────────────┐ ┌─────────────────┐                       │
│  │market_data_hub  │ │  stock_code     │                       │
│  └─────────────────┘ └─────────────────┘                       │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    数据访问层 (CRUD)                              │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐   │
│  │   auth_crud     │ │  quant_crud     │ │   v2_crud       │   │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    数据库层 (PostgreSQL)                         │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐   │
│  │   v2_models     │ │  quant_models   │ │    Base         │   │
│  │  (9个表)        │ │  (15个表)       │ │                 │   │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 目录结构
```
stock/
├── src/stock_service/          # 核心业务代码
│   ├── api/                    # HTTP API层
│   │   ├── app.py              # FastAPI应用入口
│   │   ├── dependencies.py     # 依赖注入
│   │   ├── auth_cookies.py     # Cookie认证
│   │   └── routes/             # 路由模块
│   │       ├── health.py       # 健康检查
│   │       ├── auth.py         # 认证
│   │       ├── popularity.py   # 人气榜
│   │       ├── analysis.py     # 分析
│   │       ├── query.py        # 查询
│   │       └── chat.py         # AI聊天
│   ├── application/            # 应用服务层
│   │   └── services/
│   │       ├── popularity_service.py
│   │       ├── market_data_service.py
│   │       ├── analysis_service.py
│   │       ├── pipeline_service.py
│   │       ├── auth_service.py
│   │       └── chat_service.py
│   ├── domain/                 # 领域层
│   │   └── services/
│   │       ├── analysis_rules.py
│   │       └── stock_utils.py
│   ├── infrastructure/         # 基础设施层
│   │   ├── config/
│   │   │   └── settings.py
│   │   └── providers/
│   │       ├── akshare_provider.py
│   │       ├── eastmoney_provider.py
│   │       ├── sina_provider.py
│   │       ├── tencent_provider.py
│   │       ├── ths_provider.py
│   │       ├── mootdx_provider.py
│   │       ├── market_data_hub.py
│   │       └── stock_code.py
│   ├── crud/                   # 数据访问层
│   │   ├── auth_crud.py
│   │   ├── quant_crud.py
│   │   ├── v2_crud.py
│   │   └── utils.py
│   ├── db/                     # 数据库模型
│   │   └── models/
│   │       ├── __init__.py
│   │       ├── v2_models.py
│   │       └── quant_models.py
│   ├── quant/                  # 量化交易模块
│   │   ├── api/routes/         # 量化API
│   │   ├── application/        # 量化应用服务
│   │   ├── domain/             # 量化领域层
│   │   ├── infrastructure/     # 量化基础设施
│   │   ├── schemas.py
│   │   └── tasks.py
│   ├── schemas/                # 数据模型定义
│   │   └── responses.py
│   ├── main.py                 # 命令行入口
│   ├── scheduler.py            # 定时任务调度器
│   └── celery_app.py           # Celery配置
├── web-ui/                     # 前端项目
├── tests/                      # 单元测试
├── docs/                       # 项目文档
├── schema_v2.sql               # 主数据库 schema
├── schema_quant_v1.sql         # 量化数据库 schema
├── docker-compose.yml          # Docker 配置
├── ecosystem.config.js         # PM2 配置
├── pyproject.toml              # Python 依赖配置
├── alembic.ini                 # Alembic配置
├── start.sh / stop.sh          # 启停脚本
└── README.md                   # 项目说明
```

---

## 技术栈

### 后端
| 技术 | 版本 | 用途 |
|------|------|------|
| Python | 3.12+ | 主要编程语言 |
| FastAPI | 0.136.1+ | Web框架 |
| SQLAlchemy | 2.0+ (async) | ORM框架 |
| PostgreSQL | 16 | 关系型数据库 |
| Alembic | 1.13.0+ | 数据库迁移 |
| Celery | 5.4+ | 异步任务队列 |
| Redis | 5.0+ | 消息队列/缓存 |
| Uvicorn | 0.46.0+ | ASGI服务器 |
| pandas | 2.2.3+ | 数据处理 |
| numpy | - | 数值计算 |

### 数据源
| 数据源 | 库 | 用途 | 优先级 |
|--------|-----|------|--------|
| 同花顺 | pywencai | 人气榜数据 | 主数据源 |
| 东方财富 | akshare | 行情数据 | 备用 |
| 新浪财经 | mootdx | 日线数据 | 备用 |
| 腾讯财经 | tencent_provider | 实时行情 | 主数据源 |
| 通达信 | mootdx | 行情数据 | 备用 |

### 前端
| 技术 | 版本 | 用途 |
|------|------|------|
| UmiJS | 4 | 前端框架 |
| Ant Design | 6 | UI组件库 |
| TypeScript | - | 类型安全 |

### 部署
| 工具 | 用途 |
|------|------|
| Docker | 容器化部署 |
| PM2 | 进程管理 |
| Nginx | 前端静态文件托管 |

---

## 文件详情

### 配置文件

#### `/pyproject.toml`
**用途**: Python项目依赖和构建配置
**关键配置**:
```toml
[project]
name = "stock"
version = "0.1.0"
description = "A股人气榜股票数据采集、行情分析、新闻情绪分析平台"
requires-python = ">=3.12"

[project.scripts]
stock-main = "stock_service.main:main"

[tool.setuptools]
package-dir = {"" = "src"}
```

**核心依赖**:
- `fastapi>=0.136.1`: Web框架
- `sqlalchemy[asyncio]>=2.0.0`: ORM
- `asyncpg>=0.31.0`: PostgreSQL异步驱动
- `akshare>=1.18.59`: 东方财富数据
- `pywencai>=0.13.1`: 同花顺数据
- `celery[redis]>=5.4`: 异步任务
- `vectorbt>=1.0.0`: 量化回测
- `plotly>=5.0`: 图表
- `numba>=0.58`: 性能优化

#### `/docker-compose.yml`
**用途**: Docker容器编排配置
**服务**:
```yaml
services:
  postgres:           # PostgreSQL 16数据库
    image: postgres:16-alpine
    ports: "55443:5432"
    
  stock-api:          # API服务
    build: Dockerfile.api
    ports: "8000:8000"
    depends_on: postgres, agent-stock
    
  stock-scheduler:    # 定时任务调度器
    build: Dockerfile.api
    command: ["python", "-m", "stock_service.scheduler"]
    
  stock-web:          # 前端服务
    build: Dockerfile.web
    ports: "8001:8001"
```

#### `/ecosystem.config.js`
**用途**: PM2进程管理配置
**进程**:
```javascript
apps: [
  {
    name: "stock-api",
    script: "uvicorn stock_service.api.app:app --host 0.0.0.0 --port 8000",
    autorestart: true,
    max_restarts: 15,
  },
  {
    name: "stock-scheduler",
    script: "python -m stock_service.scheduler",
    autorestart: true,
    max_restarts: 100,
  }
]
```

#### `/.env.example`
**用途**: 环境变量模板
**关键配置**:
```bash
# 数据库
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=stock_db
DB_USER=postgresql
DB_PASSWORD=your_password
DB_SSL=disable

# JWT
JWT_SECRET_KEY=change-me-in-production
JWT_ACCESS_EXPIRE_MINUTES=30
JWT_REFRESH_EXPIRE_DAYS=7

# Agent Stock AI服务
AGENT_STOCK_URL=http://localhost:9002

# Redis
REDIS_URL=redis://localhost:6379/0
```

#### `/alembic.ini`
**用途**: Alembic数据库迁移配置
**关键配置**:
```ini
[alembic]
script_location = alembic
sqlalchemy.url = postgresql+asyncpg://postgresql:password@localhost:5432/stock_db
```

### 脚本文件

#### `/start.sh`
**用途**: 服务启动脚本
**功能**:
1. 检查pm2和python3是否安装
2. 同步Python依赖（uv sync）
3. 清理端口占用
4. 启动PM2进程（stock-api, stock-scheduler）
5. 等待服务就绪（最多30秒）
6. 输出服务访问地址

**使用方法**:
```bash
# 生产模式
./start.sh

# 开发模式
./start.sh dev
```

#### `/stop.sh`
**用途**: 服务停止脚本
**功能**: 停止PM2进程

#### `/build-frontend.sh`
**用途**: 前端构建脚本

### 数据库模型

#### `/src/stock_service/db/models/__init__.py`
**用途**: SQLAlchemy Base 定义
```python
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass
```

#### `/src/stock_service/db/models/v2_models.py`
**用途**: 主业务数据模型（9个表）

**数据表详情**:

| 表名 | 说明 | 关键字段 |
|------|------|----------|
| `pipeline_run` | 数据采集流水线运行记录 | run_type, status, stock_count, news_count |
| `stock_master` | 股票基础信息 | stock_code(PK), stock_name, market, industry, is_st |
| `popularity_snapshot` | 人气榜快照 | trade_date, stock_code, popularity_rank, is_new_entry |
| `news_article` | 新闻文章 | stock_code, title, content, source, published_at |
| `market_snapshot` | 市场行情快照 | stock_code, latest_price, pct_change, volume, main_net_inflow |
| `news_analysis` | 新闻分析结果 | article_id, event_type, event_label, sentiment_score |
| `stock_analysis_snapshot` | 股票综合分析快照 | stock_code, text_score, market_score, integrated_score |
| `users` | 用户表 | username, password_hash |
| `refresh_tokens` | 刷新令牌表 | user_id, token_hash, expires_at |

**表关系**:
```
pipeline_run (1) ──< (N) popularity_snapshot
pipeline_run (1) ──< (N) news_article
pipeline_run (1) ──< (N) market_snapshot
pipeline_run (1) ──< (N) news_analysis
pipeline_run (1) ──< (N) stock_analysis_snapshot
news_article (1) ──< (N) news_analysis
users (1) ──< (N) refresh_tokens
```

#### `/src/stock_service/db/models/quant_models.py`
**用途**: 量化交易数据模型（15个表）

**数据表详情**:

| 表名 | 说明 | 关键字段 |
|------|------|----------|
| `stock_basic` | 量化基础股票表 | code, name, market, industry |
| `stock_daily` | 日线行情数据 | code, trade_date, open, high, low, close, volume |
| `stock_indicator` | 技术指标 | code, trade_date, ma5, ma20, rsi, macd, boll_upper, boll_lower, atr |
| `strategy_pick` | 策略选股记录 | strategy_id, trade_date, code, score, reason |
| `backtest_result` | 回测结果 | strategy_id, total_return, annual_return, max_drawdown, sharpe, sortino |
| `backtest_trade` | 回测交易记录 | backtest_id, code, side, price, quantity, pnl |
| `backtest_daily_nav` | 回测每日净值 | backtest_id, trade_date, nav, total_assets, cash |
| `backtest_task` | 回测任务管理 | celery_task_id, task_type, status, params, progress |
| `trade_order` | 交易订单 | account_id, code, side, price, quantity, status |
| `position_account` | 持仓账户 | account_id, code, quantity, avg_price, available_quantity |
| `strategy` | 策略配置 | name, type, params(JSONB), is_active |
| `sim_account` | 模拟账户 | user_id, account_name, initial_capital, current_capital, strategy_ids(JSONB) |
| `position_daily_snapshot` | 每日持仓快照 | account_id, code, trade_date, quantity, market_value, pnl |
| `feedback_log` | 反馈日志 | backtest_id, strategy_id, before_params, after_params |
| `pending_order` | 挂单 | account_id, code, side, target_price, quantity, status |

**表关系**:
```
strategy (1) ──< (N) strategy_pick
strategy (1) ──< (N) backtest_result
backtest_result (1) ──< (N) backtest_trade
backtest_result (1) ──< (N) backtest_daily_nav
backtest_result (1) ──< (N) feedback_log
backtest_task (1) ──< (N) backtest_result
sim_account (1) ──< (N) position_account
sim_account (1) ──< (N) trade_order
sim_account (1) ──< (N) pending_order
sim_account (1) ──< (N) position_daily_snapshot
```

### API路由

#### `/src/stock_service/api/app.py`
**用途**: FastAPI应用入口
**功能**:
- 配置CORS中间件（支持多域名）
- 注册所有路由模块
- 全局异常处理（HTTPException + 通用异常）
- 统一响应格式

**路由注册**:
```python
app.include_router(health_router)           # /api/health
app.include_router(auth_router)             # /api/auth/*
app.include_router(popularity_router)       # /api/popularity/*
app.include_router(analysis_router)         # /api/analysis/*
app.include_router(query_router)            # /api/stocks, /api/news/*, /api/market/*
app.include_router(strategies.router)       # /api/quant/strategies/*
app.include_router(backtest.router)         # /api/quant/backtest/*
app.include_router(sim_trading.router)      # /api/quant/sim/*
app.include_router(feedback.router)         # /api/quant/feedback/*
app.include_router(pending_orders.router)   # /api/quant/pending-orders/*
app.include_router(market.router)           # /api/quant/market/*
app.include_router(optimizer.router)        # /api/quant/optimizer/*
app.include_router(task.router)             # /api/quant/tasks/*
app.include_router(chat_router)             # /api/chat/*
```

#### `/src/stock_service/api/routes/health.py`
**用途**: 健康检查接口
**接口**:
- `GET /api/health`: 返回服务状态
  ```json
  {
    "status": "ok",
    "service": "stock-api",
    "version": "0.1.0"
  }
  ```

#### `/src/stock_service/api/routes/auth.py`
**用途**: 用户认证接口
**接口**:
- `POST /api/auth/register`: 用户注册
  ```json
  // 请求
  {
    "username": "testuser",
    "password": "password123"
  }
  // 响应
  {
    "code": 0,
    "msg": "注册成功",
    "data": {"user_id": 1}
  }
  ```

- `POST /api/auth/login`: 用户登录
  ```json
  // 请求
  {
    "username": "testuser",
    "password": "password123"
  }
  // 响应
  {
    "code": 0,
    "msg": "登录成功",
    "data": {
      "access_token": "eyJ...",
      "token_type": "bearer"
    }
  }
  ```

- `POST /api/auth/refresh`: 刷新令牌
- `GET /api/auth/me`: 获取当前用户信息

#### `/src/stock_service/api/routes/popularity.py`
**用途**: 人气榜数据接口
**接口**:
- `POST /api/popularity/fetch`: 手动采集人气榜
- `GET /api/popularity/latest`: 获取最新人气榜
  ```json
  // 响应
  {
    "code": 0,
    "data": {
      "trade_date": "2026-06-15",
      "stocks": [
        {
          "stock_code": "000001.SZ",
          "stock_name": "平安银行",
          "popularity_rank": 1,
          "popularity_score": 99.99,
          "latest_price": 12.50,
          "pct_change": 2.35,
          "is_new_entry": false
        }
      ]
    }
  }
  ```

- `GET /api/popularity/history/{stock_code}`: 获取人气榜历史

#### `/src/stock_service/api/routes/analysis.py`
**用途**: 股票分析接口
**接口**:
- `POST /api/analyze`: 运行分析
- `GET /api/analysis`: 获取分析结果列表
- `GET /api/analysis/{stock_code}`: 获取指定股票分析结果
  ```json
  // 响应
  {
    "code": 0,
    "data": {
      "stock_code": "000001.SZ",
      "stock_name": "平安银行",
      "text_event_label": "利好",
      "text_score": 0.75,
      "behavior_label": "放量上涨",
      "market_score": 0.65,
      "integrated_score": 0.705,
      "decision": "建议关注"
    }
  }
  ```

#### `/src/stock_service/api/routes/query.py`
**用途**: 数据查询接口
**接口**:
- `GET /api/stocks`: 获取股票列表
- `GET /api/news/{stock_code}`: 获取股票新闻
- `GET /api/market/{stock_code}`: 获取市场行情

#### `/src/stock_service/api/routes/chat.py`
**用途**: AI聊天接口
**接口**:
- `POST /api/chat/stream`: SSE流式聊天

### 量化交易模块

#### `/src/stock_service/quant/domain/strategy_interface.py`
**用途**: 策略接口定义
**数据结构**:
```python
class SignalType(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"

class Signal(BaseModel):
    code: str              # 股票代码
    signal_type: SignalType # 信号类型
    score: float           # 信号强度 (0-1)
    reason: str            # 信号原因

class StrategyInterface(ABC):
    @abstractmethod
    async def generate_signals(
        self, stock_codes: List[str], context: StrategyContext
    ) -> List[Signal]:
        pass
```

#### `/src/stock_service/quant/domain/indicators.py`
**用途**: 技术指标计算
**指标详情**:
| 指标 | 计算方法 | 用途 |
|------|----------|------|
| MA5 | 5日移动平均线 | 短期趋势 |
| MA20 | 20日移动平均线 | 中期趋势 |
| RSI | 14日相对强弱指标 | 超买超卖 |
| MACD | 12/26/9日指数平滑 | 趋势判断 |
| BOLL | 20日布林带 | 波动区间 |
| ATR | 14日真实波幅 | 波动率 |

#### `/src/stock_service/quant/domain/risk_manager.py`
**用途**: 风险管理
**功能**:
- 止损检查: 当前价格 < 买入价 × (1 - 止损比例)
- 止盈检查: 当前价格 > 买入价 × (1 + 止盈比例)
- 最大回撤限制: 当前回撤 > 最大回撤限制
- 移动止损: 从最高点回撤超过阈值

#### `/src/stock_service/quant/domain/backtest_rules.py`
**用途**: 回测规则
**配置项**:
```python
class BacktestConfig(BaseModel):
    initial_capital: float = 1000000      # 初始资金
    commission_rate: float = 0.0003       # 佣金费率
    stamp_tax_rate: float = 0.001         # 印花税率（卖出）
    slippage: float = 0.001               # 滑点
    stop_loss_pct: float = -0.08          # 止损比例
    take_profit_pct: float = 0.20         # 止盈比例
    trailing_stop_pct: float = 0.05       # 移动止损比例
    max_drawdown_pct: float = -0.20       # 最大回撤限制
```

#### `/src/stock_service/quant/domain/trading_calendar.py`
**用途**: 交易日历
**功能**:
```python
def is_trading_day() -> bool:
    """检查今天是否是交易日（周一到周五）"""
    return datetime.now().weekday() < 5

def is_trading_time() -> tuple[bool, str]:
    """检查当前是否在交易时间内"""
    # 上午盘：9:30 - 11:30
    # 下午盘：13:00 - 15:00
```

#### `/src/stock_service/quant/domain/pending_order.py`
**用途**: 挂单管理
**功能**:
```python
def should_fill_order(order: dict, current_price: float) -> bool:
    """判断挂单是否成交"""
    if order["side"] == "buy":
        return current_price <= order["target_price"]
    else:
        return current_price >= order["target_price"]
```

#### `/src/stock_service/quant/domain/market_regime.py`
**用途**: 市场状态识别
**功能**: 识别牛/熊/震荡市

#### `/src/stock_service/quant/application/strategy_engine.py`
**用途**: 策略引擎
**功能**:
```python
class StrategyEngine:
    def __init__(self):
        self._strategies: Dict[str, StrategyInterface] = {}
    
    def register(self, name: str, strategy: StrategyInterface):
        """注册策略"""
        self._strategies[name] = strategy
    
    async def generate_signals(
        self, stock_codes: List[str], context: StrategyContext
    ) -> List[Signal]:
        """生成交易信号"""
        all_signals = []
        for strategy in self._strategies.values():
            signals = await strategy.generate_signals(stock_codes, context)
            all_signals.extend(signals)
        return all_signals
```

#### `/src/stock_service/quant/application/backtest_engine.py`
**用途**: 回测引擎
**功能**:
- 加载历史数据
- 模拟交易执行
- 计算绩效指标（收益率、夏普比率、最大回撤等）
- 生成回测报告

#### `/src/stock_service/quant/application/sim_trading_engine.py`
**用途**: 模拟交易引擎
**功能**:
```python
class SimTradingEngine:
    async def buy(self, account_id: int, code: str, quantity: int, price: float):
        """买入"""
        # 1. 检查资金是否充足
        # 2. 计算佣金
        # 3. 扣减资金
        # 4. 增加持仓
        # 5. 记录交易
    
    async def sell(self, account_id: int, code: str, quantity: int, price: float):
        """卖出"""
        # 1. 检查持仓是否充足
        # 2. 检查是否T+1
        # 3. 计算佣金和印花税
        # 4. 增加资金
        # 5. 减少持仓
        # 6. 记录交易
    
    async def daily_settlement(self, account_id: int, trade_date: date):
        """每日结算"""
        # 1. T+1解锁
        # 2. 更新持仓市值
        # 3. 检查止损/止盈
        # 4. 检查最大回撤
        # 5. 生成每日快照
```

#### `/src/stock_service/quant/application/optimizer.py`
**用途**: 参数优化器
**功能**:
```python
class GridSearchOptimizer:
    async def optimize(
        self,
        strategy_type: str,
        param_grid: Dict[str, List],
        backtest_config: BacktestConfig
    ) -> List[Dict]:
        """网格搜索最优参数"""
        results = []
        for params in itertools.product(*param_grid.values()):
            param_dict = dict(zip(param_grid.keys(), params))
            result = await self._run_backtest(strategy_type, param_dict, backtest_config)
            results.append(result)
        return sorted(results, key=lambda x: x["sharpe"], reverse=True)
```

#### `/src/stock_service/quant/application/feedback_service.py`
**用途**: 反馈服务
**功能**:
- 根据回测结果调整策略权重
- 记录反馈日志

#### `/src/stock_service/quant/application/vectorbt_engine.py`
**用途**: VectorBT引擎集成
**功能**:
- 使用VectorBT进行高性能回测

#### `/src/stock_service/quant/infrastructure/data_provider.py`
**用途**: 量化数据提供者
**功能**:
```python
class QuantDataProvider:
    async def get_stock_daily(
        self, code: str, start_date: date, end_date: date
    ) -> pd.DataFrame:
        """获取日线数据"""
    
    async def get_stock_indicator(
        self, code: str, trade_date: date
    ) -> Dict:
        """获取技术指标"""
```

#### `/src/stock_service/quant/infrastructure/analysis_adapter.py`
**用途**: 分析适配器
**功能**:
```python
class AnalysisAdapter:
    async def get_analysis_signals(
        self, stock_codes: List[str]
    ) -> Dict[str, Dict]:
        """获取分析信号"""
```

#### `/src/stock_service/quant/schemas.py`
**用途**: 量化模块数据模型

#### `/src/stock_service/quant/tasks.py`
**用途**: Celery异步任务
**任务**:
- `run_backtest`: 运行回测
- `run_optimization`: 运行参数优化

### 量化API路由

#### `/src/stock_service/quant/api/routes/strategies.py`
**用途**: 策略管理接口
**接口**:
- `GET /api/quant/strategies`: 获取策略列表
- `POST /api/quant/strategies`: 创建策略
  ```json
  // 请求
  {
    "name": "人气榜策略",
    "type": "popularity",
    "params": {
      "new_entry_threshold": 50,
      "rank_drop_threshold": 30
    },
    "description": "基于人气榜变化的交易策略"
  }
  ```
- `PUT /api/quant/strategies/{id}`: 更新策略
- `DELETE /api/quant/strategies/{id}`: 删除策略

#### `/src/stock_service/quant/api/routes/backtest.py`
**用途**: 回测接口
**接口**:
- `POST /api/quant/backtest/run`: 运行回测
  ```json
  // 请求
  {
    "strategy_id": 1,
    "start_date": "2025-01-01",
    "end_date": "2026-06-15",
    "initial_capital": 1000000,
    "commission_rate": 0.0003
  }
  // 响应
  {
    "code": 0,
    "data": {
      "backtest_id": 1,
      "status": "running",
      "task_id": "abc123"
    }
  }
  ```

- `GET /api/quant/backtest/results`: 获取回测结果
- `GET /api/quant/backtest/{id}`: 获取回测详情

#### `/src/stock_service/quant/api/routes/sim_trading.py`
**用途**: 模拟交易接口
**接口**:
- `GET /api/quant/sim/accounts`: 获取模拟账户列表
- `POST /api/quant/sim/accounts`: 创建模拟账户
  ```json
  // 请求
  {
    "account_name": "我的模拟账户",
    "initial_capital": 1000000,
    "strategy_ids": [1, 2],
    "config": {
      "stop_loss_pct": -0.08,
      "take_profit_pct": 0.20,
      "max_position_pct": 0.2
    }
  }
  ```

- `POST /api/quant/sim/trade`: 下单
  ```json
  // 请求
  {
    "account_id": 1,
    "code": "000001.SZ",
    "side": "buy",
    "quantity": 1000,
    "price": 12.50
  }
  ```

- `POST /api/quant/sim/settlement`: 每日结算

#### `/src/stock_service/quant/api/routes/pending_orders.py`
**用途**: 挂单接口
**接口**:
- `GET /api/quant/pending-orders`: 获取挂单列表
- `POST /api/quant/pending-orders`: 创建挂单
- `DELETE /api/quant/pending-orders/{id}`: 取消挂单

#### `/src/stock_service/quant/api/routes/market.py`
**用途**: 行情接口
**接口**:
- `GET /api/quant/market/prices`: 获取实时行情
  ```json
  // 请求
  ?codes=000001.SZ,600036.SH
  // 响应
  {
    "code": 0,
    "data": {
      "000001.SZ": {
        "price": 12.50,
        "change": 0.29,
        "change_pct": 2.35,
        "volume": 1234567
      }
    }
  }
  ```

- `GET /api/quant/market/kline`: 获取K线数据

#### `/src/stock_service/quant/api/routes/optimizer.py`
**用途**: 参数优化接口
**接口**:
- `POST /api/quant/optimizer/grid-search`: 网格搜索优化
  ```json
  // 请求
  {
    "strategy_type": "technical",
    "param_grid": {
      "ma_short": [5, 10, 20],
      "ma_long": [20, 30, 60],
      "rsi_threshold": [30, 40, 50]
    },
    "start_date": "2025-01-01",
    "end_date": "2026-06-15"
  }
  ```

#### `/src/stock_service/quant/api/routes/feedback.py`
**用途**: 反馈接口
**接口**:
- `GET /api/quant/feedback`: 获取反馈日志
- `POST /api/quant/feedback/apply`: 应用反馈优化

#### `/src/stock_service/quant/api/routes/task.py`
**用途**: 任务管理接口
**接口**:
- `GET /api/quant/tasks`: 获取任务列表
- `GET /api/quant/tasks/{id}`: 获取任务详情

### 基础设施层

#### `/src/stock_service/infrastructure/config/settings.py`
**用途**: 应用配置管理
**配置项详情**:
```python
class Settings:
    # 数据库配置
    db_host: str          # 数据库主机
    db_port: int          # 数据库端口
    db_name: str          # 数据库名
    db_user: str          # 数据库用户
    db_password: str      # 数据库密码
    db_ssl: bool          # SSL连接
    
    # JWT配置
    jwt_secret_key: str   # JWT密钥
    jwt_access_expire_minutes: int  # Access Token过期时间
    jwt_refresh_expire_days: int    # Refresh Token过期时间
    
    # 数据源配置
    ths_query: str        # 同花顺查询语句
    ths_cookie: str       # 同花顺Cookie
    
    # 行情数据源
    market_quote_providers: tuple   # 行情数据源优先级
    market_fetch_concurrency: int   # 并发数
    
    # Redis
    redis_url: str        # Redis连接地址
    
    # Agent Stock AI
    agent_stock_url: str  # AI服务地址
```

#### `/src/stock_service/infrastructure/providers/akshare_provider.py`
**用途**: 东方财富数据提供者（akshare库）
**功能**:
- 获取股票列表
- 获取历史行情
- 获取资金流向

#### `/src/stock_service/infrastructure/providers/eastmoney_provider.py`
**用途**: 东方财富数据提供者
**功能**:
- 获取实时行情
- 获取K线数据

#### `/src/stock_service/infrastructure/providers/sina_provider.py`
**用途**: 新浪财经数据提供者
**功能**:
- 获取实时行情
- 获取日线数据

#### `/src/stock_service/infrastructure/providers/tencent_provider.py`
**用途**: 腾讯财经数据提供者
**功能**:
```python
def fetch_realtime_price(stock_code: str) -> float:
    """获取实时行情"""
    # 调用腾讯财经API

def fetch_kline_tx(stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """获取K线数据"""
    # 调用腾讯财经API
```

#### `/src/stock_service/infrastructure/providers/ths_provider.py`
**用途**: 同花顺数据提供者
**功能**:
```python
async def fetch_popularity() -> List[Dict]:
    """获取人气榜数据"""
    # 使用pywencai库
    # 查询语句: 人气排名前200
```

#### `/src/stock_service/infrastructure/providers/mootdx_provider.py`
**用途**: 通达信数据提供者
**功能**:
- 获取行情数据

#### `/src/stock_service/infrastructure/providers/market_data_hub.py`
**用途**: 行情数据聚合器
**功能**:
```python
class MarketDataHub:
    def __init__(self, providers: List[str]):
        self.providers = providers
    
    async def get_realtime_price(self, stock_code: str) -> float:
        """获取实时行情（多数据源聚合）"""
        for provider in self.providers:
            try:
                return await provider.get_price(stock_code)
            except Exception:
                continue
        raise Exception("所有数据源都失败")
```

#### `/src/stock_service/infrastructure/providers/stock_code.py`
**用途**: 股票代码工具
**功能**:
```python
def normalize_code(code: str) -> str:
    """标准化股票代码"""
    # 000001 -> 000001.SZ
    # 600036 -> 600036.SH

def get_market(code: str) -> str:
    """获取股票市场"""
    # 000001.SZ -> SZ
    # 600036.SH -> SH
```

### 数据访问层

#### `/src/stock_service/crud/__init__.py`
**用途**: CRUD模块初始化

#### `/src/stock_service/crud/auth_crud.py`
**用途**: 认证相关CRUD
**功能**:
```python
async def create_user(session, username: str, password_hash: str) -> int:
    """创建用户"""

async def get_user_by_username(session, username: str) -> Dict:
    """根据用户名查询用户"""

async def create_refresh_token(session, user_id: int, token_hash: str, expires_at: datetime):
    """创建刷新令牌"""

async def get_refresh_token(session, token_hash: str) -> Dict:
    """查询刷新令牌"""
```

#### `/src/stock_service/crud/quant_crud.py`
**用途**: 量化交易CRUD
**功能**:
```python
# 策略管理
async def create_strategy(session, data: Dict) -> int:
async def list_strategies(session) -> List[Dict]:
async def update_strategy(session, strategy_id: int, data: Dict):
async def delete_strategy(session, strategy_id: int):

# 回测数据
async def create_backtest_result(session, data: Dict) -> int:
async def list_backtest_results(session, strategy_id: int) -> List[Dict]:

# 模拟账户
async def create_sim_account(session, data: Dict) -> int:
async def list_sim_accounts(session, user_id: int) -> List[Dict]:
async def get_sim_account(session, account_id: int) -> Dict:

# 持仓管理
async def get_positions(session, account_id: int) -> List[Dict]:
async def get_position(session, account_id: int, code: str) -> Dict:
async def update_position(session, account_id: int, code: str, data: Dict):

# 挂单管理
async def create_pending_order(session, data: Dict) -> int:
async def list_all_pending_orders(session) -> List[Dict]:
async def update_pending_order(session, order_id: int, data: Dict):
async def cancel_all_pending_orders(session, account_id: int) -> int:
```

#### `/src/stock_service/crud/v2_crud.py`
**用途**: 主业务CRUD
**功能**:
```python
# 人气榜数据
async def insert_popularity_snapshot(session, data: Dict):
async def get_latest_popularity(session) -> List[Dict]:

# 新闻数据
async def insert_news_article(session, data: Dict):
async def get_news_by_stock(session, stock_code: str) -> List[Dict]:

# 行情数据
async def insert_market_snapshot(session, data: Dict):

# 分析数据
async def insert_stock_analysis(session, data: Dict):
async def get_analysis_by_stock(session, stock_code: str) -> Dict:
```

#### `/src/stock_service/crud/utils.py`
**用途**: CRUD工具函数

### 应用服务层

#### `/src/stock_service/application/services/popularity_service.py`
**用途**: 人气榜服务
**功能**:
```python
async def run_popularity_pipeline(session) -> Dict:
    """执行人气榜采集流水线"""
    # 1. 从同花顺获取最新数据
    # 2. 对比新旧数据
    # 3. 检测新增股票
    # 4. 存储快照
    # 5. 返回结果
```

#### `/src/stock_service/application/services/market_data_service.py`
**用途**: 行情数据服务
**功能**:
```python
async def run_fetch_pipeline_for_rows(session, rows: List[Dict], run_type: str, source: str):
    """执行数据采集流水线"""
    # 1. 获取新闻数据
    # 2. 获取行情数据
    # 3. 存储到数据库

async def compute_and_store_indicators(session) -> int:
    """计算并存储技术指标"""
    # 1. 获取日线数据
    # 2. 计算MA/RSI/MACD/BOLL/ATR
    # 3. 存储到数据库
```

#### `/src/stock_service/application/services/analysis_service.py`
**用途**: 分析服务
**功能**:
```python
async def run_and_store(session, stock_codes: List[str]):
    """运行分析并存储结果"""
    # 1. 获取新闻分析
    # 2. 获取市场行为分析
    # 3. 计算综合评分
    # 4. 存储分析结果
```

#### `/src/stock_service/application/services/pipeline_service.py`
**用途**: 流水线服务
**功能**:
- 编排采集/分析流程

#### `/src/stock_service/application/services/auth_service.py`
**用途**: 认证服务
**功能**:
```python
async def register(username: str, password: str) -> int:
    """用户注册"""
    # 1. 检查用户名是否已存在
    # 2. 密码加密
    # 3. 创建用户

async def login(username: str, password: str) -> Dict:
    """用户登录"""
    # 1. 验证用户名密码
    # 2. 生成JWT Token
    # 3. 返回Token

async def refresh_token(token: str) -> Dict:
    """刷新Token"""
    # 1. 验证Refresh Token
    # 2. 生成新的Access Token
```

#### `/src/stock_service/application/services/chat_service.py`
**用途**: 聊天服务
**功能**:
- 调用Agent Stock AI服务

### 领域层

#### `/src/stock_service/domain/services/analysis_rules.py`
**用途**: 分析规则
**功能**:
```python
class AnalysisRules:
    # 事件类型
    EVENT_TYPES = {
        "业绩利好": ["业绩增长", "净利润增长", "营收增长"],
        "业绩利空": ["业绩下滑", "净利润下降", "亏损"],
        "政策利好": ["政策支持", "补贴", "减税"],
        "政策利空": ["监管收紧", "罚款", "限制"],
        "资金流入": ["主力净流入", "大单买入"],
        "资金流出": ["主力净流出", "大单卖出"],
    }
    
    # 正负面词
    POSITIVE_WORDS = ["增长", "上涨", "突破", "利好", "强势"]
    NEGATIVE_WORDS = ["下跌", "下滑", "跌破", "利空", "弱势"]
    
    def analyze_sentiment(self, text: str) -> Dict:
        """分析文本情绪"""
```

#### `/src/stock_service/domain/services/stock_utils.py`
**用途**: 股票工具函数

### 其他文件

#### `/src/stock_service/main.py`
**用途**: 命令行入口
**功能**:
```python
async def main_async(fetch_only: bool = False):
    """主函数"""
    # 1. 采集人气榜
    # 2. 获取新增股票
    # 3. 采集新闻/行情
    # 4. 运行分析

def main():
    """命令行入口"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--fetch-only", action="store_true")
    args = parser.parse_args()
    asyncio.run(main_async(fetch_only=args.fetch_only))
```

#### `/src/stock_service/scheduler.py`
**用途**: 定时任务调度器
**触发时间**:
```python
trigger_times = [
    time(9, 25),   # 开盘前 - 采集人气榜
    time(14, 30),  # 下午盘 - 采集人气榜
    time(15, 5),   # 收盘后 - 每日结算
]

# 挂单检查: 交易时间内每60秒
```

**主要函数**:
```python
async def run_pipeline():
    """执行完整的人气榜流水线"""

async def run_daily_settlement():
    """对所有活跃模拟账户执行每日结算"""

async def check_pending_orders():
    """检查挂单是否可以成交"""

async def auto_trade_for_accounts(session, new_entries: List[Dict]):
    """对有策略的模拟账户自动执行交易"""
```

#### `/src/stock_service/celery_app.py`
**用途**: Celery应用配置

#### `/src/stock_service/schemas/__init__.py`
**用途**: 数据模型模块初始化

#### `/src/stock_service/schemas/responses.py`
**用途**: API响应模型
```python
class ApiResponse(BaseModel):
    code: int = 0
    msg: str = "success"
    data: Any = None
```

### 测试文件

#### `/tests/__init__.py`
**用途**: 测试模块初始化

#### `/tests/conftest.py`
**用途**: pytest配置
**功能**:
- 测试数据库连接
- 测试数据准备
- Fixtures定义

#### `/tests/test_auth.py`
**用途**: 认证模块测试

#### `/tests/test_popularity_service.py`
**用途**: 人气榜服务测试

#### `/tests/test_scheduler.py`
**用途**: 调度器测试

#### `/tests/test_ths_provider.py`
**用途**: 同花顺数据源测试

#### `/tests/quant/__init__.py`
**用途**: 量化测试模块初始化

#### `/tests/quant/test_backtest_engine.py`
**用途**: 回测引擎测试

#### `/tests/quant/test_backtest_rules.py`
**用途**: 回测规则测试

#### `/tests/quant/test_indicators.py`
**用途**: 技术指标测试

#### `/tests/quant/test_risk_manager.py`
**用途**: 风险管理测试

#### `/tests/quant/test_sim_trading_engine.py`
**用途**: 模拟交易引擎测试

#### `/tests/quant/test_strategy_engine.py`
**用途**: 策略引擎测试

---

### 数据库迁移

#### `/alembic/env.py`
**用途**: Alembic迁移环境配置

#### `/alembic/versions/1132df767b86_baseline_existing_schema.py`
**用途**: 初始数据库迁移

### 前端项目

#### `/web-ui/`
**用途**: 前端项目（UmiJS + Ant Design）
**构建产物**: `/web-ui/dist/`

---

## 环境变量配置

### 必需配置
```bash
# 数据库
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=stock_db
DB_USER=postgresql
DB_PASSWORD=your_password

# JWT
JWT_SECRET_KEY=change-me-in-production

# Agent Stock AI服务
AGENT_STOCK_URL=http://localhost:9002
```

### 可选配置
```bash
# 测试数据库
TEST_DB_HOST=
TEST_DB_PORT=
TEST_DB_NAME=
TEST_DB_USER=
TEST_DB_PASSWORD=

# 行情数据源
MARKET_QUOTE_PROVIDERS=tencent
MARKET_FETCH_CONCURRENCY=5
NEWS_FETCH_CONCURRENCY=5

# Redis
REDIS_URL=redis://localhost:6379/0

# 同花顺
THS_POPULARITY_QUERY=人气排名前200
THS_COOKIE=

# CORS
ALLOWED_ORIGINS=http://localhost:8001,http://101.35.255.200:8001
```

---

## 快速开始

### 环境要求
- Python 3.12+
- Node.js 18+
- PostgreSQL 14+
- Redis

### 安装
```bash
# 克隆项目
git clone <repo-url>
cd stock

# 后端依赖
python -m venv .venv
source .venv/bin/activate
pip install -e .

# 前端依赖
cd web-ui
pnpm install
cd ..
```

### 配置
```bash
# 复制环境变量
cp .env.example .env

# 编辑 .env 填写数据库和 JWT 配置
```

### 数据库初始化
```bash
psql -U postgresql -d stock_db -f schema_v2.sql
psql -U postgresql -d stock_db -f schema_quant_v1.sql
```

### 启动服务
```bash
# PM2方式（默认生产模式）
./start.sh

# PM2方式（开发模式）
./start.sh dev

# Docker方式
docker-compose up -d
```

### 访问
- 前端: http://localhost:8001
- API文档: http://localhost:8000/docs

---

## API接口列表

### 分析模块
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/popularity/fetch | 采集人气榜 |
| GET | /api/popularity/latest | 获取最新人气榜 |
| GET | /api/popularity/history/{stock_code} | 获取人气榜历史 |
| POST | /api/analyze | 运行分析 |
| GET | /api/analysis | 获取分析结果列表 |
| GET | /api/analysis/{stock_code} | 获取指定股票分析 |

### 量化模块
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/quant/strategies | 获取策略列表 |
| POST | /api/quant/strategies | 创建策略 |
| PUT | /api/quant/strategies/{id} | 更新策略 |
| DELETE | /api/quant/strategies/{id} | 删除策略 |
| POST | /api/quant/backtest/run | 运行回测 |
| GET | /api/quant/backtest/results | 获取回测结果 |
| GET | /api/quant/backtest/{id} | 获取回测详情 |
| GET | /api/quant/sim/accounts | 获取模拟账户列表 |
| POST | /api/quant/sim/accounts | 创建模拟账户 |
| POST | /api/quant/sim/trade | 下单 |
| POST | /api/quant/sim/settlement | 每日结算 |
| GET | /api/quant/pending-orders | 获取挂单列表 |
| POST | /api/quant/pending-orders | 创建挂单 |
| DELETE | /api/quant/pending-orders/{id} | 取消挂单 |
| GET | /api/quant/market/prices | 获取实时行情 |
| GET | /api/quant/market/kline | 获取K线数据 |
| POST | /api/quant/optimizer/grid-search | 参数优化 |
| GET | /api/quant/feedback | 获取反馈日志 |
| POST | /api/quant/feedback/apply | 应用反馈优化 |
| GET | /api/quant/tasks | 获取任务列表 |
| GET | /api/quant/tasks/{id} | 获取任务详情 |

### 认证模块
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/auth/register | 注册 |
| POST | /api/auth/login | 登录 |
| POST | /api/auth/refresh | 刷新令牌 |
| GET | /api/auth/me | 获取当前用户信息 |

### 其他
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/health | 健康检查 |
| POST | /api/chat/stream | AI聊天 |
| GET | /api/stocks | 获取股票列表 |
| GET | /api/news/{stock_code} | 获取股票新闻 |
| GET | /api/market/{stock_code} | 获取市场行情 |

---

## 策略说明

### 1. 人气榜策略 (popularity)
**逻辑**: 基于同花顺人气榜变化
- 新进榜 = 买入信号
- 排名大跌 = 买入信号
- 大涨 = 卖出信号

**参数**:
```json
{
  "new_entry_threshold": 50,
  "rank_drop_threshold": 30,
  "price_rise_threshold": 0.05
}
```

### 2. 情绪驱动策略 (sentiment)
**逻辑**: 基于新闻情绪+市场行为综合得分
- 综合得分 > 0.7 = 买入
- 综合得分 < 0.3 = 卖出

### 3. 技术面策略 (technical)
**逻辑**: MA/RSI/MACD 组合
- MA5上穿MA20 = 买入
- MA5下穿MA20 = 卖出
- RSI < 30 = 超卖（买入）
- RSI > 70 = 超买（卖出）

### 4. 多因子策略 (multi_factor)
**逻辑**: 以上三种加权组合
```json
{
  "popularity_weight": 0.3,
  "sentiment_weight": 0.3,
  "technical_weight": 0.4
}
```

### 5. 量价策略 (volume_price)
**逻辑**: 基于成交量和价格关系
- 放量上涨 = 买入
- 放量下跌 = 卖出

### 6. 动量策略 (momentum)
**逻辑**: 强势追涨，弱势杀跌
- 连续上涨 = 买入
- 连续下跌 = 卖出

### 7. 均值回归策略 (mean_reversion)
**逻辑**: 偏离均线过多反向操作
- 价格 < MA20 × 0.95 = 买入
- 价格 > MA20 × 1.05 = 卖出

### 8. 资金流策略 (fund_flow)
**逻辑**: 基于主力资金流向
- 主力净流入 > 阈值 = 买入
- 主力净流出 > 阈值 = 卖出

### 9. 突破策略 (breakout)
**逻辑**: 基于布林带
- 突破布林上轨 = 买入
- 跌破布林下轨 = 卖出

### 10. 网格策略 (grid)
**逻辑**: 区间震荡网格交易
- 价格触及网格下沿 = 买入
- 价格触及网格上沿 = 卖出

---

## 定时任务

| 时间 | 任务 | 说明 |
|------|------|------|
| 9:25 | 采集人气榜 + 更新日线数据 + 分析 + 自动交易 | 开盘前 |
| 14:30 | 采集人气榜 + 更新日线数据 + 分析 + 自动交易 | 下午盘 |
| 15:05 | 每日结算（T+1更新、止损检查） | 收盘后 |
| 每60秒 | 检查挂单成交 | 交易时间内 |

---

## 常用命令

```bash
# 查看PM2进程状态
pm2 status

# 查看日志
pm2 logs
pm2 logs stock-api
pm2 logs stock-scheduler

# 停止服务
./stop.sh
pm2 stop stock-api stock-scheduler

# 重启服务
pm2 restart stock-api stock-scheduler

# 运行测试
python -m pytest tests/ -v

# 运行后端（开发模式）
uvicorn stock_service.api.app:app --reload

# 运行前端（开发模式）
cd web-ui && pnpm dev

# 手动触发采集
python -m stock_service.main

# 仅采集不分析
python -m stock_service.main --fetch-only
```

---

## License

Private
