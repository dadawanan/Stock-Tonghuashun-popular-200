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


_load_dotenv()


class Settings:
    db_host = _get_required_env("DB_HOST", "127.0.0.1")
    db_port = _get_int_env("DB_PORT", "5432")
    db_name = _get_required_env("DB_NAME", "stock_db")
    db_user = _get_required_env("DB_USER", "postgres")
    db_password = _get_required_env("DB_PASSWORD", "")
    ths_query = _get_required_env("THS_POPULARITY_QUERY", "人气排名前200")
    ths_cookie = os.getenv("THS_COOKIE", "").strip()


settings = Settings()


DATABASE_CONFIG = {
    "host": settings.db_host,
    "port": settings.db_port,
    "database": settings.db_name,
    "user": settings.db_user,
    "password": settings.db_password,
}
