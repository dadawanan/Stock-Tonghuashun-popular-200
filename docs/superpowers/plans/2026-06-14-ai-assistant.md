# AI 智能助手 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an AI chat assistant to the stock system with SSE streaming, tool calling, and a professional analyst persona.

**Architecture:** Single Pydantic AI Agent in a separate `agent-stock` service, proxied through the stock backend's `/api/chat/send` endpoint. Frontend streams responses via SSE.

**Tech Stack:** Pydantic AI, OpenAI API (GPT-4o), FastAPI, httpx, SSE, Docker

**Design Spec:** `docs/superpowers/specs/2026-06-14-ai-assistant-design.md`

---

## File Structure

### agent-stock (new project)

| File | Responsibility |
|---|---|
| `agent-stock/pyproject.toml` | Project config, dependencies |
| `agent-stock/Dockerfile` | Container build |
| `agent-stock/.env.example` | Environment template |
| `agent-stock/src/agent_stock/__init__.py` | Package init |
| `agent-stock/src/agent_stock/config.py` | Settings (API key, stock API URL) |
| `agent-stock/src/agent_stock/schemas.py` | Pydantic request/response models |
| `agent-stock/src/agent_stock/agent.py` | Agent definition + system prompt |
| `agent-stock/src/agent_stock/tools/__init__.py` | Tool registration |
| `agent-stock/src/agent_stock/tools/stock_tools.py` | Hot stocks tools |
| `agent-stock/src/agent_stock/tools/account_tools.py` | Sim account tools |
| `agent-stock/src/agent_stock/tools/news_tools.py` | News & market tools |
| `agent-stock/src/agent_stock/tools/analysis_tools.py` | Backtest & strategy tools |
| `agent-stock/src/agent_stock/main.py` | FastAPI app + SSE endpoint |

### stock backend (modifications)

| File | Change |
|---|---|
| `src/stock_service/infrastructure/config/settings.py` | Add `agent_stock_url` property |
| `src/stock_service/api/routes/chat.py` | New route file |
| `src/stock_service/application/services/chat_service.py` | New service file |
| `src/stock_service/api/app.py` | Register chat router |
| `stock/docker-compose.yml` | Add agent-stock service |

### Frontend (modifications)

| File | Change |
|---|---|
| `web-ui/src/utils/api.ts` | chatApi SSE support |
| `web-ui/src/components/ChatAssistant.tsx` | Streaming render |

---

### Task 1: Scaffold agent-stock project

**Files:**
- Create: `agent-stock/pyproject.toml`
- Create: `agent-stock/src/agent_stock/__init__.py`
- Create: `agent-stock/.env.example`

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[project]
name = "agent-stock"
version = "0.1.0"
description = "AI 智能助手服务 - Pydantic AI Agent"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "pydantic-ai>=0.2.0",
    "pydantic>=2.0",
    "fastapi>=0.136.1",
    "uvicorn>=0.46.0",
    "httpx>=0.27.0",
    "openai>=1.50.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=9.0.3",
    "pytest-asyncio>=1.3.0",
    "respx>=0.21.0",
]

[tool.setuptools]
package-dir = {"" = "src"}

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

- [ ] **Step 2: Create __init__.py**

```python
"""agent-stock: AI 智能助手服务"""
```

- [ ] **Step 3: Create .env.example**

```bash
OPENAI_API_KEY=sk-your-key-here
STOCK_API_URL=http://localhost:8000
AGENT_HOST=0.0.0.0
AGENT_PORT=8001
```

- [ ] **Step 4: Install dependencies and verify**

Run: `cd /Users/fyq/Desktop/workshop/stock-system/agent-stock && pip install -e ".[dev]"`
Expected: Successfully installed agent-stock and dependencies

- [ ] **Step 5: Commit**

```bash
cd /Users/fyq/Desktop/workshop/stock-system/agent-stock
git init
git add pyproject.toml .env.example src/agent_stock/__init__.py
git commit -m "feat(agent-stock): scaffold project with pydantic-ai dependencies"
```

---

### Task 2: Config and schemas

