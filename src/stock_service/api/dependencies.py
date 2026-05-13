from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from stock_service.db.database import AsyncSessionFactory
from stock_service.db.models.v2_models import User
from stock_service.infrastructure.config.settings import settings


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_session),
) -> User:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="未授权")
        user_id = int(payload["sub"])
    except (JWTError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="未授权") from exc

    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="未授权")
    return user


@asynccontextmanager
async def lifespan(_: object):
    yield
