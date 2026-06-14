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
    except Exception:
        logger.exception("stream_chat error")
        yield {"event": "message", "data": json.dumps({"type": "error", "content": "AI 服务处理出错，请稍后重试"}, ensure_ascii=False)}
