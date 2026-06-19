from __future__ import annotations

import logging

from fastapi import APIRouter, Request
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
async def api_send_message(request: ChatRequest, http_request: Request):
    """接收用户消息，转发到 agent-stock，SSE 流式返回"""
    history = [{"role": msg.role, "content": msg.content} for msg in request.history]
    auth_header = http_request.headers.get("authorization", "")
    return EventSourceResponse(stream_chat(request.message, history, auth_header))
