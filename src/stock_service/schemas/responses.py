from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ApiResponse(BaseModel):
    code: int = 0
    msg: str = ""
    data: Any = None

