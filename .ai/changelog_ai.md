# AI 决策与纠偏日志

> 记录"为什么"而非"改了什么"。当 AI 反复犯错时追加规则，当架构决策变更时记录原因。

格式：`日期 | 类型 | 规则/决策 | 原因`

---

## 2025-05-09 | 初始化 | 项目初始状态记录

- 项目采用 DDD 分层架构（api → application → domain ← infrastructure），不使用 ORM，直接 asyncpg 原生 SQL
- 分析引擎当前仅支持规则分析（`analysis_rules.py`），预留 LLM 分析扩展点（`analyzer_type` 字段支持 `rule/llm/hybrid`）
- 股票代码格式统一为 `XXXXXX.SH/SZ/BJ`，项目中存在两个 `normalize_stock_code()` 实现（`domain/services/analysis_rules.py` 和 `infrastructure/providers/eastmoney_provider.py`），功能一致但未统一，后续应收敛为一处

---

## 2025-05-10 | 决策 | 引入 SQLAlchemy 异步 ORM，逐步替换 asyncpg 原生 SQL

- **类型**：决策
- **规则/决策**：在 `src/stock_service/db/` 下新建 SQLAlchemy 异步数据库模块，与现有 `infrastructure/db/`（asyncpg 原生 SQL）并存，逐步替换
- **原因**：原生 SQL 维护成本高、缺少类型安全，SQLAlchemy ORM 可提供模型约束和查询抽象，降低后续开发复杂度
- **影响**：
  - 新增 `src/stock_service/db/database.py`（异步引擎、SessionFactory、get_async_session）
  - 依赖添加 `sqlalchemy[asyncio]>=2.0.0`
  - 复用 `settings.DATABASE_CONFIG` 构建连接串，两套模块共享配置
  - 后续新建 ORM 模型和 Repository 应放在 `db/` 下，逐步迁移 `infrastructure/db/repositories/`

## 2026-05-10 | 决策 | 创建全部 14 张表的 SQLAlchemy ORM 模型

- **类型**：决策
- **规则/决策**：在 `src/stock_service/db/models/` 下建立 SQLAlchemy 2.0 声明式模型，覆盖 `schema_v2.sql`（7 张主表）和 `schema_quant_v1.sql`（7 张量化表），表名、列类型、约束、索引严格对标现有 DDL
- **原因**：为后续逐步替换 asyncpg 原生 SQL 提供数据对象基础，模型先行、替换后行
- **影响**：
  - 新增 `src/stock_service/db/models/__init__.py`（AsyncAttrs + DeclarativeBase）
  - 新增 `src/stock_service/db/models/v2_models.py`（PipelineRun、StockMaster 等 7 模型）
  - 新增 `src/stock_service/db/models/quant_models.py`（StockBasic、StockDaily 等 7 模型）
  - `db/__init__.py` 改为惰性导入，避免模块级 env var 校验阻塞 models 子包加载
  - 模型不定义 relationship，后续按需添加；不创建新表，仅映射现有表

## 2026-05-10 | 决策 | 创建 CRUD 层，路由数据库操作迁移至 crud 模块

- **类型**：决策
- **规则/决策**：在 `src/stock_service/crud/` 下创建 CRUD 层，所有数据库表的读/写操作封装为 `async def` 函数，接受 `AsyncSession` 参数，使用 SQLAlchemy ORM 查询。路由通过 `Depends(get_session)` 注入会话后调用 CRUD 函数
- **原因**：解耦路由和数据库操作，遵循系统规则「禁止在 router 中写业务逻辑」的延伸——路由不直接写 SQL，也不直接操作 ORM session
- **影响**：
  - 新增 `src/stock_service/crud/v2_crud.py`（16 个函数，覆盖 pipeline_run、stock_master、popularity_snapshot、news_article、market_snapshot、news_analysis、stock_analysis_snapshot）
  - 新增 `src/stock_service/crud/quant_crud.py`（8 个占位函数，量化表暂未接入）
  - `api/dependencies.py` 新增 `get_session()` 依赖，产出 `AsyncSession`
  - `api/routes/query.py` 全部 4 个端点改用 CRUD
  - `api/routes/popularity.py` 2 个读端点改用 CRUD
  - `api/routes/analysis.py` 2 个端点改用 CRUD（api_run_all 和 _fetch_then_analyze 仍用 StockDatabase，待服务层迁移）
  - CRUD 返回 `list[dict]` 与现有 `ApiResponse` 兼容，后续可逐步改为 Pydantic 模型

## 2026-05-10 | 决策 | 完成 asyncpg → SQLAlchemy ORM 全量迁移，删除旧 infrastructure/db/

- **类型**：决策
- **规则/决策**：application services 层、CLI 入口（main.py）、API routes、dependencies 全部切换至 `AsyncSession` + `v2_crud`，删除 `infrastructure/db/`（asyncpg 原生 SQL 模块）
- **原因**：双轨并存造成维护负担，API 路由已先期切换，剩余服务层和 CLI 仍依赖旧 StockDatabase，统一消除技术债务
- **影响**：
  - `v2_crud.py` 补全 `insert_news_batch`、`insert_market_batch`；修正 `upsert_stocks`（推导 market/code_digits/is_st）、`get_all_news`（limit_per_stock 窗口）、`get_market_data`（DISTINCT ON per stock）
  - `popularity_service.py` / `market_data_service.py` / `analysis_service.py` / `pipeline_service.py` 所有函数从 `db: StockDatabase` 改为 `session: AsyncSession`
  - `popularity_service.run_popularity_pipeline()` 和 `market_data_service.run_fetch_pipeline_for_rows()` 不再内部创建/销毁连接，由调用方注入 session
  - `dependencies.py` 移除 `StockDatabase`、`_db` 全局单例、`get_db()`；lifespan 简化为空
  - `api/routes/analysis.py` 移除 `get_db()` 调用，`api_run_all` 改为 `Depends(get_session)`
  - `api/routes/health.py` 移除数据库探活，改为静态就绪检查
  - `main.py` CLI 改用 `AsyncSessionFactory()` 上下文管理器
  - 删除 `infrastructure/db/` 全部 9 个文件（database.py、database_utils.py、repositories/*）

---

<!-- 追加模板

## YYYY-MM-DD | 类型 | 标题

- **类型**：纠偏 / 决策 / 踩坑
- **规则/决策**：具体内容
- **原因**：为什么这么做

示例：

## 2025-05-10 | 纠偏 | async 数据库操作必须 await

- AI 生成的新 Repository 方法中遗漏了 await，导致协程未执行
- 已修正，并在 system_rules.md 中强调

## 2025-05-11 | 决策 | 从 SQLite 迁移到 PostgreSQL

- 原因：并发写入需求增加，SQLite 的写锁瓶颈无法满足
- 影响：所有 SQL 语法需检查兼容性，settings.py 连接配置已更新

-->

## 2026-05-11 用户认证模块

**为什么：** 平台需要用户系统保护 API 接口，防止未授权访问。

**做了什么：**
- 新增 users + refresh_tokens 表
- 实现注册、登录、token 刷新、登出接口
- JWT access token (30min) + refresh token (7d) 轮换机制
- 所有现有 API 加认证保护（health 除外）
- passlib+bcrypt 密码哈希，refresh token 存 SHA256 哈希
