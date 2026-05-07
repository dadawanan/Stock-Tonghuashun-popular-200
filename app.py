"""ASGI entrypoint for `uvicorn app:app` when run from the repository root."""

from __future__ import annotations

import sys
from pathlib import Path

_src = Path(__file__).resolve().parent / "src"
if _src.is_dir():
    path = str(_src)
    if path not in sys.path:
        sys.path.insert(0, path)

from stock_service.api.app import app

__all__ = ["app"]
