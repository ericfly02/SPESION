"""Evolving Memory System — Retain / Recall / Reflect.

Inspired by OpenClaw's memory architecture:
• Daily logs (memory/YYYY-MM-DD.md) — append-only daily records
• Memory bank — typed memories (world facts, experiences, opinions, entities)
• Curated MEMORY.md — promoted long-term memories
• Vector search overlay — semantic retrieval across all memories
• Opinion evolution — confidence scores that change with evidence

This is the system that makes SPESION "keep getting smarter."
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, date
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Memory Types
# ---------------------------------------------------------------------------

MemoryType = Literal[
    "fact",         # World facts: "Python 3.12 released Oct 2023"
    "experience",   # Things that happened: "User ran a 10K in 48:30"
    "opinion",      # Evolved opinions: "User prefers FastAPI over Django"
    "entity",       # People, companies, projects
    "preference",   # User preferences: "Likes concise responses"
    "goal",         # Active goals: "Run sub-1:30 half marathon"
    "decision",     # Key decisions made
    "insight",      # Extracted learnings
    "pattern",      # Detected behavioral patterns
]


@dataclass
class Memory:
    """A single memory entry."""
    id: str
    content: str
    memory_type: str  # MemoryType
    confidence: float = 1.0       # 0.0-1.0, evolves with evidence
    importance: int = 5           # 1-10
    source: str = "conversation"  # conversation, reflection, heartbeat, tool
    tags: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)  # supporting evidence
    created_at: str = ""
    updated_at: str = ""
    access_count: int = 0
    last_accessed: str = ""
    superseded_by: str | None = None  # ID of newer memory that replaces this

    @property
    def is_active(self) -> bool:
        return self.superseded_by is None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type,
            "confidence": self.confidence,
            "importance": self.importance,
            "source": self.source,
            "tags": self.tags,
            "evidence": self.evidence,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed,
            "superseded_by": self.superseded_by,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Memory:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ---------------------------------------------------------------------------
# Daily Log Manager
# ---------------------------------------------------------------------------

class DailyLogManager:
    """Manages daily memory logs in workspace/memory/YYYY-MM-DD.md.

    Each day gets its own append-only log file. These are the "raw" memory
    before curation and compaction.
    """

    def __init__(self, memory_dir: str | Path = "./workspace/memory") -> None:
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)

    def _log_path(self, d: date | None = None) -> Path:
        d = d or date.today()
        return self.memory_dir / f"{d.isoformat()}.md"

    def append(self, content: str, category: str = "general", d: date | None = None) -> None:
        """Append an entry to today's daily log."""
        d = d or date.today()
        path = self._log_path(d)
        now = datetime.now().strftime("%H:%M:%S")

        if not path.exists():
            header = f"# Daily Log — {d.isoformat()}\n\n"
            path.write_text(header, encoding="utf-8")

        with open(path, "a", encoding="utf-8") as f:
            f.write(f"\n## [{now}] {category}\n\n{content}\n")

        logger.debug(f"Daily log appended: {d.isoformat()} [{category}]")

    def read_today(self) -> str:
        """Read today's log."""
        path = self._log_path()
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def read_date(self, d: date) -> str:
        """Read a specific date's log."""
        path = self._log_path(d)
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def list_logs(self, last_n: int = 30) -> list[date]:
        """List available log dates, most recent first."""
        dates = []
        for f in sorted(self.memory_dir.glob("*.md"), reverse=True):
            try:
                d = date.fromisoformat(f.stem)
                dates.append(d)
            except ValueError:
                continue
        return dates[:last_n]


# ---------------------------------------------------------------------------
# Memory Bank — SQLite-backed typed memory store
# ---------------------------------------------------------------------------

_MEMORY_BANK_SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id              TEXT PRIMARY KEY,
    content         TEXT NOT NULL,
    memory_type     TEXT NOT NULL,
    confidence      REAL DEFAULT 1.0,
    importance      INTEGER DEFAULT 5,
    source          TEXT DEFAULT 'conversation',
    tags            TEXT DEFAULT '[]',
    evidence        TEXT DEFAULT '[]',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    access_count    INTEGER DEFAULT 0,
    last_accessed   TEXT,
    superseded_by   TEXT,
    embedding_hash  TEXT
);

CREATE INDEX IF NOT EXISTS idx_mem_type ON memories(memory_type);
CREATE INDEX IF NOT EXISTS idx_mem_importance ON memories(importance DESC);
CREATE INDEX IF NOT EXISTS idx_mem_confidence ON memories(confidence DESC);
CREATE INDEX IF NOT EXISTS idx_mem_active ON memories(superseded_by);
CREATE INDEX IF NOT EXISTS idx_mem_tags ON memories(tags);

