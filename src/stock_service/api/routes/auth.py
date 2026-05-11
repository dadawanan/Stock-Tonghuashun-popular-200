from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from stock_service.api.dependencies import get_current_user, get_session
from stock_service.application.services import auth_service
from stock_service.schemas.responses import ApiResponse


logger = logging.getLogger("stock-api")
router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


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
async def api_login(body: LoginRequest, session: AsyncSession = Depends(get_session)) -> ApiResponse:
    try:
        tokens = await auth_service.login(session, body.username, body.password)
        return ApiResponse(data=tokens)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.post("/refresh", response_model=ApiResponse)
async def api_refresh(body: RefreshRequest, session: AsyncSession = Depends(get_session)) -> ApiResponse:
    try:
        tokens = await auth_service.refresh(session, body.refresh_token)
        return ApiResponse(data=tokens)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.post("/logout", response_model=ApiResponse)
async def api_logout(
    body: LogoutRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    await auth_service.logout(session, current_user.id, body.refresh_token)
    return ApiResponse(data=None)


@router.get("/me", response_model=ApiResponse)
async def api_me(current_user: dict = Depends(get_current_user)) -> ApiResponse:
    return ApiResponse(data={"id": current_user.id, "username": current_user.username})
