# 架构契约

> 本文件描述系统组件如何协作，以及新增功能时的架构约束。

---

## 项目定位

A股同花顺人气榜 Top 200 股票的数据采集、行情分析、新闻情绪分析平台。

核心流水线：**抓取人气榜 → 检测新增股票 → 抓取新闻/行情 → 规则分析 → 存储结果**

---

## 目录结构

```
src/stock_service/
├── api/                          # HTTP 层
│   ├── app.py                    # FastAPI 应用、lifespan、路由注册
│   ├── dependencies.py           # 依赖注入（get_db、lifespan）
│   └── routes/                   # 路由模块（每个文件一个 tag）
│       ├── health.py
│       ├── popularity.py         # 人气榜相关接口
│       ├── analysis.py           # 分析触发接口
│       └── query.py              # 数据查询接口
├── application/services/          # 应用服务层（编排业务流程）
│   ├── popularity_service.py     # 人气榜流水线
│   ├── market_data_service.py    # 新闻+行情抓取流水线
│   ├── analysis_service.py       # 分析流水线（run + store）
│   └── pipeline_service.py       # 全流程编排（run-all）
├── domain/services/               # 领域服务层（纯逻辑，无 IO）
│   └── analysis_rules.py         # 规则引擎、情绪分析、市场行为判定
├── infrastructure/                # 基础设施层
│   ├── config/settings.py        # 环境变量与配置
│   ├── providers/                # 外部数据源封装
│   │   ├── ths_provider.py       # 同花顺（pywencai）
│   │   └── eastmoney_provider.py # 东方财富（akshare + curl_cffi）
│   └── db/                       # 数据库层
│       ├── database.py           # StockDatabase 门面类
│       ├── database_utils.py     # 工具函数
│       └── repositories/         # 数据访问（每张表一个 Repository）
│           ├── base.py
│           ├── stock.py
│           ├── popularity.py
│           ├── news.py
│           ├── market.py
│           ├── analysis.py
│           └── pipeline.py
└── schemas/                       # Pydantic 模型
    └── responses.py              # ApiResponse 统一响应
```

---

## 分层职责与约束

| 层 | 职责 | 禁止 |
|---|---|---|
| `api/routes/` | 参数校验、调用 service、返回响应 | 写业务逻辑、直接操作数据库 |
| `application/services/` | 编排业务流程、协调多个 repository | 写纯计算逻辑（归 domain） |
| `domain/services/` | 纯函数计算，无 IO、无数据库依赖 | 导入 infrastructure 或 api 层 |
| `infrastructure/providers/` | 封装外部 API 调用 | 包含业务逻辑 |
| `infrastructure/db/repositories/` | SQL 数据访问 | 包含业务逻辑 |
| `schemas/` | 请求/响应模型定义 | 包含业务逻辑 |

依赖方向：`api → application → domain ← infrastructure`（domain 不依赖任何外层）。

---

## 数据库

- 引擎：PostgreSQL，驱动 asyncpg（不使用 ORM）
- 连接池：`asyncpg.create_pool(min_size=2, max_size=10)`
- Schema：项目根目录 `schema_v2.sql`，启动时自动执行（仅当 `stock_master` 表不存在时）
- 7 张核心表：`pipeline_run`、`stock_master`、`popularity_snapshot`、`news_article`、`market_snapshot`、`news_analysis`、`stock_analysis_snapshot`
- 2 个视图：`v_latest_market_snapshot`、`v_latest_stock_analysis`

### 新增表时的流程

1. 在 `schema_v2.sql` 中添加 `CREATE TABLE` 语句
2. 在 `infrastructure/db/repositories/` 下新建对应 Repository
3. 在 `StockDatabase` 中添加 Repository 绑定和便捷方法
4. 更新本文档的表清单

---

## 应用生命周期

```
启动 → lifespan → StockDatabase.initialize() → 创建连接池 + 自动建表
                                                      ↓
关闭 → lifespan → StockDatabase.close() → 关闭连接池
```

`get_db()` 依赖注入返回全局 `StockDatabase` 单例。

---

## 核心流水线

```
run_all_pipeline()
    ↓
run_popularity_pipeline()        # 1. 抓取同花顺人气榜 Top 200
    ↓                              对比上次榜单，识别新增股票
run_fetch_pipeline_for_rows()    # 2. 对新增股票抓取新闻 + 行情
    ↓
run_analysis()                   # 3. 规则分析（文本情绪 + 市场行为）
    ↓
store_analysis_results()         # 4. 存储分析结果
```

每一步都创建 `pipeline_run` 记录用于审计追踪。

---

## 前端

- 位置：`web-ui/`，使用 UmiJS + React + TypeScript
- 仅做数据展示，不包含业务逻辑
- 通过 `web-ui/src/utils/request.ts` 调用后端 API

---

## 新增功能时的检查清单

1. 新增路由 → 在 `api/routes/` 下新建文件，在 `app.py` 中注册
2. 新增业务逻辑 → 在 `application/services/` 下新建文件
3. 新增纯计算逻辑 → 在 `domain/services/` 下新建文件
4. 新增数据源 → 在 `infrastructure/providers/` 下新建文件
5. 新增数据库表 → 更新 `schema_v2.sql` + 新建 Repository
6. 新增配置项 → 在 `settings.py` 中添加，同步更新 `.env.example`
