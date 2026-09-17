"""Discord interaction orchestration and real TA handoff."""

from __future__ import annotations

from typing import Any

import discord

from .api_client import assist
from .config import BotConfig
from .embeds import ResponseView


class DiscordAssistant:
    def __init__(self, config: BotConfig):
        self.config = config

    async def answer_to_interaction(self, interaction: discord.Interaction, question: str, *, source_message: discord.Message | None = None) -> None:
        if not question.strip():
            await interaction.followup.send("Bạn hãy nhập câu hỏi sau `/ask`.", ephemeral=True)
            return
        try:
            response = await assist(
                self.config.core_ai_url,
                user_id=str(interaction.user.id),
                channel_id=str(getattr(interaction.channel, "id", self.config.channel_id)),
                message_text=question.strip(),
            )
            view = ResponseView(
                response=response,
                question=question.strip(),
                source_map=self.config.source_map,
                server_id=self.config.server_id,
                on_question=self.answer_followup,
                handoff_handler=self.create_handoff,
                source_message=source_message,
            )
            reply_text = str(response.get("reply_text", ""))
            await interaction.followup.send(content=reply_text, view=view)
        except RuntimeError as error:
            await interaction.followup.send(f"Mình chưa kết nối được Core AI: {error}", ephemeral=True)

    async def answer_followup(self, interaction: discord.Interaction, question: str) -> None:
        if not interaction.response.is_done():
            await interaction.response.defer()
        channel = interaction.channel
        if channel is not None:
            async with channel.typing():
                await self.answer_to_interaction(interaction, question)
        else:
            await self.answer_to_interaction(interaction, question)

    async def create_handoff(self, interaction: discord.Interaction, question: str, response: dict[str, Any], *, source_message: discord.Message | None = None) -> None:
        if not interaction.response.is_done():
            await interaction.response.defer()
        channel = interaction.channel
        if channel is None:
            await interaction.followup.send("Không xác định được kênh để chuyển TA.", ephemeral=True)
            return
        reason = (response.get("handoff_metadata") or {}).get("reason") or "unsupported_or_no_ground_truth"
        try:
            role = channel.guild.get_role(self.config.ta_role_id) if channel.guild else None
            mention = f"<@{self.config.ta_user_id}>" if self.config.ta_user_id else (role.mention if role else f"<@&{self.config.ta_role_id}>")
            content = f"{mention} cần kiểm tra case này.\n**Lý do:** `{reason}`"
            if source_message is not None:
                await source_message.reply(content)
            else:
                await channel.send(content)
        except (discord.Forbidden, discord.HTTPException):
            await interaction.followup.send("Mình không có quyền tag TA hoặc reply trong kênh này.", ephemeral=True)
