from __future__ import annotations

import os
from pathlib import Path
from typing import Any


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


def _get_float_env(name: str, default: str) -> float:
    raw_value = _get_required_env(name, default)
    try:
        return float(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"环境变量无效: {name}={raw_value!r}") from exc


def _parse_db_ssl() -> bool | None:
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


_initialized = False


def _ensure_initialized() -> None:
    """惰性初始化：首次访问时才加载 .env 并解析环境变量"""
    global _initialized
    if _initialized:
        return
    _initialized = True
    _load_dotenv()
    _resolve_db_env()


class Settings:
    """惰性 Settings：属性首次被访问时才读取环境变量"""

    def __init__(self) -> None:
        self._cache: dict[str, object] = {}

    def _get(self, key: str, loader) -> object:
        if key not in self._cache:
            _ensure_initialized()
            self._cache[key] = loader()
        return self._cache[key]

    @property
    def db_host(self) -> str:
        return self._get("db_host", lambda: _get_required_env("DB_HOST", "127.0.0.1"))  # type: ignore[return-value]

    @property
    def db_port(self) -> int:
        return self._get("db_port", lambda: _get_int_env("DB_PORT", "5432"))  # type: ignore[return-value]

    @property
    def db_name(self) -> str:
        return self._get("db_name", lambda: _get_required_env("DB_NAME", "stock_db"))  # type: ignore[return-value]

    @property
    def db_user(self) -> str:
        return self._get("db_user", lambda: _get_required_env("DB_USER", "postgres"))  # type: ignore[return-value]

    @property
    def db_password(self) -> str:
        return self._get("db_password", lambda: _get_required_env("DB_PASSWORD", ""))  # type: ignore[return-value]

    @property
    def db_ssl(self) -> bool | None:
        return self._get("db_ssl", _parse_db_ssl)  # type: ignore[return-value]

    @property
    def db_connect_timeout(self) -> int:
        return self._get("db_connect_timeout", lambda: _get_int_env("DB_CONNECT_TIMEOUT", "90"))  # type: ignore[return-value]

    @property
    def ths_query(self) -> str:
        return self._get("ths_query", lambda: _get_required_env("THS_POPULARITY_QUERY", "人气排名前200"))  # type: ignore[return-value]

    @property
    def ths_cookie(self) -> str:
        return self._get("ths_cookie", lambda: os.getenv("THS_COOKIE", "").strip())  # type: ignore[return-value]

    @property
    def jwt_secret_key(self) -> str:
        return self._get("jwt_secret_key", lambda: _get_required_env("JWT_SECRET_KEY", "change-me-in-production"))  # type: ignore[return-value]

    @property
    def jwt_access_expire_minutes(self) -> int:
        return self._get("jwt_access_expire_minutes", lambda: _get_int_env("JWT_ACCESS_EXPIRE_MINUTES", "30"))  # type: ignore[return-value]

    @property
    def jwt_refresh_expire_days(self) -> int:
        return self._get("jwt_refresh_expire_days", lambda: _get_int_env("JWT_REFRESH_EXPIRE_DAYS", "7"))  # type: ignore[return-value]

    @property
    def jwt_refresh_cookie_name(self) -> str:
        return self._get("jwt_refresh_cookie_name", lambda: _get_required_env("JWT_REFRESH_COOKIE_NAME", "stock_refresh_token"))  # type: ignore[return-value]

    @property
    def cookie_secure(self) -> bool:
        return self._get("cookie_secure", lambda: _get_bool_env("COOKIE_SECURE", "false"))  # type: ignore[return-value]

    @property
    def cookie_samesite(self) -> str:
        return self._get("cookie_samesite", lambda: _get_samesite_env("COOKIE_SAMESITE", "lax"))  # type: ignore[return-value]

    @property
    def market_quote_providers(self) -> tuple[str, ...]:
        return self._get("market_quote_providers", lambda: _get_csv_env("MARKET_QUOTE_PROVIDERS", "tencent"))  # type: ignore[return-value]

    @property
    def market_fetch_concurrency(self) -> int:
        return self._get("market_fetch_concurrency", lambda: _get_int_env("MARKET_FETCH_CONCURRENCY", "5"))  # type: ignore[return-value]

    @property
    def news_fetch_concurrency(self) -> int:
        return self._get("news_fetch_concurrency", lambda: _get_int_env("NEWS_FETCH_CONCURRENCY", "5"))  # type: ignore[return-value]

    @property
    def redis_url(self) -> str:
        return self._get("redis_url", lambda: _get_required_env("REDIS_URL", "redis://localhost:6379/0"))  # type: ignore[return-value]

    @property
    def agent_stock_url(self) -> str:
        return self._get("agent_stock_url", lambda: os.getenv("AGENT_STOCK_URL", "http://localhost:8001"))  # type: ignore[return-value]

    # -----------------------------------------------------------------------
    # 代理配置 — Tailscale + Clash Verge 反爬代理
    # -----------------------------------------------------------------------
    @property
    def proxy_host(self) -> str:
        """Tailscale 对端 IP（家庭电脑的 100.x.x.x 地址）。为空则不使用代理。"""
        return self._get("proxy_host", lambda: os.getenv("PROXY_HOST", "").strip())  # type: ignore[return-value]

    @property
    def proxy_port(self) -> int:
        """Clash Verge 局域网共享端口，默认 7890。"""
        return self._get("proxy_port", lambda: _get_int_env("PROXY_PORT", "7890"))  # type: ignore[return-value]

    @property
    def proxy_timeout(self) -> float:
        """请求超时秒数，默认 30。"""
        return self._get("proxy_timeout", lambda: _get_float_env("PROXY_TIMEOUT", "30"))  # type: ignore[return-value]

    @property
    def proxy_delay_min(self) -> float:
        """随机延迟最小秒数，默认 0.3。"""
        return self._get("proxy_delay_min", lambda: _get_float_env("PROXY_DELAY_MIN", "0.3"))  # type: ignore[return-value]

    @property
    def proxy_delay_max(self) -> float:
        """随机延迟最大秒数，默认 1.2。"""
        return self._get("proxy_delay_max", lambda: _get_float_env("PROXY_DELAY_MAX", "1.2"))  # type: ignore[return-value]


settings = Settings()


def get_database_config() -> dict:
    """惰性获取数据库配置（首次调用时才读取环境变量）"""
    return {
        "host": settings.db_host,
        "port": settings.db_port,
        "database": settings.db_name,
        "user": settings.db_user,
        "password": settings.db_password,
        "ssl": settings.db_ssl,
        "timeout": float(settings.db_connect_timeout),
    }


# 兼容旧代码：模块级别变量，但延迟求值
class _LazyConfig:
    def __getitem__(self, key: str) -> Any:
        return get_database_config()[key]
    def get(self, key: str, default: Any = None) -> Any:
        return get_database_config().get(key, default)
    def __repr__(self) -> str:
        return repr(get_database_config())

DATABASE_CONFIG = _LazyConfig()
