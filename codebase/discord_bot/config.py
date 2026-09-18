"""Environment-backed configuration for the Discord adapter."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field


def _required_int(name: str) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    try:
        return int(value)
    except ValueError as error:
        raise RuntimeError(f"{name} must be a Discord snowflake integer") from error


def _optional_int(name: str) -> int | None:
    value = os.getenv(name, "").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError as error:
        raise RuntimeError(f"{name} must be a Discord snowflake integer") from error


@dataclass(frozen=True)
class BotConfig:
    token: str = field(repr=False)
    server_id: int
    channel_id: int
    ta_role_id: int
    ta_user_id: int | None
    bot_name: str
    core_ai_url: str
    source_map: dict[str, tuple[int, int]]

    @classmethod
    def from_env(cls) -> "BotConfig":
        token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
        if not token:
            raise RuntimeError("DISCORD_BOT_TOKEN is required")
        source_map_raw = os.getenv("DISCORD_SOURCE_MAP_JSON", "{}").strip() or "{}"
        try:
            raw_map = json.loads(source_map_raw)
        except json.JSONDecodeError as error:
            raise RuntimeError("DISCORD_SOURCE_MAP_JSON must be valid JSON") from error
        if not isinstance(raw_map, dict):
            raise RuntimeError("DISCORD_SOURCE_MAP_JSON must be an object")
        source_map: dict[str, tuple[int, int]] = {}
        for source_id, value in raw_map.items():
            if not isinstance(source_id, str) or not isinstance(value, dict):
                raise RuntimeError("Each source map entry must contain an object")
            try:
                source_map[source_id] = (int(value["channel_id"]), int(value["message_id"]))
            except (KeyError, TypeError, ValueError) as error:
                raise RuntimeError(f"Invalid Discord mapping for {source_id}") from error
        return cls(
            token=token,
            server_id=_required_int("DISCORD_SERVER_ID"),
            channel_id=_required_int("DISCORD_CHANNEL_ID"),
            ta_role_id=_required_int("DISCORD_TA_ROLE_ID"),
            ta_user_id=_optional_int("DISCORD_TA_USER_ID"),
            bot_name=os.getenv("DISCORD_BOT_NAME", "Trợ lý").strip() or "Trợ lý",
            core_ai_url=os.getenv("CORE_AI_URL", "http://localhost:8000").rstrip("/"),
            source_map=source_map,
        )
