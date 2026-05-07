from __future__ import annotations

from typing import Any

import asyncpg


class BaseRepository:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    @staticmethod
    def rows_to_dicts(rows: list[Any]) -> list[dict[str, Any]]:
        return [dict(row) for row in rows]

