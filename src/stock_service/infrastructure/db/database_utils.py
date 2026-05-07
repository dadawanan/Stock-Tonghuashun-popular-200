from __future__ import annotations

import json
from typing import Any


def to_json_text(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)
