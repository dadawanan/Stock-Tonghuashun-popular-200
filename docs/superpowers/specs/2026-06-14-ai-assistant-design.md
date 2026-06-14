# AI 智能助手设计文档

> 日期：2026-06-14
> 状态：已批准

## 概述

为 stock-system 添加 AI 智能助手功能。前端 ChatAssistant 组件已实现，需要补全后端代理层和 AI 服务。

## 技术选型

| 维度 | 选择 |
|---|---|
| AI 框架 | Pydantic AI (`pydantic-ai`) |
| LLM | OpenAI API (GPT-4o) |
| 架构模式 | 代理模式（stock 后端 → agent-stock） |
| 传输方式 | SSE 流式 |
| 部署方式 | Docker 容器 |
| 聊天历史 | 有状态（前端维护，请求时传入） |
| Agent 策略 | 单 Agent + 工具路由 |
| AI 风格 | 专业金融分析师 |

## 系统架构

```
┌──────────────┐  POST /api/chat/send  ┌───────────────┐  HTTP   ┌──────────────┐
│  前端         │ ───────────────────→  │  stock 后端    │ ──────→ │  agent-stock  │
│  ChatAssist. │ ←─── SSE stream ────  │  (新增路由)    │ ←SSE──  │  (Pydantic AI)│
└──────────────┘                       └───────────────┘        │  Docker 容器  │
                                                                └──────────────┘
```

**数据流：**

1. 前端发送 `{ message, history }` 到 stock 后端 `POST /api/chat/send`
2. stock 后端转发到 agent-stock 的 SSE 端点
3. agent-stock 的 Pydantic AI Agent 处理请求，流式返回 token
4. stock 后端透传 SSE 流到前端
5. 前端逐字渲染 AI 回复

**通信协议：**

- stock 后端 → agent-stock：`POST /api/chat/stream`，`Accept: text/event-stream`
- stock 后端 → 前端：透传相同的 SSE 流（`Content-Type: text/event-stream`）
- SSE 事件格式（端到端一致）：
  - `data: {"type": "token", "content": "..."}` — 文本 token
  - `data: {"type": "done"}` — 流结束
  - `data: {"type": "error", "content": "..."}` — 错误

## agent-stock 服务

### 目录结构

```
agent-stock/
├── pyproject.toml
├── Dockerfile
├── .env.example
├── src/
│   └── agent_stock/
│       ├── __init__.py
│       ├── main.py              # FastAPI 入口 + SSE 端点
│       ├── agent.py             # Pydantic AI Agent 定义
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── stock_tools.py   # 热门股票、排行查询
│       │   ├── account_tools.py # 模拟账户操作
│       │   ├── news_tools.py    # 新闻与行情
│       │   └── analysis_tools.py # 回测与策略
│       ├── schemas.py           # 请求/响应模型
│       └── config.py            # 配置
```

### 核心组件

**config.py：**
- `OPENAI_API_KEY` — OpenAI API 密钥
- `STOCK_API_URL` — stock 后端地址（默认 `http://localhost:8000`）

**agent.py：**
```python
from pydantic_ai import Agent

agent = Agent(
    'openai:gpt-4o',
    system_prompt="""你是A股智能助手，专业金融分析师风格。
    你可以帮助用户查询热门股票、查看模拟账户、了解新闻行情、分析回测结果。
    回答要专业、简洁、有数据支撑。""",
    tools=[...],  # 注册所有工具
)
```

**main.py — SSE 端点：**
```python
@router.post("/api/chat/stream")
async def api_chat_stream(request: ChatRequest):
    """SSE 流式聊天端点"""
    # 使用 Pydantic AI 的 stream 方法
    # 逐 token 生成 SSE 事件
```

**schemas.py：**
```python
class ChatRequest(BaseModel):
    message: str
    history: list[ChatHistoryMessage] = []

class ChatHistoryMessage(BaseModel):
    role: Literal['user', 'assistant']
    content: str

class ChatChunk(BaseModel):
    type: Literal['token', 'done', 'error']
    content: str = ''
```

### 聊天历史管理

- 前端每次请求带上本次会话的历史消息
- Agent 使用 Pydantic AI 的 `message_history` 参数维护上下文
- 不做持久化，刷新页面历史清空

## 工具定义（Function Calling）

### stock_tools.py — 热门股票查询

| 工具函数 | 说明 | 调用的 API |
|---|---|---|
| `get_popular_stocks()` | 获取今日热门排行 | `GET /api/popularity/latest` |
| `get_stock_list()` | 获取股票列表 | `GET /api/stocks` |

