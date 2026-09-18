# Discord Bot Adapter

## Run

From the repository root:

```bash
python3 -m uvicorn codebase.core_ai.server:app --reload
python3 -m codebase.discord_bot.bot
```

The bot reads its token and IDs from the root `.env`. Never commit or paste `DISCORD_BOT_TOKEN`.

## Environment

```env
DISCORD_BOT_TOKEN=...
DISCORD_SERVER_ID=1550097057115541585
DISCORD_CHANNEL_ID=1550097057820450931
DISCORD_TA_ROLE_ID=1550098311548108823
DISCORD_TA_USER_ID=888679823512334336
DISCORD_BOT_NAME=Trợ lý
CORE_AI_URL=http://localhost:8000
```

For real citation jump links, add a JSON mapping after obtaining the Discord message IDs of official announcements:

```env
DISCORD_SOURCE_MAP_JSON={"ANN_04":{"channel_id":123,"message_id":456}}
```

Without a mapping, the bot shows citation text and deliberately does not create a fake URL.

## Discord setup

Install the bot with `bot` and `applications.commands` scopes. Enable Message Content Intent for `@Trợ lý` handling. The `/ask` slash command is the canonical demo path.
