from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from stock_service.api.auth_cookies import clear_refresh_cookie, set_refresh_cookie
from stock_service.api.dependencies import get_current_user, get_session
from stock_service.application.services import auth_service
from stock_service.infrastructure.config.settings import settings
from stock_service.schemas.responses import ApiResponse


logger = logging.getLogger("stock-api")
router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)


class LoginRequest(BaseModel):
    username: str
    password: str


def _tokens_public_payload(tokens: dict) -> dict:
    """响应 JSON 仅包含 access_token，refresh 只走 HttpOnly Cookie。"""
    return {
        "access_token": tokens["access_token"],
        "token_type": tokens["token_type"],
    }


@router.post("/register", response_model=ApiResponse, status_code=201)
async def api_register(body: RegisterRequest, session: AsyncSession = Depends(get_session)) -> ApiResponse:
    try:
        user = await auth_service.register(session, body.username, body.password)
        return ApiResponse(data=user)
    except ValueError as exc:
        if "已被注册" in str(exc):
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/login", response_model=ApiResponse)
async def api_login(
    body: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    try:
        tokens = await auth_service.login(session, body.username, body.password)
        refresh = tokens["refresh_token"]
        set_refresh_cookie(response, refresh)
        return ApiResponse(data=_tokens_public_payload(tokens))
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.post("/refresh", response_model=ApiResponse)
async def api_refresh(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    refresh_token = request.cookies.get(settings.jwt_refresh_cookie_name)
    if not refresh_token:
        raise HTTPException(status_code=401, detail="未登录或 refresh 已过期")
    try:
        tokens = await auth_service.refresh(session, refresh_token)
        set_refresh_cookie(response, tokens["refresh_token"])
        return ApiResponse(data=_tokens_public_payload(tokens))
    except ValueError as exc:
        clear_refresh_cookie(response)
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.post("/logout", response_model=ApiResponse)
async def api_logout(
    request: Request,
    response: Response,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    refresh_token = request.cookies.get(settings.jwt_refresh_cookie_name)
    if refresh_token:
        await auth_service.logout(session, current_user.id, refresh_token)
    clear_refresh_cookie(response)
    return ApiResponse(data=None)


@router.get("/me", response_model=ApiResponse)
async def api_me(current_user: dict = Depends(get_current_user)) -> ApiResponse:
    return ApiResponse(data={"id": current_user.id, "username": current_user.username})
