from __future__ import annotations


def __getattr__(name: str):
    if name in ("get_async_session", "async_engine", "AsyncSessionFactory"):
        from stock_service.db.database import get_async_session, async_engine, AsyncSessionFactory
        return locals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["get_async_session", "async_engine", "AsyncSessionFactory"]
