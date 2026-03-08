"""GET /api/v1/health — System health and readiness check."""

from __future__ import annotations

import os
import time

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()
_start_time = time.time()


class HealthResponse(BaseModel):
    status: str
    uptime_seconds: float
    services: dict[str, str]


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Return overall health + per-service status."""
    services: dict[str, str] = {}

    # ── Ollama ────────────────────────────────────────────────────────────
    try:
        import httpx

        base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(f"{base}/api/tags")
        models = r.json().get("models", [])
        names = [m.get("name", "?") for m in models[:5]]
        services["ollama"] = f"ok ({len(models)} models: {', '.join(names)})"
    except Exception as e:
        services["ollama"] = f"unreachable: {e}"

    # ── ChromaDB ──────────────────────────────────────────────────────────
    try:
        from src.services.vector_store import get_vector_store

        store = get_vector_store()
        stats = store.get_collection_stats() if hasattr(store, "get_collection_stats") else {}
        total = sum(stats.values()) if isinstance(stats, dict) else 0
        services["chromadb"] = f"ok ({total} vectors)"
    except Exception as e:
        services["chromadb"] = f"error: {e}"

    # ── Session store ─────────────────────────────────────────────────────
    try:
        from src.persistence.session_store import get_session_store

        get_session_store()
        services["session_store"] = "ok"
    except Exception as e:
        services["session_store"] = f"error: {e}"

    overall = "healthy" if all("ok" in v for v in services.values()) else "degraded"
    return HealthResponse(
        status=overall,
        uptime_seconds=round(time.time() - _start_time, 1),
        services=services,
    )
