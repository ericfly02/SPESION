"""POST /api/v1/chat — Main conversational endpoint.

Routes messages through the LangGraph engine and returns the agent response.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.auth import require_api_key

router = APIRouter()
logger = logging.getLogger("spesion.api.chat")


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000, description="User message")
    user_id: str = Field(default="default", max_length=128, description="User identifier")
    agent_hint: Optional[str] = Field(
        default=None,
        description="Force routing to a specific agent (scholar, coach, tycoon, companion, techlead, connector, executive, sentinel)",
    )
    session_id: Optional[str] = Field(default=None, description="Continue a session (reserved)")
    platform: str = Field(default="api", description="Source platform (api, discord, telegram)")


class ChatResponse(BaseModel):
    response: str
    agent: str
    session_id: str


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------
VALID_AGENTS = {"scholar", "coach", "tycoon", "companion", "techlead", "connector", "executive", "sentinel"}


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, _key: str = Depends(require_api_key)):
    """Send a message through the SPESION multi-agent graph."""

    # Validate agent_hint
    if req.agent_hint and req.agent_hint not in VALID_AGENTS:
        raise HTTPException(400, f"Invalid agent_hint '{req.agent_hint}'. Valid: {sorted(VALID_AGENTS)}")

    # Input security
    from src.security.guard import validate_input

    clean_message = validate_input(req.message)

    # Route through graph
    from src.core.graph import get_assistant

    assistant = get_assistant()

    try:
        response_text = await assistant.achat(
            message=clean_message,
            user_id=req.user_id,
            agent_hint=req.agent_hint,
        )
    except Exception as exc:
        logger.error(f"Graph error: {exc}", exc_info=True)
        raise HTTPException(500, f"Processing error: {exc}") from exc

    return ChatResponse(
        response=response_text,
        agent=getattr(assistant, "last_agent", None) or "supervisor",
        session_id=getattr(assistant, "last_session_id", "") or "",
    )