**Files:**
- Create: `agent-stock/src/agent_stock/config.py`
- Create: `agent-stock/src/agent_stock/schemas.py`

- [ ] **Step 1: Create config.py**

```python
from __future__ import annotations

import os
from pathlib import Path


def _load_dotenv() -> None:
    """Load .env file if present."""
    for env_path in [Path.cwd() / ".env", Path(__file__).resolve().parents[3] / ".env"]:
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or "=" not in stripped:
                    continue
                key, value = stripped.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())
            break


_load_dotenv()


class Settings:
    """Lazy-loaded settings from environment variables."""

    def __init__(self) -> None:
        self._cache: dict[str, object] = {}

    def _get(self, key: str, loader) -> object:
        if key not in self._cache:
            self._cache[key] = loader()
        return self._cache[key]

    @property
    def openai_api_key(self) -> str:
        return self._get("openai_api_key", lambda: os.environ.get("OPENAI_API_KEY", ""))  # type: ignore[return-value]

    @property
    def stock_api_url(self) -> str:
        return self._get("stock_api_url", lambda: os.environ.get("STOCK_API_URL", "http://localhost:8000"))  # type: ignore[return-value]

    @property
    def agent_host(self) -> str:
        return self._get("agent_host", lambda: os.environ.get("AGENT_HOST", "0.0.0.0"))  # type: ignore[return-value]

    @property
    def agent_port(self) -> int:
        return self._get("agent_port", lambda: int(os.environ.get("AGENT_PORT", "8001")))  # type: ignore[return-value]


settings = Settings()
```

- [ ] **Step 2: Create schemas.py**

```python
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ChatHistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatHistoryMessage] = []


class ChatChunk(BaseModel):
    type: Literal["token", "done", "error"]
    content: str = ""
```

- [ ] **Step 3: Verify imports**

Run: `cd /Users/fyq/Desktop/workshop/stock-system/agent-stock && python -c "from agent_stock.config import settings; from agent_stock.schemas import ChatRequest, ChatChunk; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
cd /Users/fyq/Desktop/workshop/stock-system/agent-stock
git add src/agent_stock/config.py src/agent_stock/schemas.py
git commit -m "feat(agent-stock): add config and Pydantic schemas"
```

---

### Task 3: Tool functions — stock tools

**Files:**
- Create: `agent-stock/src/agent_stock/tools/__init__.py`
- Create: `agent-stock/src/agent_stock/tools/stock_tools.py`

- [ ] **Step 1: Create tools/__init__.py**

```python
"""Tool modules for the AI agent."""
```

- [ ] **Step 2: Create tools/stock_tools.py**

```python
from __future__ import annotations

import json
import logging

import httpx

from agent_stock.config import settings

logger = logging.getLogger(__name__)


async def get_popular_stocks() -> str:
    """获取今日A股热门股票排行。返回同花顺人气榜Top200的JSON数据，包含股票代码、名称、排名等。"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{settings.stock_api_url}/api/popularity/latest")
            resp.raise_for_status()
            data = resp.json()
            return json.dumps(data, ensure_ascii=False)
    except Exception as e:
        logger.exception("get_popular_stocks failed")
        return json.dumps({"error": f"获取热门股票失败: {e}"}, ensure_ascii=False)


async def get_stock_list() -> str:
    """获取所有股票列表。返回数据库中所有股票代码和名称的JSON数据。"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{settings.stock_api_url}/api/stocks")
            resp.raise_for_status()
            data = resp.json()
            return json.dumps(data, ensure_ascii=False)
    except Exception as e:
        logger.exception("get_stock_list failed")
        return json.dumps({"error": f"获取股票列表失败: {e}"}, ensure_ascii=False)
```

- [ ] **Step 3: Verify module loads**

Run: `cd /Users/fyq/Desktop/workshop/stock-system/agent-stock && python -c "from agent_stock.tools.stock_tools import get_popular_stocks, get_stock_list; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
cd /Users/fyq/Desktop/workshop/stock-system/agent-stock
git add src/agent_stock/tools/
git commit -m "feat(agent-stock): add stock tools (popular stocks, stock list)"
```

