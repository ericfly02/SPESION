"""Skill Store — Agent Self-Learning System.

SPESION 3.0: Agents can learn from their own successful task executions.
Each time an agent successfully handles a task type, the pattern is stored
as a "skill". Future agents recall matching skills before their LLM call
to execute known tasks faster and more accurately (without relearning).

Architecture:
    - Skills are SQLite-backed (data/skill_store.db)
    - Each skill belongs to one agent (or 'global' for shared skills)
    - Skills have trigger keywords, a step-by-step template, and a success rate
    - Agents recall skills by keyword overlap (Jaccard) before each call
    - After a successful response, a skill extraction LLM call extracts the pattern
    - Skills evolve: high-success skills gain weight; low-success skills are pruned

Usage in agents:
    store = get_skill_store()
    # Recall before LLM
    relevant = store.recall(agent_name="executive", query="create event tomorrow", limit=3)
    # Save after success
    store.save_from_interaction(agent_name, user_msg, agent_response)
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DB_PATH = Path("./data/skill_store.db")


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Skill:
    """A learned task execution pattern."""

    id: str
    agent: str                      # owning agent name or 'global'
    name: str                       # short skill name
    description: str                # what this skill does
    trigger_keywords: list[str]     # words that activate this skill
    steps: str                      # markdown steps template
    outcome_hint: str               # what a good outcome looks like
    use_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    confidence: float = 0.5         # 0–1, increases on success
    created_at: str = ""
    last_used: str = ""

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else self.confidence

    def to_context_block(self) -> str:
        """Format skill as a context injection for an agent's system prompt."""
        return (
            f"### Skill: {self.name} (confidence: {self.confidence:.0%})\n"
            f"**When to use**: {self.description}\n"
            f"**Steps**:\n{self.steps}\n"
            f"**Expected outcome**: {self.outcome_hint}\n"
        )


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS skills (
    id          TEXT PRIMARY KEY,
    agent       TEXT NOT NULL,
    name        TEXT NOT NULL,
    description TEXT NOT NULL,
    trigger_keywords TEXT NOT NULL,   -- JSON array
    steps       TEXT NOT NULL,
    outcome_hint TEXT NOT NULL DEFAULT '',
    use_count   INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    confidence  REAL DEFAULT 0.5,
    created_at  TEXT NOT NULL,
    last_used   TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_skills_agent ON skills(agent);
CREATE INDEX IF NOT EXISTS idx_skills_confidence ON skills(confidence DESC);
"""


class SkillStore:
    """Persistent skill store for agent self-learning.

    Thread-safe SQLite with WAL mode.
    """

    def __init__(self, db_path: Path = _DB_PATH) -> None:
        self._path = db_path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript(_SCHEMA)

    # ------------------------------------------------------------------
    # RETAIN — Save a new skill
    # ------------------------------------------------------------------
    def retain(
        self,
        *,
        agent: str,
        name: str,
        description: str,
        trigger_keywords: list[str],
        steps: str,
        outcome_hint: str = "",
        confidence: float = 0.5,
    ) -> str:
        """Store a new skill. Returns the skill ID."""
        skill_id = str(uuid.uuid4())[:12]
        now = datetime.utcnow().isoformat()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO skills
                  (id, agent, name, description, trigger_keywords, steps,
                   outcome_hint, use_count, success_count, failure_count,
                   confidence, created_at, last_used)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 0, ?, ?, '')
                """,
                (
                    skill_id, agent, name, description,
                    json.dumps(trigger_keywords, ensure_ascii=False),
                    steps, outcome_hint, confidence, now,
                ),
            )
        logger.info(f"Skill retained: [{agent}] {name} ({skill_id})")
        return skill_id

    # ------------------------------------------------------------------
    # RECALL — Find relevant skills for a query
    # ------------------------------------------------------------------
    def recall(
        self,
        agent: str,
        query: str,
        limit: int = 3,
        min_confidence: float = 0.3,
    ) -> list[Skill]:
        """Return the most relevant skills for an agent and query.

        Uses keyword overlap (Jaccard-like) + confidence weighting.
        Searches both agent-specific and global skills.
        """
        query_words = set(_tokenize(query))
        if not query_words:
            return []

        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM skills
                WHERE (agent = ? OR agent = 'global')
                  AND confidence >= ?
                ORDER BY confidence DESC
                LIMIT 100
                """,
                (agent, min_confidence),
            ).fetchall()

        if not rows:
            return []

        scored: list[tuple[float, Skill]] = []
        for row in rows:
            skill_keywords = set(json.loads(row["trigger_keywords"]))
            overlap = len(query_words & skill_keywords)
            union = len(query_words | skill_keywords)
            jaccard = overlap / union if union > 0 else 0.0
            # Boost by confidence
            score = jaccard * 0.7 + row["confidence"] * 0.3
            if jaccard > 0:
                scored.append((score, _row_to_skill(row)))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [s for _, s in scored[:limit]]

    # ------------------------------------------------------------------
    # FEEDBACK — Update success / failure counts
    # ------------------------------------------------------------------
    def mark_success(self, skill_id: str, delta: float = 0.05) -> None:
        """Increase skill confidence after successful use."""
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE skills
                SET use_count = use_count + 1,
                    success_count = success_count + 1,
                    confidence = MIN(0.99, confidence + ?),
                    last_used = ?
                WHERE id = ?
                """,
                (delta, datetime.utcnow().isoformat(), skill_id),
            )

    def mark_failure(self, skill_id: str, delta: float = 0.08) -> None:
        """Decrease skill confidence after failure."""
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE skills
                SET use_count = use_count + 1,
                    failure_count = failure_count + 1,
                    confidence = MAX(0.05, confidence - ?),
                    last_used = ?
                WHERE id = ?
                """,
                (delta, datetime.utcnow().isoformat(), skill_id),
            )

    # ------------------------------------------------------------------
    # AUTO-EXTRACT — LLM-assisted skill extraction after success
    # ------------------------------------------------------------------
    def save_from_interaction(
        self,
        agent: str,
        user_message: str,
        agent_response: str,
        llm=None,
    ) -> str | None:
        """Attempt to extract and save a reusable skill from a successful interaction.

        Uses a local LLM for privacy-safe extraction.
        Returns the new skill ID or None if extraction failed / not worth saving.
        """
        # Only learn from substantive interactions
        if len(user_message) < 20 or len(agent_response) < 50:
            return None

        # Don't try to learn casual conversation
        conversational_markers = {
            "hola", "gracias", "ok", "vale", "bien", "genial", "perfecto",
            "hello", "thanks", "great", "cool", "bye", "adios",
        }
        words = set(_tokenize(user_message))
        if words <= conversational_markers:
            return None

        if llm is None:
            try:
                from src.core.model_router import get_model_router
                router = get_model_router()
                llm = router.get_llm(agent_name="supervisor", temperature=0.3)
            except Exception:
                return None

        extraction_prompt = f"""Analyze this agent interaction and extract a reusable skill pattern.
