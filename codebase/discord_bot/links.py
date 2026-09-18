"""Pure helpers for Discord source jump links."""

from __future__ import annotations

from typing import Any


def source_jump_url(server_id: int, citation: dict[str, Any] | None, source_map: dict[str, tuple[int, int]]) -> str | None:
    if not citation:
        return None
    source_id = citation.get("ground_truth_id")
    mapped = source_map.get(source_id)
    if not mapped:
        return None
    channel_id, message_id = mapped
    return f"https://discord.com/channels/{server_id}/{channel_id}/{message_id}"
