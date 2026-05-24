# A股量化交易平台

A股同花顺人气榜 Top 200 股票的数据采集、行情分析、量化交易平台。

## 功能概览

### 数据采集
- 同花顺人气榜 Top 200 自动采集（交易日 9:25 / 14:30）
- 新闻/行情/资金流数据抓取
- 日线数据自动更新（新浪数据源）
- 技术指标自动计算（MA/RSI/MACD）

### 股票分析
- 新闻情绪分析（6 种事件模式 + 正负面词统计）
- 市场行为分析（量价信号 + 资金流信号）
- 综合评分（文本分 × 0.55 + 市场分 × 0.45）

### 量化交易
- **10 种内置策略**：人气榜、情绪驱动、技术面、多因子、量价、动量、均值回归、资金流、突破、网格
- **回测系统**：含交易成本、T+1、滑点、多策略对比、沪深300基准对比
- **模拟盘**：市价单/限价单、止损止盈（固定+移动）、账户回撤限制、多策略共识
- **参数优化**：网格搜索最优策略参数
- **闭环反馈**：回测结果反向优化策略权重

### 定时任务
| 时间 | 任务 |
|------|------|
| 9:25 | 采集人气榜 + 更新日线数据 + 分析 + 自动交易 |
| 14:30 | 采集人气榜 + 更新日线数据 + 分析 + 自动交易 |
| 15:05 | 每日结算（T+1更新、止损检查） |
| 每60秒 | 检查挂单成交 |

## 技术栈

- **后端**：Python 3.12 + FastAPI + SQLAlchemy 2.0 (async) + PostgreSQL
- **前端**：UmiJS 4 + Ant Design 6 + TypeScript
- **数据源**：同花顺(pywencai)、东方财富(akshare)、新浪财经
- **部署**：PM2 / Docker

## 快速开始

### 环境要求
- Python 3.12+
- Node.js 18+
- PostgreSQL 14+

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
# PM2 方式（开发模式，默认）
./start.sh

# PM2 方式（生产模式）
WEB_MODE=prod ./start.sh

# Docker 方式
docker-compose up -d
```

### 访问

- 前端：http://localhost:8001
- API 文档：http://localhost:8000/docs

## 项目结构

```
stock/
├── src/stock_service/
│   ├── api/                    # HTTP 层
│   │   ├── app.py              # FastAPI 应用
│   │   ├── dependencies.py     # 依赖注入
│   │   └── routes/             # 路由模块
│   ├── application/services/   # 应用服务层
│   │   ├── popularity_service.py
│   │   ├── market_data_service.py
│   │   ├── analysis_service.py
│   │   └── pipeline_service.py
│   ├── domain/services/        # 领域服务层
│   │   └── analysis_rules.py
│   ├── quant/                  # 量化模块
│   │   ├── domain/             # 策略接口、规则、风控
│   │   ├── application/        # 策略引擎、回测、模拟盘
│   │   ├── infrastructure/     # 数据源适配
│   │   └── api/routes/         # 量化 API
│   ├── infrastructure/         # 基础设施层
│   │   ├── config/settings.py
│   │   └── providers/          # 外部数据源
│   └── crud/                   # 数据访问层
├── web-ui/                     # 前端项目
├── schema_v2.sql               # 主数据库 schema
├── schema_quant_v1.sql         # 量化数据库 schema
├── docker-compose.yml          # Docker 配置
├── ecosystem.config.js         # PM2 配置
└── start.sh / stop.sh          # 启停脚本
```

## API 接口

### 分析模块
- `POST /api/popularity/fetch` - 采集人气榜
- `POST /api/analyze` - 运行分析
- `GET /api/analysis` - 获取分析结果

### 量化模块
- `GET/POST /api/quant/strategies` - 策略管理
- `POST /api/quant/backtest/run` - 运行回测
- `GET /api/quant/backtest/results` - 回测结果
- `GET/POST /api/quant/sim/accounts` - 模拟账户
- `POST /api/quant/sim/trade` - 下单
- `POST /api/quant/sim/settlement` - 每日结算
- `POST /api/quant/optimizer/grid-search` - 参数优化

## 策略说明

| 策略 | 类型 | 逻辑 |
|------|------|------|
| 人气榜策略 | popularity | 新进榜=买，排名大跌=买，大涨=卖 |
| 情绪驱动策略 | sentiment | 新闻情绪+市场行为综合得分 |
| 技术面策略 | technical | MA/RSI/MACD 组合 |
| 多因子策略 | multi_factor | 以上三种加权组合 |
| 量价策略 | volume_price | 放量上涨=买，放量下跌=卖 |
| 动量策略 | momentum | 强势追涨，弱势杀跌 |
| 均值回归策略 | mean_reversion | 偏离均线过多反向操作 |
| 资金流策略 | fund_flow | 主力净流入=买，净流出=卖 |
| 突破策略 | breakout | 突破布林上轨=买，跌破下轨=卖 |
| 网格策略 | grid | 区间震荡网格交易 |

## Docker 部署

```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止
docker-compose down
```

## 开发

```bash
# 运行测试
python -m pytest tests/ -v

# 运行后端
uvicorn stock_service.api.app:app --reload

# 运行前端
cd web-ui && pnpm dev
```

## License

Private
