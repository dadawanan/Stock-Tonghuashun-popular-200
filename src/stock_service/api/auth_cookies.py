"""Refresh token 仅通过 HttpOnly Cookie 传递，JSON 响应体不包含 refresh_token。"""

from __future__ import annotations

from starlette.responses import Response

from stock_service.infrastructure.config.settings import settings


def set_refresh_cookie(response: Response, refresh_token: str) -> None:
    max_age = settings.jwt_refresh_expire_days * 86400
    response.set_cookie(
        key=settings.jwt_refresh_cookie_name,
        value=refresh_token,
        max_age=max_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=settings.jwt_refresh_cookie_name, path="/")
