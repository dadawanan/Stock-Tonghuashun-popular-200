# Prompt — 新增 FastAPI 路由

请扮演本仓库的资深后端工程师。你**必须**严格遵循 `web/docs/ai_context/system_rules.md` 与 `architecture.md`。
当下任务：根据下方「模块设计稿」生成一组完整的接口实现。

---

## 输入（由提问者补全）

- 模块设计稿：`web/docs/ai_context/api_spec/<module>.md`
- 接口编号 / 名称：<例如 `POST /xxx`>
- 业务约束（非默认部分）：<例如鉴权 / 限流 / 边界条件>

## 你必须按以下顺序产出

1. **Pydantic 模型**（在 `app/schemas/<module>.py`）
   - In：`*Request`
   - Out：`*Response` / `*Data` / `*ListData`（`from_attributes=True` 当且仅当来源是 ORM 实体）
   - 字段必带 `Field(..., description=...)`，描述使用中文
   - 校验通过 `field_validator`，**严禁**在路由内手写校验
2. **Service 函数 / 类**（在 `app/services/<module>_service.py`）
   - 处理所有业务逻辑：DB 读写、Redis 操作、模板比对、外部 HTTP 调用
   - 失败抛 `ValueError`（业务错） / 自定义 `Exception`（系统错），**严禁**直接抛 `HTTPException`
   - DB 显式 `commit/rollback`；后台流程使用 `SessionLocal()` + `try/finally`
3. **FastAPI 路由**（在 `app/routes/api.py`）
   - 函数名 `api_<动词>_<对象>`（如 `api_get_xxx`）
   - 必须 `async def`；声明 `response_model=SuccessResponse[<DataModel>]`
   - 业务异常 `ValueError → HTTPException(400|404)`，未知异常 `→ logger.error(exc_info=True) + HTTPException(500)`
   - 写操作完成后**必须**调用 `core/websocket_manager.send_*` 推送对应消息（如果业务相关）
4. **Settings 项**（如需新配置）
   - 在 `app/core/config.py::Settings` 增加字段，给默认值，加中文注释
   - 不要在代码中重复硬编码字面量
5. **API Spec 同步**
   - 把新增 / 修改的内容回填到 `api_spec/<module>.md`，保持文档与代码 1:1
6. **changelog 追加一条**
   - 写到 `web/docs/ai_context/changelog_ai.md`，遵循文件顶部模板

## 强校验清单（写完后自检）

- [ ] 路由函数为 `async def`
- [ ] 路由声明了 `response_model`，统一 `SuccessResponse[T]`
- [ ] Schema 区分 In/Out，**没有**混用同一个类
- [ ] DB 写入有 `try/except + rollback`
- [ ] 没有在路由层 `redis.Redis(...)` 重新建立连接
- [ ] 配置值没有硬编码
- [ ] 错误信息为中文且语义明确
- [ ] 已用 `logger.info` 记录关键路径，关键失败 `logger.error(exc_info=True)`
- [ ] 已更新 `api_spec/<module>.md` 与 `changelog_ai.md`
