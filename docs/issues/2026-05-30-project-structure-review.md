# 项目结构审查报告 (2026-05-30)

---

## CRITICAL 严重

### 1. ~~生产密钥提交到 Git~~ （已排除）

经核实，`.env` 未被 git 追踪，远端仓库也没有。`.gitignore` 生效正常。

### 2. 全局异常处理器泄露堆栈信息

`src/stock_service/api/app.py` 的 `global_exception_handler` 直接返回 `traceback.format_exc()`。生产环境会把文件路径、变量名、SQL 查询暴露给客户端。

**处理**：生产环境只返回错误消息，不返回 traceback。

### 3. `get_async_session()` 死代码

- `db/database.py` 35-42 行定义 `get_async_session()`
- `api/dependencies.py` 16-23 行定义 `get_session()`

两者逻辑完全相同，但名字不同。FastAPI 用的是 `dependencies.py` 的 `get_session()`，`database.py` 的 `get_async_session()` 没有被任何地方引用，是死代码。

**处理**：删除 `database.py` 中的 `get_async_session()`。

### 4. ~~`list_feedback_logs` 重复定义~~ （已排除）

经核实，`quant_crud.py` 中只有一处 `list_feedback_logs` 定义（第 575 行）。审查报告误判。

### 5. CRUD 层混用原始 SQL

以下位置使用 `session.execute(text("..."))` 绕过 ORM：
- `quant_crud.py` 的 `batch_upsert_stock_daily` / `batch_upsert_stock_indicator`
- `strategies.py` 路由中的查询
- `scheduler.py` 中的查询
- `market_data_service.py` 中的查询

列名变更不会在编译期报错，只会在运行时失败。

**处理**：逐步迁回 ORM，或至少将原始 SQL 集中到 CRUD 层。

### 6. StrategyEngine 注册重复 4 处

同样的 10 个 `strategy_engine.register(...)` 调用分散在：
- `scheduler.py`
- `quant/api/routes/backtest.py`
- `quant/application/strategy_engine.py`
- `quant/application/optimizer.py`

新增策略需要改 4 个文件。

**处理**：统一到 `strategy_engine.py` 的全局 `engine` 实例，其他地方直接 import。

---

## MODERATE 中等

### 7. 生产代码使用 `print()` 而非 `logging`

`market_data_service.py`、`analysis_service.py`、`main.py` 中有 12 处 `print()`。无法按日志级别过滤，不带时间戳。

**处理**：改为 `logger.info()` / `logger.warning()`。

### 8. 裸 `except:` 静默吞错误

`quant/api/routes/sim_trading.py` 第 182 行：

```python
except:
    pass
```

捕获所有异常（包括 `KeyboardInterrupt`），导致日期解析错误被静默忽略，交易分析数据不准确。

**处理**：改为 `except Exception:` 并记录日志。

### 9. `normalize_stock_code` 导入层级不一致

- `analysis_service.py` 从 `domain.services.stock_utils` 导入（正确）
- `v2_crud.py` 从 `infrastructure.providers.stock_code` 导入（违反依赖方向）

CRUD 层不应依赖 infrastructure 层。

**处理**：统一从 `domain.services.stock_utils` 导入。

### 10. 错误响应格式不统一

- 主路由：`HTTPException(status_code=500, detail=str(exc))`
- 量化路由：英文消息 `"Strategy not found"`
- 全局异常：`{"code": -1, "msg": ..., "detail": ...}`
- 正常响应：`{"code": 0, "msg": "", "data": ...}`

**处理**：统一错误响应格式。

### 11. 空的 `quant/crud/__init__.py`

`quant/crud/` 包存在但只有一个空的 `__init__.py`，没有实际模块。所有量化 CRUD 在 `stock_service/crud/quant_crud.py`。

**处理**：删除空目录。

### 12. 空的 `infrastructure/db/repositories/` 目录

目录存在但无文件，是未完成的 repository 模式残留。

**处理**：删除空目录。

### 13. Schema SQL 无版本管理

`schema_v2.sql` 和 `schema_quant_v1.sql` 两个文件，无 Alembic 等迁移工具，无文档说明应用顺序。

**处理**：引入 Alembic 或至少在 README 中说明。

### 14. 分析规则硬编码

`analysis_rules.py` 中关键词列表、评分权重（`0.55`、`0.45`）全部硬编码。

**处理**：移到配置文件或数据库。

---

## MINOR 轻微

### 15. `_rows_to_dicts` 重复定义

`v2_crud.py` 和 `quant_crud.py` 各定义了一份相同的工具函数。

**处理**：提取到共享模块。

### 16. quant 子包 7 个空 `__init__.py`

`src/stock_service/quant/` 下所有 `__init__.py` 为空，与主包风格不一致。

### 17. 根目录 `app.py` 使用 `sys.path` hack

`app.py` 手动插入 `src/` 到 `sys.path`。`pyproject.toml` 已正确定义包，`pip install -e .` 即可。

### 18. `docker-compose.yml` 使用废弃的 `version` 键

### 19. CORS 默认值硬编码了生产 IP

`app.py` 默认 `ALLOWED_ORIGINS` 包含 `101.35.255.200:8001`。

### 20. 测试覆盖率低

约 1082 行测试代码 vs 79000 行源代码。无 API 集成测试，前端零测试。

### 21. `test_scheduler.py` 在项目根目录

不在 `tests/` 目录下，pytest 默认不会发现。

### 22. `pyproject.toml` 描述是占位符

`description = "Add your description here"`

### 23. `web-ui/dist/` 提交到 Git

编译产物不应在版本控制中。`.gitignore` 未排除。

### 24. 模块加载时执行副作用

`settings.py` 在 import 时读 `.env`、修改环境变量。`database.py` 在 import 时创建引擎并打印连接串（含密码）。

**处理**：改为惰性初始化。
