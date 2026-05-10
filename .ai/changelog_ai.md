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
