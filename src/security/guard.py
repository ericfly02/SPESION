"""Prompt-injection detection and input validation.

Guards every user message before it reaches the LangGraph engine.
"""

from __future__ import annotations

import logging
import re

from fastapi import HTTPException

logger = logging.getLogger("spesion.security")

# ---------------------------------------------------------------------------
# Injection patterns (case-insensitive)
# ---------------------------------------------------------------------------
_INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"you\s+are\s+now\s+",
        r"new\s+instructions?\s*:",
        r"system\s*:\s*",
        r"<\|im_start\|>",
        r"\[INST\]",
        r"</s>",
        r"<<SYS>>",
        r"ADMIN[\s_-]*OVERRIDE",
        r"DEBUG[\s_-]*MODE\s*(ON|ENABLED)",
        r"reveal\s+(your\s+)?(system\s+)?prompt",
        r"print\s+(your\s+)?(system\s+)?prompt",
        r"output\s+(your\s+)?instructions",
        r"act\s+as\s+(if\s+)?(you\s+)?(are|were)\s+",
        r"do\s+not\s+follow\s+(your|any)\s+rules",
        r"jailbreak",
        r"DAN\s*mode",
        r"developer\s+mode\s+(enabled|on)",
        r"pretend\s+(you\s+)?(are|to\s+be)\s+",
    ]
]

MAX_MESSAGE_LENGTH = 8000
MIN_MESSAGE_LENGTH = 1


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def detect_injection(text: str) -> str | None:
    """Return the first matched pattern if injection is suspected, else None."""
    for pat in _INJECTION_PATTERNS:
        match = pat.search(text)
        if match:
            return match.group()
    return None


def validate_input(text: str) -> str:
    """Validate and sanitise user input.

    Raises:
        HTTPException 400 on empty, too-long, or suspicious input.

    Returns:
        Cleaned (stripped) text.
    """
    if not text or len(text.strip()) < MIN_MESSAGE_LENGTH:
        raise HTTPException(400, "Message is empty.")

    if len(text) > MAX_MESSAGE_LENGTH:
        raise HTTPException(
            400,
            f"Message too long ({len(text)} chars, max {MAX_MESSAGE_LENGTH}).",
        )

    injection = detect_injection(text)
    if injection:
        logger.warning(f"⚠️  Prompt injection attempt blocked: '{injection[:80]}'")
        raise HTTPException(
            400,
            "Your message was flagged as potentially unsafe. "
            "If this is a mistake, please rephrase and try again.",
        )

    return text.strip()


def sanitize_for_log(text: str, max_len: int = 200) -> str:
    """Truncate text for safe logging (prevent credential leaks)."""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "…"