### account_tools.py — 模拟交易

| 工具函数 | 说明 | 调用的 API |
|---|---|---|
| `get_sim_accounts()` | 获取模拟账户列表 | `GET /api/quant/sim/accounts` |
| `get_account_positions(account_id)` | 获取持仓 | `GET /api/quant/sim/{id}/positions` |
| `get_account_orders(account_id)` | 获取委托记录 | `GET /api/quant/sim/{id}/orders` |

### news_tools.py — 新闻与行情

| 工具函数 | 说明 | 调用的 API |
|---|---|---|
| `get_stock_news(stock_code)` | 获取股票新闻 | `GET /api/news/{code}` |
| `get_stock_analysis(stock_code)` | 获取分析结果 | `GET /api/analysis/{code}` |

### analysis_tools.py — 回测与策略

| 工具函数 | 说明 | 调用的 API |
|---|---|---|
| `get_strategies()` | 获取策略列表 | `GET /api/quant/strategies` |
| `get_backtest_results()` | 获取回测结果 | `GET /api/quant/backtest/results` |
| `get_stock_price(stock_code)` | 获取实时行情 | `GET /api/quant/market/prices` |

### 工具实现模式

每个工具函数使用 `@agent.tool` 装饰器注册到 Agent。Pydantic AI 自动将函数签名和 docstring 转换为 LLM 可调用的工具定义。

```python
from pydantic_ai import Agent, RunContext
import httpx

agent = Agent('openai:gpt-4o', system_prompt='...')

@agent.tool
async def get_popular_stocks(ctx: RunContext) -> str:
    """获取今日A股热门股票排行。返回热门股票列表的JSON数据。"""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{settings.stock_api_url}/api/popularity/latest")
        return json.dumps(resp.json(), ensure_ascii=False)
```

## stock 后端代理层

### 新增文件

- `src/stock_service/api/routes/chat.py` — 路由
- `src/stock_service/application/services/chat_service.py` — HTTP 客户端

### 路由定义

```python
router = APIRouter(prefix="/api/chat", tags=["chat"])

@router.post("/send")
async def api_send_message(request: ChatRequest):
    """接收用户消息，转发到 agent-stock，SSE 流式返回"""
```

### 路由注册（app.py 新增）

```python
from stock_service.api.routes.chat import router as chat_router
app.include_router(chat_router)
```

### 配置

- 新增环境变量 `AGENT_STOCK_URL`（默认 `http://localhost:8001`）
- Docker 环境中为 `http://agent-stock:8001`

## 前端改造

### 改动文件

1. `web-ui/src/utils/api.ts` — chatApi 改为 SSE 流式请求
2. `web-ui/src/components/ChatAssistant.tsx` — 支持逐字渲染

### SSE 客户端

```typescript
chatApi.sendMessage = (message: string, history: ChatMessage[]) => {
  return fetch('/api/chat/send', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
    body: JSON.stringify({ message, history }),
  });
};
```

### 流式渲染

- 收到 SSE 事件后，逐 token 追加到当前消息的 `content`
- 复用现有加载动画（loading dots），在第一个 token 到达前显示
- 新增 `isStreaming` 状态控制

### 意图动作处理

- `navigate` → `window.location.href = payload.path`
- `query` → 调用对应 API 并展示结果
- `analyze` → 跳转分析页面并传参

## Docker 部署

### Dockerfile

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install -e .
COPY src/ src/
CMD ["uvicorn", "agent_stock.main:app", "--host", "0.0.0.0", "--port", "8001"]
```

### docker-compose.yml 新增

```yaml
services:
  agent-stock:
    build: ../agent-stock
    ports:
      - "8001:8001"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - STOCK_API_URL=http://stock-api:8000
    depends_on:
      - stock-api
```

### 网络关系

- `agent-stock` 通过 Docker 内部网络访问 `stock-api:8000`
- 前端通过 `stock-api:8000/api/chat/send` 访问
- agent-stock 不直接暴露给前端

## 错误处理

| 场景 | 处理方式 |
|---|---|
| agent-stock 不可用 | stock 后端返回 503，前端显示"服务暂时不可用" |
| OpenAI API 错误 | agent-stock 返回错误事件，前端显示错误提示 |
| 工具调用失败 | Agent 优雅降级，用自然语言告知用户 |
| SSE 连接断开 | 前端自动重试一次，失败后显示错误 |

## 测试策略

- **单元测试**：工具函数 mock stock API 响应
- **集成测试**：agent-stock 端到端测试（mock OpenAI）
- **E2E 测试**：前端完整流程测试
