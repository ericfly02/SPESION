"""Bearer-token API-key authentication."""

from __future__ import annotations

import os
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer = HTTPBearer(auto_error=False)


def _get_api_key() -> str:
    """Return the configured API key or raise at startup."""
    key = os.getenv("SPESION_API_KEY", "")
    if not key or key == "change-me":
        raise RuntimeError(
            "SPESION_API_KEY is not set or is still the default value. "
            "Generate one with:  python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )
    return key


async def require_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """FastAPI dependency — validates the Bearer token.

    Usage:
        @router.post("/endpoint")
        async def endpoint(_key: str = Depends(require_api_key)):
            ...
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header. Use: Authorization: Bearer <key>",
        )
    if not secrets.compare_digest(credentials.credentials, _get_api_key()):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )
    return credentials.credentials