---

### Task 4: Tool functions — account tools

**Files:**
- Create: `agent-stock/src/agent_stock/tools/account_tools.py`

- [ ] **Step 1: Create tools/account_tools.py**

```python
from __future__ import annotations

import json
import logging

import httpx

from agent_stock.config import settings

logger = logging.getLogger(__name__)


async def get_sim_accounts() -> str:
    """获取用户的模拟交易账户列表。返回所有模拟账户的JSON数据，包含账户ID、名称、资金等。"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{settings.stock_api_url}/api/quant/sim/accounts")
            resp.raise_for_status()
            return json.dumps(resp.json(), ensure_ascii=False)
    except Exception as e:
        logger.exception("get_sim_accounts failed")
        return json.dumps({"error": f"获取模拟账户失败: {e}"}, ensure_ascii=False)


async def get_account_positions(account_id: int) -> str:
    """获取指定模拟账户的持仓信息。参数account_id为账户ID。"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{settings.stock_api_url}/api/quant/sim/{account_id}/positions")
            resp.raise_for_status()
            return json.dumps(resp.json(), ensure_ascii=False)
    except Exception as e:
        logger.exception("get_account_positions failed")
        return json.dumps({"error": f"获取持仓失败: {e}"}, ensure_ascii=False)


async def get_account_orders(account_id: int) -> str:
    """获取指定模拟账户的委托记录。参数account_id为账户ID。"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{settings.stock_api_url}/api/quant/sim/{account_id}/orders")
            resp.raise_for_status()
            return json.dumps(resp.json(), ensure_ascii=False)
    except Exception as e:
        logger.exception("get_account_orders failed")
        return json.dumps({"error": f"获取委托记录失败: {e}"}, ensure_ascii=False)
```

- [ ] **Step 2: Verify module loads**

Run: `cd /Users/fyq/Desktop/workshop/stock-system/agent-stock && python -c "from agent_stock.tools.account_tools import get_sim_accounts, get_account_positions, get_account_orders; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd /Users/fyq/Desktop/workshop/stock-system/agent-stock
git add src/agent_stock/tools/account_tools.py
git commit -m "feat(agent-stock): add account tools (sim accounts, positions, orders)"
```

---

### Task 5: Tool functions — news & analysis tools

**Files:**
- Create: `agent-stock/src/agent_stock/tools/news_tools.py`
- Create: `agent-stock/src/agent_stock/tools/analysis_tools.py`

- [ ] **Step 1: Create tools/news_tools.py**

```python
from __future__ import annotations

import json
import logging

import httpx

from agent_stock.config import settings

logger = logging.getLogger(__name__)


async def get_stock_news(stock_code: str) -> str:
    """获取指定股票的新闻资讯。参数stock_code为股票代码（如 000001.SZ）。"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{settings.stock_api_url}/api/news/{stock_code}")
            resp.raise_for_status()
            return json.dumps(resp.json(), ensure_ascii=False)
    except Exception as e:
        logger.exception("get_stock_news failed")
        return json.dumps({"error": f"获取新闻失败: {e}"}, ensure_ascii=False)


async def get_stock_analysis(stock_code: str) -> str:
    """获取指定股票的分析结果。参数stock_code为股票代码（如 000001.SZ）。"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{settings.stock_api_url}/api/analysis/{stock_code}")
            resp.raise_for_status()
            return json.dumps(resp.json(), ensure_ascii=False)
    except Exception as e:
        logger.exception("get_stock_analysis failed")
        return json.dumps({"error": f"获取分析结果失败: {e}"}, ensure_ascii=False)
```

- [ ] **Step 2: Create tools/analysis_tools.py**

