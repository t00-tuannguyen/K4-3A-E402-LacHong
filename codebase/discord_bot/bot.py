"""Run the real Discord adapter.

From the repository root:
    python3 -m codebase.discord_bot.bot
"""

from __future__ import annotations

import os
import re

import discord
from discord import app_commands
from dotenv import load_dotenv

from .config import BotConfig
from .interactions import DiscordAssistant


load_dotenv()
config = BotConfig.from_env()
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)
assistant = DiscordAssistant(config)


@tree.command(name="ask", description="Hỏi Trợ lý về deadline và thủ tục K4")
@app_commands.describe(question="Câu hỏi về deadline hoặc quy định")
async def ask(interaction: discord.Interaction, question: str) -> None:
    await interaction.response.defer()
    await assistant.answer_to_interaction(interaction, question)


@bot.event
async def on_ready() -> None:
    guild = discord.Object(id=config.server_id)
    tree.copy_global_to(guild=guild)
    await tree.sync(guild=guild)
    print(f"Discord bot ready as {bot.user} in guild {config.server_id}")


@bot.event
async def on_message(message: discord.Message) -> None:
    if message.author.bot or bot.user is None or bot.user not in message.mentions:
        return
    question = re.sub(rf"<@!?{bot.user.id}>\s*", "", message.content).strip()
    interaction_message = _MessageInteraction(message)
    async with message.channel.typing():
        await assistant.answer_to_interaction(interaction_message.interaction, question, source_message=message)


class _MessageInteraction:
    """Small adapter so the same renderer can answer a mention message.

    The first implementation uses a webhook-like followup shim; slash commands
    remain the canonical path until the mention responder is upgraded to a
    native message-context response object.
    """

    def __init__(self, message: discord.Message):
        self.interaction = _MentionInteraction(message)


class _MentionInteraction:
    def __init__(self, message: discord.Message):
        self.user = message.author
        self.channel = message.channel
        self.followup = _MessageFollowup(message)
        self.response = _DoneResponse()


class _DoneResponse:
    def is_done(self) -> bool:
        return True


class _MessageFollowup:
    def __init__(self, message: discord.Message):
        self.message = message

    async def send(self, content: str | None = None, *, embed: discord.Embed | None = None, view: discord.ui.View | None = None, ephemeral: bool = False) -> discord.Message:
        return await self.message.reply(
            content=content,
            embed=embed,
            view=view,
            mention_author=False,
        )


if __name__ == "__main__":
    bot.run(config.token)
