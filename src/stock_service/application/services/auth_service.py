from datetime import datetime, timedelta, timezone
from uuid import uuid4

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from stock_service.crud import auth_crud
from stock_service.infrastructure.config.settings import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: int, username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_expire_minutes)
    payload = {
        "sub": str(user_id),
        "username": username,
        "type": "access",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=ALGORITHM)


def create_refresh_token(user_id: int, username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_expire_days)
    payload = {
        "sub": str(user_id),
        "username": username,
        "type": "refresh",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": uuid4().hex,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[ALGORITHM])
    except JWTError:
        return None


def hash_token(token: str) -> str:
    import hashlib
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def register(session: AsyncSession, username: str, password: str) -> dict:
    existing = await auth_crud.get_user_by_username(session, username)
    if existing:
        raise ValueError("用户名已被注册")
    password_hash = hash_password(password)
    return await auth_crud.create_user(session, username=username, password_hash=password_hash)


async def login(session: AsyncSession, username: str, password: str) -> dict:
    user = await auth_crud.get_user_by_username(session, username)
    if not user or not verify_password(password, user.password_hash):
        raise ValueError("用户名或密码错误")

    access_token = create_access_token(user.id, user.username)
    refresh_token = create_refresh_token(user.id, user.username)
    refresh_hash = hash_token(refresh_token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_expire_days)
    await auth_crud.save_refresh_token(session, user_id=user.id, token_hash=refresh_hash, expires_at=expires_at)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


async def refresh(session: AsyncSession, refresh_token: str) -> dict:
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise ValueError("refresh token 无效或已过期")

    token_hash = hash_token(refresh_token)
    stored_token = await auth_crud.get_refresh_token(session, token_hash)

    if not stored_token:
        # Token 不在数据库中，可能已被使用（轮换检测）
        user_id = int(payload["sub"])
        await auth_crud.delete_all_user_refresh_tokens(session, user_id)
        raise ValueError("refresh token 已失效，请重新登录")

    if stored_token.expires_at < datetime.now(timezone.utc):
        await auth_crud.delete_refresh_token(session, stored_token.id)
        raise ValueError("refresh token 无效或已过期")

    # 轮换：删除旧 token，生成新的
    user_id = int(payload["sub"])
    username = payload.get("username", "")
    await auth_crud.delete_refresh_token(session, stored_token.id)

    new_access = create_access_token(user_id, username)
    new_refresh = create_refresh_token(user_id, username)
    new_hash = hash_token(new_refresh)
    new_expires = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_expire_days)
    await auth_crud.save_refresh_token(session, user_id=user_id, token_hash=new_hash, expires_at=new_expires)

    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
    }


async def logout(session: AsyncSession, user_id: int, refresh_token: str) -> None:
    token_hash = hash_token(refresh_token)
    stored_token = await auth_crud.get_refresh_token(session, token_hash)
    if stored_token and stored_token.user_id == user_id:
        await auth_crud.delete_refresh_token(session, stored_token.id)