```python
from __future__ import annotations

import json
import logging

import httpx

from agent_stock.config import settings

logger = logging.getLogger(__name__)


async def get_strategies() -> str:
    """获取所有量化策略列表。返回策略的JSON数据，包含策略ID、名称、参数等。"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{settings.stock_api_url}/api/quant/strategies")
            resp.raise_for_status()
            return json.dumps(resp.json(), ensure_ascii=False)
    except Exception as e:
        logger.exception("get_strategies failed")
        return json.dumps({"error": f"获取策略列表失败: {e}"}, ensure_ascii=False)


async def get_backtest_results() -> str:
    """获取回测结果列表。返回所有回测记录的JSON数据。"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{settings.stock_api_url}/api/quant/backtest/results")
            resp.raise_for_status()
            return json.dumps(resp.json(), ensure_ascii=False)
    except Exception as e:
        logger.exception("get_backtest_results failed")
        return json.dumps({"error": f"获取回测结果失败: {e}"}, ensure_ascii=False)


async def get_stock_price(stock_code: str) -> str:
    """获取股票实时行情。参数stock_code为股票代码（如 000001.SZ）。"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{settings.stock_api_url}/api/quant/market/prices",
                params={"codes": stock_code},
            )
            resp.raise_for_status()
            return json.dumps(resp.json(), ensure_ascii=False)
    except Exception as e:
        logger.exception("get_stock_price failed")
        return json.dumps({"error": f"获取行情失败: {e}"}, ensure_ascii=False)
```

- [ ] **Step 3: Verify modules load**

Run: `cd /Users/fyq/Desktop/workshop/stock-system/agent-stock && python -c "from agent_stock.tools.news_tools import get_stock_news, get_stock_analysis; from agent_stock.tools.analysis_tools import get_strategies, get_backtest_results, get_stock_price; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
cd /Users/fyq/Desktop/workshop/stock-system/agent-stock
git add src/agent_stock/tools/news_tools.py src/agent_stock/tools/analysis_tools.py
git commit -m "feat(agent-stock): add news and analysis tools"
```

---

### Task 6: Agent definition

**Files:**
- Create: `agent-stock/src/agent_stock/agent.py`

- [ ] **Step 1: Create agent.py**

```python
from __future__ import annotations

import json

from pydantic_ai import Agent, RunContext

from agent_stock.tools.stock_tools import get_popular_stocks, get_stock_list
from agent_stock.tools.account_tools import get_sim_accounts, get_account_positions, get_account_orders
from agent_stock.tools.news_tools import get_stock_news, get_stock_analysis
from agent_stock.tools.analysis_tools import get_strategies, get_backtest_results, get_stock_price

SYSTEM_PROMPT = """你是A股智能助手，一位专业的金融分析师。

你的职责：
1. 回答用户关于A股市场的问题
2. 帮助用户查询热门股票、行情数据、新闻资讯
3. 帮助用户了解模拟交易账户状态
4. 分析股票数据，提供专业的投资见解

回答风格：
- 专业、简洁、有数据支撑
- 使用中文回答
- 引用具体数据时说明数据来源
- 不提供具体的买卖建议，只提供分析和参考信息

你可以调用工具获取实时数据。当用户问到具体股票时，优先调用工具获取最新数据再回答。"""

stock_agent = Agent(
    "openai:gpt-4o",
    system_prompt=SYSTEM_PROMPT,
    retries=2,
)


@stock_agent.tool
async def tool_get_popular_stocks(ctx: RunContext) -> str:
    """获取今日A股热门股票排行。返回同花顺人气榜Top200的JSON数据。"""
    return await get_popular_stocks()


@stock_agent.tool
async def tool_get_stock_list(ctx: RunContext) -> str:
    """获取所有股票列表。返回数据库中所有股票代码和名称。"""
    return await get_stock_list()


@stock_agent.tool
async def tool_get_sim_accounts(ctx: RunContext) -> str:
    """获取用户的模拟交易账户列表。"""
    return await get_sim_accounts()


@stock_agent.tool
async def tool_get_account_positions(ctx: RunContext, account_id: int) -> str:
    """获取指定模拟账户的持仓信息。

    Args:
        account_id: 账户ID
    """
    return await get_account_positions(account_id)


@stock_agent.tool
async def tool_get_account_orders(ctx: RunContext, account_id: int) -> str:
    """获取指定模拟账户的委托记录。

    Args:
        account_id: 账户ID
    """
    return await get_account_orders(account_id)


@stock_agent.tool
async def tool_get_stock_news(ctx: RunContext, stock_code: str) -> str:
    """获取指定股票的新闻资讯。

    Args:
        stock_code: 股票代码，格式如 000001.SZ
    """
    return await get_stock_news(stock_code)


@stock_agent.tool
async def tool_get_stock_analysis(ctx: RunContext, stock_code: str) -> str:
    """获取指定股票的分析结果。

    Args:
        stock_code: 股票代码，格式如 000001.SZ
    """
    return await get_stock_analysis(stock_code)


@stock_agent.tool
async def tool_get_strategies(ctx: RunContext) -> str:
    """获取所有量化策略列表。"""
    return await get_strategies()


@stock_agent.tool
async def tool_get_backtest_results(ctx: RunContext) -> str:
    """获取回测结果列表。"""
    return await get_backtest_results()


@stock_agent.tool
async def tool_get_stock_price(ctx: RunContext, stock_code: str) -> str:
    """获取股票实时行情。

    Args:
        stock_code: 股票代码，格式如 000001.SZ
    """
    return await get_stock_price(stock_code)
```