CREATE TABLE IF NOT EXISTS memory_links (
    source_id   TEXT NOT NULL REFERENCES memories(id),
    target_id   TEXT NOT NULL REFERENCES memories(id),
    link_type   TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    PRIMARY KEY (source_id, target_id, link_type)
);
"""


class MemoryBank:
    """SQLite-backed typed memory store with opinion evolution.

    This is the structured long-term memory. Unlike ChromaDB (which stores
    raw conversation chunks), the MemoryBank stores curated, typed memories
    with confidence scores, evidence chains, and supersession.
    """

    def __init__(self, db_path: str | Path = "./data/memory_bank.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript(_MEMORY_BANK_SCHEMA)
        logger.info(f"Memory bank ready: {self.db_path}")

    def _now(self) -> str:
        return datetime.now().isoformat()

    # ------------------------------------------------------------------
    # RETAIN — Store new memories
    # ------------------------------------------------------------------

    def retain(
        self,
        content: str,
        memory_type: str = "fact",
        confidence: float = 1.0,
        importance: int = 5,
        source: str = "conversation",
        tags: list[str] | None = None,
        evidence: list[str] | None = None,
    ) -> str:
        """Store a new memory (RETAIN operation).

        Returns:
            The ID of the new memory
        """
        mem_id = str(uuid.uuid4())[:12]
        now = self._now()

        with self._conn() as conn:
            conn.execute(
                "INSERT INTO memories "
                "(id, content, memory_type, confidence, importance, source, "
                "tags, evidence, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    mem_id, content, memory_type, confidence, importance, source,
                    json.dumps(tags or []), json.dumps(evidence or []),
                    now, now,
                ),
            )

        logger.info(f"RETAIN: [{memory_type}] {content[:60]}... (id={mem_id})")
        return mem_id

    # ------------------------------------------------------------------
    # RECALL — Retrieve relevant memories
    # ------------------------------------------------------------------

    def recall(
        self,
        memory_type: str | None = None,
        tags: list[str] | None = None,
        min_confidence: float = 0.3,
        min_importance: int = 1,
        limit: int = 20,
        active_only: bool = True,
    ) -> list[Memory]:
        """Retrieve memories by type, tags, and filters (RECALL operation)."""
        conditions = []
        params: list[Any] = []

        if active_only:
            conditions.append("superseded_by IS NULL")

        if memory_type:
            conditions.append("memory_type = ?")
            params.append(memory_type)

        conditions.append("confidence >= ?")
        params.append(min_confidence)

        conditions.append("importance >= ?")
        params.append(min_importance)

        where = " AND ".join(conditions) if conditions else "1=1"

        # Tag filtering (JSON array in SQLite)
        tag_filter = ""
        if tags:
            tag_conditions = []
            for tag in tags:
                tag_conditions.append("tags LIKE ?")
                params.append(f'%"{tag}"%')
            tag_filter = " AND (" + " OR ".join(tag_conditions) + ")"

        query = (
            f"SELECT * FROM memories WHERE {where}{tag_filter} "
            f"ORDER BY importance DESC, confidence DESC, updated_at DESC "
            f"LIMIT ?"
        )
        params.append(limit)

        with self._conn() as conn:
            rows = conn.execute(query, params).fetchall()

        memories = []
        for row in rows:
            mem = Memory(
                id=row["id"],
                content=row["content"],
                memory_type=row["memory_type"],
                confidence=row["confidence"],
                importance=row["importance"],
                source=row["source"],
                tags=json.loads(row["tags"]),
                evidence=json.loads(row["evidence"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                access_count=row["access_count"],
                last_accessed=row["last_accessed"] or "",
                superseded_by=row["superseded_by"],
            )
            memories.append(mem)

        # Update access counts
        if memories:
            mem_ids = [m.id for m in memories]
            now = self._now()
            with self._conn() as conn:
                for mid in mem_ids:
                    conn.execute(
                        "UPDATE memories SET access_count = access_count + 1, "
                        "last_accessed = ? WHERE id = ?",
                        (now, mid),
                    )

        return memories

    def recall_all_active(self, limit: int = 100) -> list[Memory]:
        """Recall all active memories ordered by importance."""
        return self.recall(limit=limit, active_only=True)

    def recall_by_id(self, mem_id: str) -> Memory | None:
        """Recall a specific memory by ID."""
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM memories WHERE id = ?", (mem_id,)).fetchone()
        if row:
            return Memory(
                id=row["id"], content=row["content"],
                memory_type=row["memory_type"], confidence=row["confidence"],
                importance=row["importance"], source=row["source"],
                tags=json.loads(row["tags"]), evidence=json.loads(row["evidence"]),
                created_at=row["created_at"], updated_at=row["updated_at"],
                access_count=row["access_count"],
                last_accessed=row["last_accessed"] or "",
                superseded_by=row["superseded_by"],
            )
        return None

    # ------------------------------------------------------------------
    # REFLECT — Evolve and update memories
    # ------------------------------------------------------------------

    def evolve_opinion(
        self,
        mem_id: str,
        new_evidence: str,
        confidence_delta: float = 0.0,
    ) -> None:
        """Update a memory's confidence based on new evidence (REFLECT).

        If confidence drops below 0.2, the memory is effectively "forgotten"
        (still stored but filtered out by default recall).
        """
        mem = self.recall_by_id(mem_id)
        if not mem:
            return

        new_confidence = max(0.0, min(1.0, mem.confidence + confidence_delta))
        evidence = mem.evidence + [new_evidence]
        now = self._now()

        with self._conn() as conn:
            conn.execute(
                "UPDATE memories SET confidence = ?, evidence = ?, updated_at = ? "
                "WHERE id = ?",
                (new_confidence, json.dumps(evidence), now, mem_id),
            )

        logger.info(
            f"REFLECT: Opinion evolved [{mem_id}] "
            f"confidence {mem.confidence:.2f} → {new_confidence:.2f}"
        )

    def supersede(self, old_id: str, new_id: str) -> None:
        """Mark a memory as superseded by a newer one."""
        now = self._now()
        with self._conn() as conn:
            conn.execute(
                "UPDATE memories SET superseded_by = ?, updated_at = ? WHERE id = ?",
                (new_id, now, old_id),
            )
        logger.info(f"REFLECT: Memory {old_id} superseded by {new_id}")

    def update_importance(self, mem_id: str, new_importance: int) -> None:
        """Update a memory's importance score."""
        now = self._now()
        with self._conn() as conn:
            conn.execute(
                "UPDATE memories SET importance = ?, updated_at = ? WHERE id = ?",
                (new_importance, now, mem_id),
            )

    # ------------------------------------------------------------------
    # Links — Connect related memories
    # ------------------------------------------------------------------

    def link(self, source_id: str, target_id: str, link_type: str = "related") -> None:
        """Create a link between two memories."""
        now = self._now()
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO memory_links (source_id, target_id, link_type, created_at) "
                "VALUES (?, ?, ?, ?)",
                (source_id, target_id, link_type, now),
            )

    def get_linked(self, mem_id: str) -> list[tuple[str, str]]:
        """Get all memories linked to this one."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT target_id, link_type FROM memory_links WHERE source_id = ? "
                "UNION SELECT source_id, link_type FROM memory_links WHERE target_id = ?",
                (mem_id, mem_id),
            ).fetchall()
        return [(r["target_id"], r["link_type"]) for r in rows]

    # ------------------------------------------------------------------
    # Stats & Maintenance
    # ------------------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        """Get memory bank statistics."""
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            active = conn.execute(
                "SELECT COUNT(*) FROM memories WHERE superseded_by IS NULL"
            ).fetchone()[0]
            by_type = conn.execute(
                "SELECT memory_type, COUNT(*) as cnt FROM memories "
                "WHERE superseded_by IS NULL GROUP BY memory_type"
            ).fetchall()
            avg_conf = conn.execute(
                "SELECT AVG(confidence) FROM memories WHERE superseded_by IS NULL"
            ).fetchone()[0]

        return {
            "total_memories": total,
            "active_memories": active,
            "superseded": total - active,
            "by_type": {r["memory_type"]: r["cnt"] for r in by_type},
            "avg_confidence": round(avg_conf, 3) if avg_conf else 0,
        }

    def cleanup_low_confidence(self, threshold: float = 0.1) -> int:
        """Archive (don't delete) memories with very low confidence."""
        with self._conn() as conn:
            cur = conn.execute(
                "UPDATE memories SET superseded_by = 'archived' "
                "WHERE confidence < ? AND superseded_by IS NULL",
                (threshold,),
            )
        count = cur.rowcount
        if count:
            logger.info(f"Archived {count} low-confidence memories (< {threshold})")
        return count

    def get_recent(self, hours: int = 24, limit: int = 50) -> list[Memory]:
        """Get memories created in the last N hours."""
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM memories WHERE created_at > ? AND superseded_by IS NULL "
                "ORDER BY created_at DESC LIMIT ?",
                (cutoff, limit),
            ).fetchall()

        return [
            Memory(
                id=r["id"], content=r["content"], memory_type=r["memory_type"],
                confidence=r["confidence"], importance=r["importance"],
                source=r["source"], tags=json.loads(r["tags"]),
                evidence=json.loads(r["evidence"]), created_at=r["created_at"],
                updated_at=r["updated_at"], access_count=r["access_count"],
                last_accessed=r["last_accessed"] or "",
                superseded_by=r["superseded_by"],
            )
            for r in rows
        ]


# ---------------------------------------------------------------------------
# Singletons
# ---------------------------------------------------------------------------

_daily_log: DailyLogManager | None = None
_memory_bank: MemoryBank | None = None


def get_daily_log() -> DailyLogManager:
    global _daily_log
    if _daily_log is None:
        _daily_log = DailyLogManager()
    return _daily_log


def get_memory_bank() -> MemoryBank:
    global _memory_bank
    if _memory_bank is None:
        _memory_bank = MemoryBank()
    return _memory_bank
