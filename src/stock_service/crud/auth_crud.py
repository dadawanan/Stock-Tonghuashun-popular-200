from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stock_service.db.models.v2_models import RefreshToken, User


async def create_user(session: AsyncSession, *, username: str, password_hash: str) -> dict:
    user = User(username=username, password_hash=password_hash)
    session.add(user)
    await session.flush()
    return {"id": user.id, "username": user.username}


async def get_user_by_username(session: AsyncSession, username: str) -> User | None:
    result = await session.execute(select(User).where(User.username == username))
    return result.scalars().first()


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    return await session.get(User, user_id)


async def save_refresh_token(session: AsyncSession, *, user_id: int, token_hash: str, expires_at: datetime) -> None:
    token = RefreshToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
    session.add(token)


async def get_refresh_token(session: AsyncSession, token_hash: str) -> RefreshToken | None:
    result = await session.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    return result.scalars().first()


async def delete_refresh_token(session: AsyncSession, token_id: int) -> None:
    token = await session.get(RefreshToken, token_id)
    if token:
        await session.delete(token)


async def delete_all_user_refresh_tokens(session: AsyncSession, user_id: int) -> None:
    result = await session.execute(select(RefreshToken).where(RefreshToken.user_id == user_id))
    for token in result.scalars().all():
        await session.delete(token)
