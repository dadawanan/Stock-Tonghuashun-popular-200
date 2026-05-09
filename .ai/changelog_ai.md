# AI 决策与纠偏日志

> 记录"为什么"而非"改了什么"。当 AI 反复犯错时追加规则，当架构决策变更时记录原因。

格式：`日期 | 类型 | 规则/决策 | 原因`

---

## 2025-05-09 | 初始化 | 项目初始状态记录

- 项目采用 DDD 分层架构（api → application → domain ← infrastructure），不使用 ORM，直接 asyncpg 原生 SQL
- 分析引擎当前仅支持规则分析（`analysis_rules.py`），预留 LLM 分析扩展点（`analyzer_type` 字段支持 `rule/llm/hybrid`）
- 股票代码格式统一为 `XXXXXX.SH/SZ/BJ`，项目中存在两个 `normalize_stock_code()` 实现（`domain/services/analysis_rules.py` 和 `infrastructure/providers/eastmoney_provider.py`），功能一致但未统一，后续应收敛为一处

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
