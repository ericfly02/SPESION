"""SPESION 2.0 — Discord Multi-Agent Bot.

One bot, multiple channels.  Channel name → agent routing.
Messages are processed through the SPESION LangGraph engine directly
(same Python process when run inside the unified server, or standalone).

Run standalone:
    python -m src.interfaces.discord_bot

Or started automatically by src/api/server.py lifespan.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import sys
from pathlib import Path

# Ensure project root
_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import discord  # noqa: E402
from discord import Intents, Message  # noqa: E402
from discord.ext import commands  # noqa: E402

logger = logging.getLogger("spesion.discord")

# ---------------------------------------------------------------------------
# Channel → Agent mapping
# ---------------------------------------------------------------------------
CHANNEL_AGENT_MAP: dict[str, str] = {
    "scholar": "scholar",
    "research": "scholar",
    "papers": "scholar",
    "coach": "coach",
    "fitness": "coach",
    "training": "coach",
    "entreno": "coach",
    "tycoon": "tycoon",
    "finance": "tycoon",
    "portfolio": "tycoon",
    "companion": "companion",
    "journal": "companion",
    "emotions": "companion",
    "techlead": "techlead",
    "code": "techlead",
    "dev": "techlead",
    "connector": "connector",
    "networking": "connector",
    "crm": "connector",
    "executive": "executive",
    "agenda": "executive",
    "tasks": "executive",
    "sentinel": "sentinel",
    "security": "sentinel",
    "status": "sentinel",
}

AGENT_PERSONAS: dict[str, dict] = {
    "scholar":    {"emoji": "📚", "color": 0x3498DB, "name": "Scholar"},
    "coach":      {"emoji": "🏃", "color": 0x2ECC71, "name": "Coach"},
    "tycoon":     {"emoji": "💰", "color": 0xF1C40F, "name": "Tycoon"},
    "companion":  {"emoji": "💭", "color": 0x9B59B6, "name": "Companion"},
    "techlead":   {"emoji": "🔧", "color": 0xE74C3C, "name": "TechLead"},
    "connector":  {"emoji": "🤝", "color": 0x1ABC9C, "name": "Connector"},
    "executive":  {"emoji": "📅", "color": 0xE67E22, "name": "Executive"},
    "sentinel":   {"emoji": "🛡️", "color": 0x95A5A6, "name": "Sentinel"},
    "supervisor": {"emoji": "🧠", "color": 0x7289DA, "name": "SPESION"},
}


def _resolve_agent(channel_name: str) -> str | None:
    """Map a Discord channel name to an agent key."""
    clean = channel_name.lower().strip().lstrip("#")
    clean = re.sub(r"^(spesion[-_]?)", "", clean)
    return CHANNEL_AGENT_MAP.get(clean)


# ---------------------------------------------------------------------------
# Bot class
# ---------------------------------------------------------------------------
class SpesionDiscordBot(commands.Bot):
    """Discord bot that routes messages to SPESION agents."""

    def __init__(self) -> None:
        intents = Intents.default()
        intents.message_content = True
        intents.guilds = True

        allowed_ids = os.getenv("DISCORD_ALLOWED_USER_IDS", "")
        self.allowed_users: set[int] = set()
        if allowed_ids:
            self.allowed_users = {int(x.strip()) for x in allowed_ids.split(",") if x.strip()}

        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
        )

    # -- lifecycle ---------------------------------------------------------

    async def on_ready(self) -> None:
        logger.info(f"✅ Discord bot online as {self.user} (ID: {self.user.id})")
        logger.info(f"   Guilds: {[g.name for g in self.guilds]}")

        # Register slash commands
        try:
            synced = await self.tree.sync()
            logger.info(f"   Synced {len(synced)} slash commands")
        except Exception as exc:
            logger.warning(f"   Slash-command sync failed: {exc}")

    # -- message handler ---------------------------------------------------

    async def on_message(self, message: Message) -> None:
        # Skip self + other bots
        if message.author == self.user or message.author.bot:
            return

        # Allowlist check
        if self.allowed_users and message.author.id not in self.allowed_users:
            return

        # Determine routing
        agent_hint = _resolve_agent(message.channel.name)
        is_mentioned = self.user in message.mentions if self.user else False

        # In non-agent channels, only respond when @mentioned
        if not agent_hint and not is_mentioned:
            return

        # Clean message (strip bot mention)
        content = message.content
        if self.user:
            content = content.replace(f"<@{self.user.id}>", "").strip()
            content = content.replace(f"<@!{self.user.id}>", "").strip()

        if not content:
            return

        # Process with typing indicator
        async with message.channel.typing():
            response_text = await self._get_response(
                content=content,
                user_id=str(message.author.id),
                agent_hint=agent_hint,
            )

        # Send reply as embed
        agent = agent_hint or "supervisor"
        persona = AGENT_PERSONAS.get(agent, AGENT_PERSONAS["supervisor"])

        if len(response_text) <= 1900:
            embed = discord.Embed(description=response_text, color=persona["color"])
            embed.set_author(name=f"{persona['emoji']} {persona['name']}")
            await message.reply(embed=embed, mention_author=False)
        else:
            # Split long messages
            chunks = [response_text[i : i + 1900] for i in range(0, len(response_text), 1900)]
            for i, chunk in enumerate(chunks):
                embed = discord.Embed(description=chunk, color=persona["color"])
                if i == 0:
                    embed.set_author(name=f"{persona['emoji']} {persona['name']}")
                await message.channel.send(embed=embed)

    # -- SPESION integration -----------------------------------------------

    async def _get_response(
        self,
        content: str,
        user_id: str,
        agent_hint: str | None = None,
    ) -> str:
        """Get a response from the SPESION engine."""
        try:
            from src.security.guard import detect_injection

            if detect_injection(content):
                return "⚠️ Your message was flagged as potentially unsafe."

            from src.core.graph import get_assistant

            assistant = get_assistant()
            response = await assistant.achat(
                message=content,
                user_id=f"discord_{user_id}",
                agent_hint=agent_hint,
            )
            return response
        except Exception as e:
            logger.error(f"Discord processing error: {e}", exc_info=True)
            return f"⚠️ Error: {e}"


# ---------------------------------------------------------------------------
# Factory + standalone runner
# ---------------------------------------------------------------------------
def create_discord_bot() -> SpesionDiscordBot:
    """Create a fresh bot instance."""
    return SpesionDiscordBot()


async def run_discord() -> None:
    """Entry point for running the Discord bot standalone."""
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        logger.error("DISCORD_BOT_TOKEN not set — exiting")
        return
    bot = create_discord_bot()
    await bot.start(token)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_discord())