- [ ] **Step 2: Verify agent loads**

Run: `cd /Users/fyq/Desktop/workshop/stock-system/agent-stock && python -c "from agent_stock.agent import stock_agent; print(f'Agent model: {stock_agent.model}'); print(f'Tools: {len(stock_agent.tools)}'); print('OK')"`
Expected: Agent model and tools count printed, then `OK`

- [ ] **Step 3: Commit**

```bash
cd /Users/fyq/Desktop/workshop/stock-system/agent-stock
git add src/agent_stock/agent.py
git commit -m "feat(agent-stock): define Pydantic AI agent with 9 tools"
```

---

### Task 7: FastAPI app + SSE endpoint

**Files:**
- Create: `agent-stock/src/agent_stock/main.py`

- [ ] **Step 1: Create main.py**

```python
from __future__ import annotations

import json
import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from agent_stock.agent import stock_agent
from agent_stock.config import settings
from agent_stock.schemas import ChatRequest, ChatHistoryMessage

logger = logging.getLogger("agent-stock")

app = FastAPI(title="Agent Stock API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _build_message_history(history: list[ChatHistoryMessage]) -> list[dict[str, str]]:
    """Convert ChatHistoryMessage list to Pydantic AI message_history format."""
    return [{"role": msg.role, "content": msg.content} for msg in history]


async def _stream_chat(request: ChatRequest):
    """Generator that yields SSE events from the AI agent."""
    message_history = _build_message_history(request.history)

    try:
        async with stock_agent.run_stream(
            request.message,
            message_history=message_history if message_history else None,
        ) as result:
            async for token in result.stream_text():
                yield {
                    "event": "message",
                    "data": json.dumps({"type": "token", "content": token}, ensure_ascii=False),
                }

            yield {
                "event": "message",
                "data": json.dumps({"type": "done"}, ensure_ascii=False),
            }
    except Exception as e:
        logger.exception("Chat stream error")
        yield {
            "event": "message",
            "data": json.dumps({"type": "error", "content": str(e)}, ensure_ascii=False),
        }


@app.post("/api/chat/stream")
async def api_chat_stream(request: ChatRequest):
    """SSE streaming chat endpoint."""
    return EventSourceResponse(_stream_chat(request))


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "agent-stock"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.agent_host, port=settings.agent_port)
```

- [ ] **Step 2: Add sse-starlette dependency**

Run: `cd /Users/fyq/Desktop/workshop/stock-system/agent-stock && pip install sse-starlette`
Expected: Successfully installed

- [ ] **Step 3: Verify app starts**

Run: `cd /Users/fyq/Desktop/workshop/stock-system/agent-stock && timeout 3 python -c "from agent_stock.main import app; print('FastAPI app created')" 2>&1 || true`
Expected: `FastAPI app created` printed

- [ ] **Step 4: Commit**

```bash
cd /Users/fyq/Desktop/workshop/stock-system/agent-stock
git add src/agent_stock/main.py pyproject.toml
git commit -m "feat(agent-stock): add FastAPI app with SSE streaming endpoint"
```

