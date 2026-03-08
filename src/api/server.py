"""SPESION 3.0 — Unified FastAPI Server.

Entry point:
    uvicorn src.api.server:app --host 0.0.0.0 --port 8100

Starts the API server and optionally launches Discord + Telegram bots
and the Heartbeat proactive runner as background asyncio tasks.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

# Ensure project root is on sys.path
_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src.api.rate_limiter import RateLimitMiddleware  # noqa: E402
from src.api.routes import chat, health, tools  # noqa: E402

logger = logging.getLogger("spesion")


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def _setup_logging() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    for noisy in ("httpx", "httpcore", "chromadb", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# Lifespan — boot bots alongside the API
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown hook."""
    _setup_logging()
    logger.info("🚀 SPESION 3.0 starting …")

    # Ensure directories
    for d in ("./data", "./data/chroma", "./data/temp", "./data/backups",
              "./data/uploads", "./workspace", "./workspace/memory"):
        Path(d).mkdir(parents=True, exist_ok=True)

    # Warm-up persistence
    from src.persistence.session_store import get_session_store

    get_session_store()
    logger.info("✅ Session store ready")

    # ── Background bot tasks ─────────────────────────────────────────────
    bot_tasks: list[asyncio.Task] = []

    # Discord
    discord_token = os.getenv("DISCORD_BOT_TOKEN")
    if discord_token:
        try:
            from src.interfaces.discord_bot import create_discord_bot

            dbot = create_discord_bot()
            task = asyncio.create_task(dbot.start(discord_token))
            bot_tasks.append(task)
            logger.info("✅ Discord bot launched")
        except Exception as exc:
            logger.error(f"❌ Discord bot failed to start: {exc}")

    # Telegram
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if telegram_token:
        try:
            from src.interfaces.telegram_bot import SpesionBot

            tg = SpesionBot()
            task = asyncio.create_task(tg.run_async())
            bot_tasks.append(task)
            logger.info("✅ Telegram bot launched")
        except Exception as exc:
            logger.error(f"❌ Telegram bot failed to start: {exc}")

    # ── SPESION 3.0: Heartbeat Runner ────────────────────────────────────
    heartbeat_enabled = os.getenv("HEARTBEAT_ENABLED", "false").lower() in ("true", "1", "yes")
    if heartbeat_enabled:
        try:
            from src.heartbeat.runner import HeartbeatRunner

            hb = HeartbeatRunner()
            task = asyncio.create_task(hb.start())
            bot_tasks.append(task)
            logger.info("✅ Heartbeat runner launched")
        except Exception as exc:
            logger.error(f"❌ Heartbeat runner failed to start: {exc}")

    yield  # ── Application is running ──

    # ── Shutdown ──────────────────────────────────────────────────────────
    logger.info("🛑 SPESION 3.0 shutting down …")
    for t in bot_tasks:
        t.cancel()
        try:
            await t
        except (asyncio.CancelledError, Exception):
            pass


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------
def create_app() -> FastAPI:
    application = FastAPI(
        title="SPESION 3.0",
        description="Personal AI Second Brain — Multi-Agent System with AGI-tier capabilities",
        version="3.0.0",
        docs_url="/docs" if os.getenv("SPESION_DEBUG") else None,
        redoc_url=None,
        lifespan=lifespan,
    )

    # ── Middleware (last-added = first-executed) ──────────────────────────
    allowed_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
    application.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins or ["http://localhost:3000"],
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )
    application.add_middleware(
        RateLimitMiddleware,
        max_requests=int(os.getenv("RATE_LIMIT_RPM", "60")),
        window_seconds=60,
    )
    allowed_hosts = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")]
    application.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

    # ── Routers ──────────────────────────────────────────────────────────
    application.include_router(health.router, prefix="/api/v1", tags=["health"])
    application.include_router(chat.router, prefix="/api/v1", tags=["chat"])
    application.include_router(tools.router, prefix="/api/v1", tags=["tools"])

    return application


app = create_app()