Agent: {agent}
User: {user_message}
Response: {agent_response[:600]}

Return a JSON object with these fields (or null if this is too conversational/one-off to be a skill):
{{
  "name": "short skill name (3-6 words)",
  "description": "one sentence: when to use this skill",
  "trigger_keywords": ["list", "of", "5-10", "trigger", "words"],
  "steps": "1. Step one\\n2. Step two\\n3. Step three",
  "outcome_hint": "what a good outcome looks like"
}}

Return ONLY the JSON or null."""

        try:
            from langchain_core.messages import HumanMessage
            resp = llm.invoke([HumanMessage(content=extraction_prompt)])
            text = resp.content.strip()

            if text.lower() in ("null", "none", ""):
                return None

            # Extract JSON from response
            json_match = re.search(r"\{.*\}", text, re.DOTALL)
            if not json_match:
                return None

            data = json.loads(json_match.group())
            if not all(k in data for k in ("name", "description", "trigger_keywords", "steps")):
                return None

            # Check for duplicate skill names for this agent
            with self._conn() as conn:
                existing = conn.execute(
                    "SELECT id FROM skills WHERE agent = ? AND name = ?",
                    (agent, data["name"]),
                ).fetchone()
                if existing:
                    return existing["id"]  # Already have this skill

            skill_id = self.retain(
                agent=agent,
                name=data["name"],
                description=data["description"],
                trigger_keywords=data["trigger_keywords"],
                steps=data["steps"],
                outcome_hint=data.get("outcome_hint", ""),
                confidence=0.55,  # Start slightly above baseline for learned skills
            )
            logger.info(f"New skill auto-learned: [{agent}] {data['name']}")
            return skill_id

        except Exception as e:
            logger.debug(f"Skill extraction failed (non-critical): {e}")
            return None

    # ------------------------------------------------------------------
    # MAINTENANCE
    # ------------------------------------------------------------------
    def prune_low_confidence(self, threshold: float = 0.1, min_uses: int = 3) -> int:
        """Remove skills that have been used enough times but remain low-confidence."""
        with self._conn() as conn:
            result = conn.execute(
                """
                DELETE FROM skills
                WHERE confidence < ?
                  AND (use_count >= ? OR failure_count >= 2)
                """,
                (threshold, min_uses),
            )
            return result.rowcount

    def stats(self) -> dict[str, Any]:
        """Return skill store statistics."""
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM skills").fetchone()[0]
            by_agent = {}
            for row in conn.execute(
                "SELECT agent, COUNT(*) as cnt, AVG(confidence) as avg_conf FROM skills GROUP BY agent"
            ):
                by_agent[row["agent"]] = {
                    "count": row["cnt"],
                    "avg_confidence": round(row["avg_conf"] or 0, 2),
                }
            top = conn.execute(
                "SELECT agent, name, confidence, use_count FROM skills ORDER BY confidence DESC LIMIT 5"
            ).fetchall()

        return {
            "total_skills": total,
            "by_agent": by_agent,
            "top_skills": [dict(r) for r in top],
        }

    def list_agent_skills(self, agent: str) -> list[Skill]:
        """List all skills for an agent ordered by confidence."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM skills WHERE agent = ? OR agent = 'global' ORDER BY confidence DESC",
                (agent,),
            ).fetchall()
        return [_row_to_skill(r) for r in rows]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> list[str]:
    """Simple tokenizer: lowercase, remove stop words."""
    STOP = {
        "el", "la", "los", "las", "un", "una", "de", "del", "en", "con",
        "a", "al", "por", "para", "que", "es", "son", "y", "o", "no",
        "the", "a", "an", "is", "are", "in", "on", "at", "to", "for",
        "of", "and", "or", "not", "it", "this", "that", "i", "me", "my",
    }
    words = re.findall(r"[a-záéíóúüñA-ZÁÉÍÓÚÜÑ]{3,}", text.lower())
    return [w for w in words if w not in STOP]


def _row_to_skill(row: sqlite3.Row) -> Skill:
    return Skill(
        id=row["id"],
        agent=row["agent"],
        name=row["name"],
        description=row["description"],
        trigger_keywords=json.loads(row["trigger_keywords"]),
        steps=row["steps"],
        outcome_hint=row["outcome_hint"],
        use_count=row["use_count"],
        success_count=row["success_count"],
        failure_count=row["failure_count"],
        confidence=row["confidence"],
        created_at=row["created_at"],
        last_used=row["last_used"],
    )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_store: SkillStore | None = None


def get_skill_store() -> SkillStore:
    """Get or create the global SkillStore singleton."""
    global _store
    if _store is None:
        _store = SkillStore()
    return _store