---

### Task 8: Dockerfile

**Files:**
- Create: `agent-stock/Dockerfile`

- [ ] **Step 1: Create Dockerfile**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

COPY src/ src/

EXPOSE 8001

CMD ["uvicorn", "agent_stock.main:app", "--host", "0.0.0.0", "--port", "8001"]
```

- [ ] **Step 2: Commit**

```bash
cd /Users/fyq/Desktop/workshop/stock-system/agent-stock
git add Dockerfile
git commit -m "feat(agent-stock): add Dockerfile for container deployment"
```

---

### Task 9: Stock backend — config and settings

**Files:**
- Modify: `src/stock_service/infrastructure/config/settings.py`

- [ ] **Step 1: Add agent_stock_url property to Settings class**

Add this property after the `redis_url` property in the `Settings` class (after line 200):

```python
    @property
    def agent_stock_url(self) -> str:
        return self._get("agent_stock_url", lambda: os.getenv("AGENT_STOCK_URL", "http://localhost:8001"))  # type: ignore[return-value]
```

- [ ] **Step 2: Verify import**

Run: `cd /Users/fyq/Desktop/workshop/stock-system/stock && python -c "from stock_service.infrastructure.config.settings import settings; print(f'agent_stock_url: {settings.agent_stock_url}')"`
Expected: `agent_stock_url: http://localhost:8001`

- [ ] **Step 3: Commit**

```bash
cd /Users/fyq/Desktop/workshop/stock-system/stock
git add src/stock_service/infrastructure/config/settings.py
git commit -m "feat: add AGENT_STOCK_URL config to settings"
```

---

### Task 10: Stock backend — chat service

**Files:**
- Create: `src/stock_service/application/services/chat_service.py`

- [ ] **Step 1: Create chat_service.py**

```python
from __future__ import annotations

import json
import logging

import httpx

from stock_service.infrastructure.config.settings import settings

logger = logging.getLogger(__name__)


async def stream_chat(message: str, history: list[dict[str, str]] | None = None):
    """Proxy chat request to agent-stock and yield SSE events.

    Yields SSE-formatted strings for direct use in EventSourceResponse.
    """
    payload = {"message": message}
    if history:
        payload["history"] = history

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{settings.agent_stock_url}/api/chat/stream",
                json=payload,
                headers={"Accept": "text/event-stream"},
            ) as resp:
                if resp.status_code != 200:
                    body = await resp.aread()
                    logger.error("agent-stock returned %d: %s", resp.status_code, body)
                    yield {"event": "message", "data": json.dumps({"type": "error", "content": "AI 服务暂时不可用"}, ensure_ascii=False)}
                    return

                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:]
                        yield {"event": "message", "data": data_str}
                    elif line.startswith("event: "):
                        # Pass through event type
                        pass
    except httpx.ConnectError:
        logger.error("Cannot connect to agent-stock at %s", settings.agent_stock_url)
        yield {"event": "message", "data": json.dumps({"type": "error", "content": "AI 服务未启动"}, ensure_ascii=False)}
    except Exception as e:
        logger.exception("stream_chat error")
        yield {"event": "message", "data": json.dumps({"type": "error", "content": str(e)}, ensure_ascii=False)}
```

- [ ] **Step 2: Verify import**

Run: `cd /Users/fyq/Desktop/workshop/stock-system/stock && python -c "from stock_service.application.services.chat_service import stream_chat; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd /Users/fyq/Desktop/workshop/stock-system/stock
git add src/stock_service/application/services/chat_service.py
git commit -m "feat: add chat service for agent-stock SSE proxy"
```

---

### Task 11: Stock backend — chat route

**Files:**
- Create: `src/stock_service/api/routes/chat.py`
- Modify: `src/stock_service/api/app.py` (register router)

- [ ] **Step 1: Create chat.py route**

