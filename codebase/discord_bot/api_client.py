"""Small async HTTP client for the existing Core AI contract."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from typing import Any


def _post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = Request(
        f"{url.rstrip('/')}/api/assist",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            result = json.load(response)
    except HTTPError as error:
        raise RuntimeError(f"Core AI returned HTTP {error.code}") from error
    except URLError as error:
        raise RuntimeError("Không thể kết nối Core AI") from error
    if not isinstance(result, dict):
        raise RuntimeError("Core AI returned an invalid response")
    return result


async def assist(core_ai_url: str, *, user_id: str, channel_id: str, message_text: str) -> dict[str, Any]:
    payload = {
        "user_id": user_id,
        "channel_id": channel_id,
        "message_text": message_text,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return await asyncio.to_thread(_post_json, core_ai_url, payload)
