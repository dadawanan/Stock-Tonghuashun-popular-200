# 全局规则（AI 必须遵守）

> 本文件是 AI 编码时的硬约束。违反任何一条都必须拒绝执行并提示修正。

---

## 禁止事项

- **禁止在 router 中写业务逻辑。** 路由只负责参数校验、调用 service、返回响应。业务逻辑必须放在 `application/services/` 或 `domain/services/` 中。
- **禁止使用同步数据库操作。** 所有 asyncpg 调用必须 `await`，所有数据库函数必须 `async def`。
- **禁止直接 `raise Exception`。** 使用具体异常类型（`ValueError`、`RuntimeError`）或 FastAPI 的 `HTTPException`。
- **禁止硬编码数据库连接信息。** 所有配置通过 `.env` + `infrastructure/config/settings.py` 读取。
- **禁止在 Repository 层以外直接写 SQL。** SQL 只允许出现在 `infrastructure/db/repositories/` 中。
- **禁止 Pydantic 模型复用 In/Out。** 如需新增，必须区分 `XxxCreate`（入参）和 `XxxRead`（出参）。
- **禁止使用 `requests`（同步）。** 外部 HTTP 请求使用 `curl_cffi` 的异步接口，或确保在独立线程中执行同步调用。

---

## 代码风格

- Python 版本：>= 3.12，可自由使用 `type | None`、`X | Y` 语法，不需要 `from __future__ import annotations` 来兼容旧版。
- FastAPI 依赖注入：使用 `Annotated[type, Depends(func)]` 模式。
- 类型注解：所有公开函数必须有完整的类型注解。
- 日志：使用 `logging.getLogger(__name__)`，详见「日志」章节。
- 股票代码格式：统一使用 `XXXXXX.SS/SH/SZ/BJ` 格式，通过 `normalize_stock_code()` 转换，不得出现裸数字代码。

---

## 命名与文件约定

- 模块、文件名：必须使用 `snake_case`。
- 类名：必须使用 `PascalCase`；Pydantic 模型禁止用 `Model` 后缀。
- Pydantic 模型必须严格区分 In / Out / DTO 三类，命名后缀如下：
  - 入参：`*Request`（如 `HistoryQueryRequest`、`AlignmentConfigUpdateRequest`）
  - 出参 / 列表项 / 详情：`*Response` / `*Data` / `*ListData`（如 `HistoryResponse`、`AlignmentConfigData`、`AlignmentConfigListData`）
  - 数据库实体直接序列化的：必须带 `class Config: from_attributes = True`
- 路由函数名：必须以 `api_` 前缀开头（保持与 `app/routes/api.py` 现有风格一致），例如 `api_history`、`api_get_active_template`。

---

## 数据库规范

- ORM：不使用 ORM，直接使用 asyncpg 原生 SQL。
- Schema 文件：`schema_v2.sql`，新增表或字段必须同步更新此文件。
- 连接池：通过 `StockDatabase` 单例管理，`lifespan` 中初始化/关闭。
- Repository 基类：所有 Repository 继承 `BaseRepository`，通过 `self.pool` 获取连接。
- 批量写入：使用 `COPY` 或批量 `INSERT`，禁止逐条插入。
- 时区：数据库中时间字段统一使用 `TIMESTAMPTZ`，Python 端使用 `Asia/Shanghai` 时区。
- DB 连接：路由中必须通过 `Depends(get_db_pool)` 注入；后台任务中必须使用 `pool.acquire() + async with conn` 显式管理连接生命周期。
- 写操作：使用 `async with conn.transaction()` 自动管理提交/回滚；若手动管理事务，任何 except 分支若可能已执行写操作，必须显式回滚后再处理异常。
- 严禁直接拼接 SQL 字符串；参数必须使用 `$1, $2, ...` 占位符传入，禁止 f-string / format 拼接用户输入。
- 状态字段：必须使用 `VARCHAR(1)`，取值 `'Y'` / `'N'`，严禁使用 `BOOLEAN`。
- 时间字段：写入时使用 `datetime.now(ZoneInfo("Asia/Shanghai"))`，严禁使用 `time.time()` 整数戳直接落库。
- 主键：业务唯一键作为主键时长度必须 ≥ `VARCHAR(100)`，并显式声明 `NOT NULL`。