```python
from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from stock_service.application.services.chat_service import stream_chat


logger = logging.getLogger("stock-api")
router = APIRouter(tags=["chat"])


class ChatHistoryMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatHistoryMessage] = []


@router.post("/api/chat/send")
async def api_send_message(request: ChatRequest):
    """接收用户消息，转发到 agent-stock，SSE 流式返回"""
    history = [{"role": msg.role, "content": msg.content} for msg in request.history]
    return EventSourceResponse(stream_chat(request.message, history))
```

- [ ] **Step 2: Register router in app.py**

Add these two lines after line 17 (`from stock_service.quant.api.routes import ...`):

```python
from stock_service.api.routes.chat import router as chat_router
```

Add this line after line 85 (`app.include_router(task.router)`):

```python
app.include_router(chat_router)
```

- [ ] **Step 3: Verify app starts**

Run: `cd /Users/fyq/Desktop/workshop/stock-system/stock && python -c "from stock_service.api.app import app; routes = [r.path for r in app.routes]; print('/api/chat/send' in routes)"`
Expected: `True`

- [ ] **Step 4: Commit**

```bash
cd /Users/fyq/Desktop/workshop/stock-system/stock
git add src/stock_service/api/routes/chat.py src/stock_service/api/app.py
git commit -m "feat: add /api/chat/send SSE route proxied to agent-stock"
```

---

### Task 12: Docker Compose — add agent-stock service

**Files:**
- Modify: `stock/docker-compose.yml`

- [ ] **Step 1: Add agent-stock service to docker-compose.yml**

Add the following service after the `stock-web` service block (before the `volumes:` section):

```yaml
  agent-stock:
    build:
      context: ../agent-stock
      dockerfile: Dockerfile
    container_name: agent-stock
    restart: always
    depends_on:
      stock-api:
        condition: service_started
    environment:
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      STOCK_API_URL: http://stock-api:8000
    ports:
      - "8001:8001"
```

- [ ] **Step 2: Verify compose config**

Run: `cd /Users/fyq/Desktop/workshop/stock-system/stock && docker compose config --quiet 2>&1 || echo "VALIDATE FAILED"`
Expected: No output (valid config) or confirmation

- [ ] **Step 3: Commit**

```bash
cd /Users/fyq/Desktop/workshop/stock-system/stock
git add docker-compose.yml
git commit -m "feat: add agent-stock service to docker-compose"
```

---

### Task 13: Frontend — SSE client in api.ts

**Files:**
- Modify: `web-ui/src/utils/api.ts` (chatApi section, lines 444-463)

- [ ] **Step 1: Update chatApi to support SSE**

Replace the `chatApi` block (lines 446-463) with:

```typescript
export interface IntentAction {
  type: 'navigate' | 'query' | 'analyze';
  payload: Record<string, any>;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  actions?: IntentAction[];
  isWelcome?: boolean;
}

export interface ChatChunk {
  type: 'token' | 'done' | 'error';
  content: string;
}

export const chatApi = {
  sendMessage: (message: string, history: { role: string; content: string }[] = []) =>
    fetch('/api/chat/send', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
      },
      body: JSON.stringify({ message, history }),
    }),
};
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd /Users/fyq/Desktop/workshop/stock-system/stock/web-ui && npx tsc --noEmit 2>&1 | head -20`
Expected: No errors related to chatApi

- [ ] **Step 3: Commit**

```bash
cd /Users/fyq/Desktop/workshop/stock-system/stock
git add web-ui/src/utils/api.ts
git commit -m "feat(frontend): update chatApi for SSE streaming"
```

---

### Task 14: Frontend — streaming render in ChatAssistant.tsx

**Files:**
- Modify: `web-ui/src/components/ChatAssistant.tsx`

- [ ] **Step 1: Update handleSend for SSE streaming**

Replace the `handleSend` callback (lines 73-131) with:

