"""SQLite-based session and message persistence.

Replaces the in-memory ``_history`` dict in SpesionAssistant so that
conversation context survives restarts.  Uses WAL mode for decent
concurrency on a single-user system.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("spesion.persistence")

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
_CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS sessions (
    id             TEXT PRIMARY KEY,
    user_id        TEXT NOT NULL,
    platform       TEXT NOT NULL DEFAULT 'api',
    agent          TEXT,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL,
    metadata       TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS messages (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id     TEXT NOT NULL REFERENCES sessions(id),
    role           TEXT NOT NULL CHECK(role IN ('user','assistant','system','tool')),
    content        TEXT NOT NULL,
    agent          TEXT,
    created_at     TEXT NOT NULL,
    token_estimate INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user    ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_at);
"""


# ---------------------------------------------------------------------------
# SessionStore
# ---------------------------------------------------------------------------
class SessionStore:
    """Thread-safe SQLite session store (one connection per call)."""

    def __init__(self, db_path: str | Path = "./data/sessions.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # -- internals ---------------------------------------------------------

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript(_CREATE_TABLES)
        logger.info(f"Session store ready: {self.db_path}")

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    # -- sessions ----------------------------------------------------------

    def create_session(
        self,
        user_id: str,
        platform: str = "api",
        agent: str | None = None,
    ) -> str:
        sid = str(uuid.uuid4())
        now = self._now()
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO sessions (id, user_id, platform, agent, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (sid, user_id, platform, agent, now, now),
            )
        return sid

    def get_or_create_session(
        self,
        user_id: str,
        platform: str = "api",
        stale_minutes: int = 120,
    ) -> str:
        """Return the latest session for *user_id* if updated < *stale_minutes* ago,
        otherwise create a new one."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id, updated_at FROM sessions "
                "WHERE user_id = ? AND platform = ? "
                "ORDER BY updated_at DESC LIMIT 1",
                (user_id, platform),
            ).fetchone()

        if row:
            updated = datetime.fromisoformat(row["updated_at"])
            age_min = (datetime.now(timezone.utc) - updated).total_seconds() / 60
            if age_min < stale_minutes:
                return row["id"]

        return self.create_session(user_id, platform)

    def touch_session(self, session_id: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (self._now(), session_id),
            )

    # -- messages ----------------------------------------------------------

    def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        agent: str | None = None,
    ) -> None:
        now = self._now()
        token_est = max(1, len(content) // 4)
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO messages (session_id, role, content, agent, created_at, token_estimate) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, role, content, agent, now, token_est),
            )
        self.touch_session(session_id)

    def get_messages(
        self,
        session_id: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Return the last *limit* messages in chronological order."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT role, content, agent, created_at, token_estimate "
                "FROM messages WHERE session_id = ? "
                "ORDER BY id DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def get_token_count(self, session_id: str) -> int:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(token_estimate), 0) AS total "
                "FROM messages WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return row["total"] if row else 0

    def prune_old_messages(self, session_id: str, keep: int = 40) -> int:
        """Delete the oldest messages beyond *keep* per session. Returns count deleted."""
        with self._conn() as conn:
            cur = conn.execute(
                "DELETE FROM messages WHERE session_id = ? AND id NOT IN "
                "(SELECT id FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?)",
                (session_id, session_id, keep),
            )
        return cur.rowcount

    # -- queries -----------------------------------------------------------

    def list_sessions(self, user_id: str, limit: int = 20) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT s.id, s.platform, s.agent, s.created_at, s.updated_at, "
                "       COUNT(m.id) AS message_count "
                "FROM sessions s LEFT JOIN messages m ON m.session_id = s.id "
                "WHERE s.user_id = ? "
                "GROUP BY s.id ORDER BY s.updated_at DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def stats(self) -> dict[str, int]:
        with self._conn() as conn:
            sessions = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            messages = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        return {"sessions": sessions, "messages": messages}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_store: SessionStore | None = None


def get_session_store() -> SessionStore:
    global _store
    if _store is None:
        import os

        db_path = os.getenv("SQLITE_DB_PATH", "./data/sessions.db")
        _store = SessionStore(db_path)
    return _store
