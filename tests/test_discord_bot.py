import os
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from codebase.discord_bot.config import BotConfig
from codebase.discord_bot.interactions import DiscordAssistant
from codebase.discord_bot.links import source_jump_url


class DiscordBotConfigTests(unittest.TestCase):
    def test_config_parses_ids_and_source_mapping_without_exposing_token(self):
        values = {
            "DISCORD_BOT_TOKEN": "secret-token",
            "DISCORD_SERVER_ID": "1550097057115541585",
            "DISCORD_CHANNEL_ID": "1550097057820450931",
            "DISCORD_TA_ROLE_ID": "1550098311548108823",
            "DISCORD_SOURCE_MAP_JSON": '{"ANN_04":{"channel_id":123,"message_id":456}}',
        }
        with patch.dict(os.environ, values, clear=False):
            config = BotConfig.from_env()
        self.assertEqual(config.server_id, 1550097057115541585)
        self.assertEqual(config.source_map["ANN_04"], (123, 456))
        self.assertNotIn(config.token, repr(config.source_map))

    def test_missing_token_is_rejected(self):
        with patch.dict(os.environ, {"DISCORD_BOT_TOKEN": ""}, clear=False):
            with self.assertRaisesRegex(RuntimeError, "DISCORD_BOT_TOKEN"):
                BotConfig.from_env()


class DiscordSourceLinkTests(unittest.TestCase):
    def test_jump_url_uses_real_discord_snowflakes(self):
        url = source_jump_url(10, {"ground_truth_id": "ANN_04"}, {"ANN_04": (20, 30)})
        self.assertEqual(url, "https://discord.com/channels/10/20/30")

    def test_missing_mapping_does_not_create_fake_url(self):
        self.assertIsNone(source_jump_url(10, {"ground_truth_id": "ANN_04"}, {}))


class DiscordReplyTests(unittest.IsolatedAsyncioTestCase):
    async def test_mention_response_replies_to_the_original_message(self):
        interaction = SimpleNamespace(
            followup=SimpleNamespace(send=AsyncMock()),
        )
        source_message = SimpleNamespace(reply=AsyncMock())

        await DiscordAssistant._send_response(
            interaction,
            "Câu trả lời có nguồn",
            source_message=source_message,
        )

        source_message.reply.assert_awaited_once_with(
            content="Câu trả lời có nguồn",
            view=None,
            mention_author=False,
        )
        interaction.followup.send.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