```typescript
  const handleSend = useCallback(
    async (text?: string) => {
      const content = (text ?? input).trim();
      if (!content || sendingRef.current) return;

      sendingRef.current = true;
      setLoading(true);

      const userMsg: ChatMessage = {
        id: uuidv4(),
        role: 'user',
        content,
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, userMsg]);
      setInput('');

      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        // Build history from current messages
        const history = [...messages, userMsg].map((m) => ({
          role: m.role,
          content: m.content,
        }));

        const response = await chatApi.sendMessage(content, history);

        if (closedRef.current) return;

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const reader = response.body?.getReader();
        if (!reader) throw new Error('No response body');

        const decoder = new TextDecoder();
        const assistantId = uuidv4();
        let accumulated = '';
        let startedStreaming = false;

        // Add placeholder message for streaming
        setMessages((prev) => [
          ...prev,
          {
            id: assistantId,
            role: 'assistant',
            content: '',
            timestamp: Date.now(),
          },
        ]);

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const text = decoder.decode(value, { stream: true });
          const lines = text.split('\n');

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            const dataStr = line.slice(6).trim();
            if (!dataStr) continue;

            try {
              const chunk: ChatChunk = JSON.parse(dataStr);

              if (chunk.type === 'token') {
                if (!startedStreaming) {
                  startedStreaming = true;
                  setLoading(false);
                }
                accumulated += chunk.content;
                const finalContent = accumulated;
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantId ? { ...m, content: finalContent } : m,
                  ),
                );
              } else if (chunk.type === 'done') {
                break;
              } else if (chunk.type === 'error') {
                accumulated = chunk.content || '抱歉，AI 服务出错了。';
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantId ? { ...m, content: accumulated } : m,
                  ),
                );
              }
            } catch {
              // Skip non-JSON lines
            }
          }
        }
      } catch (err: any) {
        if (err?.name === 'AbortError') return;
        if (closedRef.current) return;
        setMessages((prev) => [
          ...prev,
          {
            id: uuidv4(),
            role: 'assistant',
            content: '抱歉，助手暂时无法响应。请检查 AI 服务是否已启动。',
            timestamp: Date.now(),
          },
        ]);
      } finally {
        sendingRef.current = false;
        setLoading(false);
      }
    },
    [input, messages],
  );
```

- [ ] **Step 2: Update intent action handler**

Replace the `handleAction` callback (lines 134-137) with:

```typescript
  const handleAction = useCallback((action: IntentAction) => {
    switch (action.type) {
      case 'navigate':
        if (action.payload?.path) {
          window.location.href = action.payload.path;
        }
        break;
      case 'query':
        // Trigger a new query with the action payload
        if (action.payload?.query) {
          handleSend(action.payload.query);
        }
        break;
      case 'analyze':
        if (action.payload?.stock_code) {
          window.location.href = `/?stock=${action.payload.stock_code}`;
        }
        break;
      default:
        break;
    }
  }, [handleSend]);
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd /Users/fyq/Desktop/workshop/stock-system/stock/web-ui && npx tsc --noEmit 2>&1 | head -20`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
cd /Users/fyq/Desktop/workshop/stock-system/stock
git add web-ui/src/components/ChatAssistant.tsx
git commit -m "feat(frontend): add SSE streaming render to ChatAssistant"
```

---

### Task 15: End-to-end verification

- [ ] **Step 1: Start agent-stock locally**

Run: `cd /Users/fyq/Desktop/workshop/stock-system/agent-stock && python -m agent_stock.main`
Expected: Server starts on port 8001

- [ ] **Step 2: Test health endpoint**

Run: `curl -s http://localhost:8001/api/health`
Expected: `{"status":"ok","service":"agent-stock"}`

- [ ] **Step 3: Test chat stream (requires OPENAI_API_KEY)**

Run: `curl -N -X POST http://localhost:8001/api/chat/stream -H "Content-Type: application/json" -d '{"message":"你好"}'`
Expected: SSE stream with token events

- [ ] **Step 4: Test stock backend proxy (requires both services running)**

Run: `curl -N -X POST http://localhost:8000/api/chat/send -H "Content-Type: application/json" -d '{"message":"查看今日热门股票"}'`
Expected: SSE stream proxied through stock backend

- [ ] **Step 5: Stop test servers**

Kill any running processes started in Step 1.

- [ ] **Step 6: Final commit**

```bash
cd /Users/fyq/Desktop/workshop/stock-system/stock
git add -A
git commit -m "feat: complete AI assistant integration (agent-stock + backend proxy + frontend)"
```
