from __future__ import annotations

import os
from pathlib import Path


def _load_dotenv() -> None:
    candidate_paths: list[Path] = []

    explicit_path = os.getenv("STOCK_ENV_FILE", "").strip()
    if explicit_path:
        candidate_paths.append(Path(explicit_path).expanduser())

    cwd_env = Path.cwd() / ".env"
    candidate_paths.append(cwd_env)

    source_root_env = Path(__file__).resolve().parents[4] / ".env"
    candidate_paths.append(source_root_env)

    seen: set[Path] = set()
    for env_path in candidate_paths:
        resolved = env_path.resolve()
        if resolved in seen or not resolved.exists():
            continue
        seen.add(resolved)
        for line in resolved.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())
        break


def _get_required_env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None or not str(value).strip():
        raise RuntimeError(f"缺少环境变量: {name}")
    return str(value).strip()


def _get_int_env(name: str, default: str) -> int:
    raw_value = _get_required_env(name, default)
    try:
        return int(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"环境变量无效: {name}={raw_value!r}") from exc


def _parse_db_ssl() -> bool | None:
    """asyncpg：本机 PostgreSQL 常未开 SSL，若按客户端默认去握手易卡住直至超时。默认关闭 SSL。"""
    raw = os.getenv("DB_SSL", "disable").strip().lower()
    if raw in ("require", "true", "1", "on"):
        return True
    if raw in ("prefer",):
        return None
    return False


def _get_bool_env(name: str, default: str) -> bool:
    raw = _get_required_env(name, default).strip().lower()
    return raw in ("1", "true", "yes", "on")


def _get_samesite_env(name: str, default: str = "lax") -> str:
    raw = _get_required_env(name, default).strip().lower()
    if raw not in {"lax", "strict", "none"}:
        raise RuntimeError(f"环境变量无效: {name}={raw!r}，可选值为 lax/strict/none")
    return raw


def _get_csv_env(name: str, default: str) -> tuple[str, ...]:
    raw = _get_required_env(name, default)
    items = [item.strip() for item in raw.split(",") if item.strip()]
    return tuple(items)


def _resolve_db_env() -> None:
    """根据 APP_ENV 加载对应的数据库配置。

    APP_ENV=dev  → 读 TEST_DB_* 并覆盖到 DB_*
    APP_ENV=prod → 直接读 DB_*（默认行为）
    """
    app_env = os.getenv("APP_ENV", "prod").strip().lower()
    if app_env != "dev":
        return
    mapping = {
        "TEST_DB_HOST": "DB_HOST",
        "TEST_DB_PORT": "DB_PORT",
        "TEST_DB_NAME": "DB_NAME",
        "TEST_DB_USER": "DB_USER",
        "TEST_DB_PASSWORD": "DB_PASSWORD",
        "TEST_DB_SSL": "DB_SSL",
    }
    for src, dst in mapping.items():
        val = os.getenv(src)
        if val is not None:
            os.environ[dst] = val


_load_dotenv()
_resolve_db_env()


class Settings:
    db_host = _get_required_env("DB_HOST", "127.0.0.1")
    db_port = _get_int_env("DB_PORT", "5432")
    db_name = _get_required_env("DB_NAME", "stock_db")
    db_user = _get_required_env("DB_USER", "postgres")
    db_password = _get_required_env("DB_PASSWORD", "")
    db_ssl = _parse_db_ssl()
    db_connect_timeout = _get_int_env("DB_CONNECT_TIMEOUT", "90")
    ths_query = _get_required_env("THS_POPULARITY_QUERY", "人气排名前200")
    ths_cookie = os.getenv("THS_COOKIE", "").strip()
    jwt_secret_key = _get_required_env("JWT_SECRET_KEY", "change-me-in-production")
    jwt_access_expire_minutes = _get_int_env("JWT_ACCESS_EXPIRE_MINUTES", "30")
    jwt_refresh_expire_days = _get_int_env("JWT_REFRESH_EXPIRE_DAYS", "7")
    jwt_refresh_cookie_name = _get_required_env("JWT_REFRESH_COOKIE_NAME", "stock_refresh_token")
    cookie_secure = _get_bool_env("COOKIE_SECURE", "false")
    cookie_samesite = _get_samesite_env("COOKIE_SAMESITE", "lax")
    market_quote_providers = _get_csv_env("MARKET_QUOTE_PROVIDERS", "tencent")
    market_fetch_concurrency = _get_int_env("MARKET_FETCH_CONCURRENCY", "5")
    news_fetch_concurrency = _get_int_env("NEWS_FETCH_CONCURRENCY", "5")


settings = Settings()


DATABASE_CONFIG = {
    "host": settings.db_host,
    "port": settings.db_port,
    "database": settings.db_name,
    "user": settings.db_user,
    "password": settings.db_password,
    "ssl": settings.db_ssl,
    "timeout": float(settings.db_connect_timeout),
}
