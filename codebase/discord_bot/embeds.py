"""Discord presentation layer for AgentResponse objects."""

from __future__ import annotations

import hashlib
from typing import Any, Awaitable, Callable

import discord

from .links import source_jump_url

QuestionHandler = Callable[[discord.Interaction, str], Awaitable[None]]


def _status_color(response: dict[str, Any]) -> int:
    reason = (response.get("handoff_metadata") or {}).get("reason")
    if reason == "conflicting_sources":
        return 0xF0A000
    return {
        "answered": 0x23A559,
        "clarification_needed": 0xF0B232,
        "rejected": 0x9B59B6,
        "ta_handoff": 0xED4245,
    }.get(str(response.get("status")), 0x5865F2)


def _source_text(citation: dict[str, Any]) -> str:
    return f"{citation.get('channel', 'kênh nguồn')} · {citation.get('message_id', 'không có message ID')}"


class ResponseView(discord.ui.View):
    def __init__(self, *, response: dict[str, Any], question: str, source_map: dict[str, tuple[int, int]], server_id: int, on_question: QuestionHandler, handoff_handler: Callable[..., Awaitable[None]], source_message: discord.Message | None = None, timeout: float = 900):
        super().__init__(timeout=timeout)
        self.response = response
        self.question = question
        self.on_question = on_question
        self.handoff_handler = handoff_handler
        self.source_message = source_message
        citation = response.get("source_citation")
        jump_url = source_jump_url(server_id, citation, source_map)
        if jump_url:
            self.add_item(discord.ui.Button(label="Mở thông báo nguồn", style=discord.ButtonStyle.link, url=jump_url))
        interactive = response.get("interactive_elements") or {}
        for index, option in enumerate(interactive.get("options", []), start=1):
            action = option.get("action")
            value = option.get("value") or option.get("label", "")
            if action == "show_ticket_help":
                self.add_item(TicketButton())
            elif action == "trigger_ta_handoff":
                self.add_item(HandoffButton(handoff_handler, question, response, source_message=source_message))
            elif interactive.get("type") == "chips":
                self.add_item(ClarificationButton(on_question, index, option.get("label", value), value))


class ClarificationButton(discord.ui.Button):
    def __init__(self, handler: QuestionHandler, index: int, label: str, value: str):
        super().__init__(label=f"{index} · {label}"[:80], style=discord.ButtonStyle.secondary, custom_id=f"clarify:{value[:80]}")
        self.handler = handler
        self.value = value

    async def callback(self, interaction: discord.Interaction) -> None:
        await self.handler(interaction, self.value)


class HandoffButton(discord.ui.Button):
    def __init__(self, handler: Callable[..., Awaitable[None]], question: str, response: dict[str, Any], *, source_message: discord.Message | None = None):
        request_id = hashlib.sha256(question.encode("utf-8")).hexdigest()[:16]
        super().__init__(label="Chuyển cho TA hỗ trợ", style=discord.ButtonStyle.danger, custom_id=f"handoff:{request_id}")
        self.handler = handler
        self.question = question
        self.response = response
        self.source_message = source_message

    async def callback(self, interaction: discord.Interaction) -> None:
        await self.handler(interaction, self.question, self.response, source_message=self.source_message)


class TicketButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Mở hướng dẫn /ticket create", style=discord.ButtonStyle.primary, custom_id="ticket:create")

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message("Hãy dùng `/ticket create` tại kênh #ticket-support để TA xử lý.", ephemeral=True)


def response_embed(response: dict[str, Any], *, bot_name: str) -> discord.Embed:
    """Render only the optional source block; the answer itself is plain text."""
    embed = discord.Embed(color=_status_color(response))
    embed.set_author(name="Nguồn tham khảo")
    citation = response.get("source_citation") or {}
    embed.description = _source_text(citation)
    return embed


def clarification_embed(response: dict[str, Any], *, bot_name: str) -> discord.Embed:
    embed = discord.Embed(
        description=str(response.get("reply_text", "Bạn hãy chọn một lựa chọn bên dưới.")),
        color=_status_color(response),
    )
    embed.set_author(name=bot_name)
    return embed