---

## API 规范

- 统一响应格式：`ApiResponse(code=0, msg="", data=...)`，错误时 `HTTPException`。
- RESTful 风格：GET 查询、POST 触发动作。
- 路由前缀：`/api/`，如 `/api/stocks`、`/api/analysis`。
- 分页参数：使用 `Query(default=20, le=100)` 风格的 FastAPI Query 校验。

---

## 外部数据源

- 同花顺人气榜：`pywencai` 库，通过 `ths_provider.py` 封装。
- 东方财富行情/资金流/新闻：`akshare` + `curl_cffi`，通过 `eastmoney_provider.py` 封装。
- 新增数据源时，必须在 `infrastructure/providers/` 下新建独立文件，不得混入现有 provider。
- 外部请求必须有重试机制（默认 3 次），失败时抛出 `RuntimeError` 并包含原始异常。
- 请求间必须加 `time.sleep()` 防止被限流，默认 0.2-0.3 秒。

---

## 日志

- 必须使用模块级 `logger = logging.getLogger(__name__)`。
- 严禁使用 `print(...)` 作为业务日志输出（仅允许在 `__main__` 调试入口使用）。
- 日志中严禁输出完整图片二进制、密码、token；可输出路径、大小、股票代码等元数据。
- 异常日志必须带 `exc_info=True` 或 `logger.error(traceback.format_exc())`。

---

## AI 协作纪律

- 任何对架构 / 数据流 / 状态字段的改动：必须同步更新 `architecture.md`、`api_spec/*.md`，并在 `changelog_ai.md` 追加一条「为什么这么改」。
- 当 AI 收到与本文件冲突的指令时：必须优先指出冲突并请求人类确认，严禁沉默地绕过规则。
- 本文件的修改必须留下 git diff 与 changelog 记录，严禁静默替换。

---

## 代码组织：反碎片化（避免过度抽象 / 过度拆分）

本节针对 AI 高频陋习：把一段本应就地写完的小逻辑随手抽成 `_xxx` 私有函数、甚至新建一个独立文件，导致函数 / 文件碎片化，阅读时反复跳转，长期维护成本上升。

- 简单逻辑（对 list 做求和 / 过滤 / 计数 / 取最大值、字段重命名 / 重组、字符串拼接、单一条件分支等）必须直接写在调用点函数体内，严禁为它单独抽出 `_xxx` 私有函数。
- 严禁为单一调用点新建独立文件（典型陋习：`xxx_helpers.py`、`xxx_utils.py`、`xxx_calc.py`），把一段 5–20 行的小逻辑塞进去当做"工具"。
- 抽函数 / 抽文件的唯一触发条件（满足任一即可，否则严禁抽）：
  1. 同一段逻辑被 ≥ 2 处真实调用（DRY 真正成立，不是想象的"以后可能会用到"）；或
  2. 用户 / 人类显式要求抽出来（例如「这段抽个函数」「单独搞个文件」）；或
  3. 单段逻辑长度 > 40 行且单一职责清晰（这种情况下抽出来是为了局部可读性，而非复用）。
- 抽出来时必须按「能近不远」的层级选择落点，严禁越级：

| 复用范围 | 应放在哪 |
|---|---|
| 同一函数内多次小重复 | 局部变量 / 推导式 / 内联 lambda；不抽函数 |
| 同一文件内多函数复用 | 同文件末尾 `_xxx` 私有函数 |
| 同一 service 多文件复用 | 该 service 模块的 public 函数 |
| 跨 service / 跨层复用 | `app/services/<topic>.py` 或 `app/core/<topic>.py` |

- 既存的 `_xxx` 私有 helper 若只被 1 处调用，可在改动该处时顺手内联回去；但严禁借此发起与本次任务无关的大范围重构。
- 当 AI 不确定该不该抽时：默认不抽，写在原地；若用户明确说「这段抽一下 / 单独放个文件」，再按上表选最近一层落点。