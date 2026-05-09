# Prompt — 新增 Service（业务逻辑层）

你将创建 / 修改 `app/services/` 下的业务模块。
请严格遵守 `web/docs/ai_context/system_rules.md` 第 2 节（目录与分层职责）与第 5 节（数据库访问）。

## 输入（由提问者补全）

- 模块名：`<snake_case>`（决定文件名 `<name>_service.py`）
- 业务目标：<一两句话讲清楚要做什么>
- 涉及表 / 队列 / 外部依赖：<列出>

## 你必须产出

1. **文件**：`app/services/<name>_service.py`
2. **结构（三选一，选最简单的够用即可）**：
   - 纯函数集合（无状态业务）
   - `class XxxService` 仅含 `@staticmethod / @classmethod`（无实例状态）
   - `class XxxService` 含构造、`close()` / `__del__`（持有外部资源时；如视觉 SDK、长连接）
3. **依赖与生命周期**：
   - 路由请求内：让上层把 `db: Session` 当参数传入；**不**在 service 里 `Depends(get_db)`
   - 后台线程内：`db = SessionLocal()` + `try/finally: db.close()`
   - Redis：复用 `routes/api.py::get_redis_client` 或自建 `_build_redis_client`
4. **错误处理**：
   - 业务校验失败抛 `ValueError`（中文 message，路由层会转 4xx）
   - 系统级错误抛具体异常类型（`RuntimeError / TimeoutError`）；不要静默吞
   - 写 DB 出错 → `logger.error(..., exc_info=True)`，回滚后重新抛
5. **日志**：模块顶部 `logger = logging.getLogger(__name__)`；关键步骤用 `logger.info`，慢 IO 前后各一行
6. **文档**：
   - 文件顶部 docstring 写：「这个模块的存在意义 + 主要 API + 使用示例」
   - 涉及算法 / 复杂阈值，配套写一份 `services/<name>_algorithm.md` 与代码并存

## 强校验

- [ ] 没有 FastAPI 路由装饰器
- [ ] 没有 `HTTPException` 引用
- [ ] 没有硬编码常量（阈值/路径/超时来自 `settings`）
- [ ] 后台流程优雅退出有 `stop_event` 钩子
- [ ] 单测能 mock DB / Redis（构造函数 / 参数注入足够透明）
- [ ] 没有为单点小逻辑提前预留 `_xxx` 私有函数 / `xxx_helpers.py`（在出现 ≥ 2 处复用、或用户明确要求之前**不抽**；详见 `system_rules.md` 第 14 节）
