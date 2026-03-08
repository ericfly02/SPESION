"""Human-in-the-Loop Approval Gate — Telegram/Discord confirmations.

Before SPESION performs a dangerous action (phone call, email, payment),
it sends an approval request to the user via Telegram or Discord.
The user can approve (✅) or reject (❌) from their phone.

Usage flow:
    1. PlanExecutor hits a DANGEROUS step
    2. Calls approval_callback(step) 
    3. This module sends a formatted message to Telegram/Discord
    4. Waits for user response (timeout = 5 minutes)
    5. Returns True/False
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Any, Callable

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# In-memory approval store (for sync planner→async bot bridge)
# ═══════════════════════════════════════════════════════════════════

_pending_approvals: dict[str, dict[str, Any]] = {}
_approval_lock = threading.Lock()


def request_approval(
    step_id: str,
    message: str,
    user_id: str = "default",
    timeout: float = 300.0,      # 5 minutes
) -> bool:
    """Block until the user approves or rejects, or timeout.

    This is called by PlanExecutor (sync).  The Telegram/Discord bot
    picks up the pending approval and presents it to the user.

    Args:
        step_id: Unique step identifier
        message: Human-readable description of what SPESION wants to do
        user_id: User to ask for approval
        timeout: Max seconds to wait

    Returns:
        True if approved, False if rejected or timed out.
    """
    with _approval_lock:
        _pending_approvals[step_id] = {
            "message": message,
            "user_id": user_id,
            "status": "pending",      # pending | approved | rejected
            "created_at": time.time(),
            "timeout": timeout,
        }

    logger.info(f"🔐 Approval requested: {step_id} — {message[:80]}")

    # Poll for response
    deadline = time.time() + timeout
    while time.time() < deadline:
        with _approval_lock:
            entry = _pending_approvals.get(step_id)
            if entry and entry["status"] != "pending":
                result = entry["status"] == "approved"
                del _pending_approvals[step_id]
                return result
        time.sleep(1)

    # Timeout — auto-reject
    with _approval_lock:
        _pending_approvals.pop(step_id, None)
    logger.warning(f"⏰ Approval timed out: {step_id}")
    return False


def respond_to_approval(step_id: str, approved: bool) -> bool:
    """Called by Telegram/Discord bot when user responds.

    Args:
        step_id: The step awaiting approval
        approved: True = approve, False = reject

    Returns:
        True if the approval was found and updated, False if not found.
    """
    with _approval_lock:
        if step_id in _pending_approvals:
            _pending_approvals[step_id]["status"] = "approved" if approved else "rejected"
            logger.info(f"{'✅' if approved else '🚫'} Approval response: {step_id}")
            return True
    return False


def get_pending_approvals(user_id: str | None = None) -> list[dict[str, Any]]:
    """Get all pending approvals, optionally filtered by user.

    Returns list of dicts with step_id, message, created_at.
    """
    with _approval_lock:
        results = []
        now = time.time()
        for step_id, entry in list(_pending_approvals.items()):
            if entry["status"] != "pending":
                continue
            if entry["created_at"] + entry["timeout"] < now:
                # Expired
                del _pending_approvals[step_id]
                continue
            if user_id and entry["user_id"] != user_id:
                continue
            results.append({
                "step_id": step_id,
                "message": entry["message"],
                "created_at": entry["created_at"],
                "remaining_seconds": int(entry["created_at"] + entry["timeout"] - now),
            })
        return results


def clear_expired():
    """Remove expired approvals."""
    with _approval_lock:
        now = time.time()
        expired = [
            sid for sid, e in _pending_approvals.items()
            if e["created_at"] + e["timeout"] < now
        ]
        for sid in expired:
            del _pending_approvals[sid]


# ═══════════════════════════════════════════════════════════════════
# Format approval message for Telegram / Discord
# ═══════════════════════════════════════════════════════════════════

def format_approval_telegram(step_id: str, message: str) -> tuple[str, list[list[dict]]]:
    """Format an approval request for Telegram with inline keyboard.

    Returns:
        (text, inline_keyboard) ready for sendMessage with reply_markup.
    """
    text = (
        "🔐 **SPESION necesita tu aprobación**\n\n"
        f"{message}\n\n"
        "⚠️ Esta acción contacta a terceros o implica una acción real.\n"
        "Responde en los próximos 5 minutos."
    )
    keyboard = [[
        {"text": "✅ Aprobar", "callback_data": f"approve:{step_id}"},
        {"text": "❌ Rechazar", "callback_data": f"reject:{step_id}"},
    ]]
    return text, keyboard


def format_approval_discord(step_id: str, message: str) -> dict[str, Any]:
    """Format an approval request for Discord with buttons.

    Returns:
        Dict with content and components for Discord interaction.
    """
    return {
        "content": (
            "🔐 **SPESION necesita tu aprobación**\n\n"
            f"{message}\n\n"
            "⚠️ Esta acción contacta a terceros o implica una acción real.\n"
            "Responde en los próximos 5 minutos."
        ),
        "components": [{
            "type": 1,  # ActionRow
            "components": [
                {
                    "type": 2,  # Button
                    "style": 3,  # Success (green)
                    "label": "✅ Aprobar",
                    "custom_id": f"approve:{step_id}",
                },
                {
                    "type": 2,
                    "style": 4,  # Danger (red)
                    "label": "❌ Rechazar",
                    "custom_id": f"reject:{step_id}",
                },
            ],
        }],
    }


# ═══════════════════════════════════════════════════════════════════
# Approval callback factory for the PlanExecutor
# ═══════════════════════════════════════════════════════════════════

def create_approval_callback(
    user_id: str = "default",
    notification_fn: Callable[[str, str], None] | None = None,
) -> Callable:
    """Create an approval callback for PlanExecutor.

    Args:
        user_id: User to request approval from
        notification_fn: Optional function(step_id, message) that sends
            the approval request to the user's interface (Telegram/Discord).
            If None, the approval just waits in the pending store.

    Returns:
        Callable that PlanExecutor can use as approval_callback.
    """
    def callback(step) -> bool:
        message = step.approval_message or step.description
        step_id = step.id

        # Notify user via their interface
        if notification_fn:
            try:
                notification_fn(step_id, message)
            except Exception as e:
                logger.warning(f"Could not send approval notification: {e}")

        return request_approval(step_id, message, user_id=user_id)

    return callback
