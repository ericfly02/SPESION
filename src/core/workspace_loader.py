"""Workspace Loader — Loads and injects workspace files into agent context.

Inspired by OpenClaw's workspace bootstrap system where files like SOUL.md,
AGENTS.md, IDENTITY.md, and BOOTSTRAP.md are injected into the agent's
context at session start.

The workspace is the "soul" of SPESION — it defines personality, operating
rules, memory, and proactive behavior. These files can evolve over time
as the Cognitive Loop learns from interactions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Workspace directory (relative to project root)
WORKSPACE_DIR = Path("./workspace")


@dataclass
class WorkspaceContext:
    """Loaded workspace context ready for injection into agent prompts."""
    soul: str = ""
    identity: str = ""
    agents: str = ""
    bootstrap: str = ""
    heartbeat: str = ""
    memory: str = ""
    user_profile: str = ""

    @property
    def is_first_run(self) -> bool:
        """Check if this is the first run (no memory yet)."""
        return "awaiting first interactions" in self.memory.lower()

    def get_agent_context(self, agent_name: str) -> str:
        """Build the full context string for a specific agent.

        This combines all workspace files into a single context block
        that gets injected as a SystemMessage at the start of every
        agent invocation.
        """
        parts = []

        # Always include soul (personality)
        if self.soul:
            parts.append(f"## 🧬 SOUL (Who You Are)\n\n{self.soul}")

        # Include identity (system info)
        if self.identity:
            parts.append(f"## 🆔 IDENTITY\n\n{self.identity}")

        # Include operating rules
        if self.agents:
            parts.append(f"## 📋 OPERATING RULES\n\n{self.agents}")

        # Include user profile
        if self.user_profile:
            parts.append(f"## 👤 USER PROFILE\n\n{self.user_profile}")

        # Include curated memory (condensed)
        if self.memory and not self.is_first_run:
            # Only include non-empty sections of memory
            memory_lines = []
            for line in self.memory.split("\n"):
                if line.strip() and not line.startswith("*Last") and not line.startswith("---"):
                    memory_lines.append(line)
            condensed = "\n".join(memory_lines[:50])  # Cap at 50 lines
            if condensed.strip():
                parts.append(f"## 🧠 LONG-TERM MEMORY\n\n{condensed}")

        # For heartbeat runs, include the checklist
        if agent_name == "__heartbeat__" and self.heartbeat:
            parts.append(f"## 💓 HEARTBEAT CHECKLIST\n\n{self.heartbeat}")

        return "\n\n---\n\n".join(parts)

    def get_bootstrap_context(self) -> str:
        """Get the bootstrap context for first-run scenarios."""
        if self.bootstrap:
            return f"## 🚀 BOOTSTRAP (First Run)\n\n{self.bootstrap}"
        return ""


class WorkspaceLoader:
    """Loads workspace files from disk and provides them for injection."""

    def __init__(self, workspace_dir: str | Path | None = None) -> None:
        self.workspace_dir = Path(workspace_dir or WORKSPACE_DIR)
        self._cache: WorkspaceContext | None = None
        self._cache_time: float = 0

    def _read_file(self, filename: str) -> str:
        """Read a workspace file, returning empty string if not found."""
        filepath = self.workspace_dir / filename
        if filepath.exists():
            try:
                return filepath.read_text(encoding="utf-8").strip()
            except Exception as e:
                logger.warning(f"Error reading workspace file {filename}: {e}")
        return ""

    def _read_user_profile(self) -> str:
        """Read the user profile from data/user_profile.md."""
        profile_path = Path("./data/user_profile.md")
        if profile_path.exists():
            try:
                return profile_path.read_text(encoding="utf-8").strip()
            except Exception:
                pass
        return ""

    def load(self, force_reload: bool = False) -> WorkspaceContext:
        """Load all workspace files into a WorkspaceContext.

        Results are cached for 60 seconds to avoid re-reading on every
        agent invocation within the same session.
        """
        import time

        if not force_reload and self._cache is not None:
            age = time.time() - self._cache_time
            if age < 60:
                return self._cache

        ctx = WorkspaceContext(
            soul=self._read_file("SOUL.md"),
            identity=self._read_file("IDENTITY.md"),
            agents=self._read_file("AGENTS.md"),
            bootstrap=self._read_file("BOOTSTRAP.md"),
            heartbeat=self._read_file("HEARTBEAT.md"),
            memory=self._read_file("MEMORY.md"),
            user_profile=self._read_user_profile(),
        )

        self._cache = ctx
        self._cache_time = time.time()

        logger.debug(
            f"Workspace loaded: soul={bool(ctx.soul)}, identity={bool(ctx.identity)}, "
            f"agents={bool(ctx.agents)}, memory={bool(ctx.memory)}, "
            f"first_run={ctx.is_first_run}"
        )
        return ctx

    def update_memory(self, new_content: str) -> None:
        """Update the MEMORY.md file with new content."""
        memory_path = self.workspace_dir / "MEMORY.md"
        try:
            memory_path.write_text(new_content, encoding="utf-8")
            # Invalidate cache
            self._cache = None
            logger.info("Workspace MEMORY.md updated")
        except Exception as e:
            logger.error(f"Error updating MEMORY.md: {e}")

    def append_to_soul(self, preference: str) -> None:
        """Append a learned preference to SOUL.md."""
        soul_path = self.workspace_dir / "SOUL.md"
        try:
            current = soul_path.read_text(encoding="utf-8")
            # Append under "Learned Preferences" section
            updated = current.rstrip() + f"\n- {preference}\n"
            soul_path.write_text(updated, encoding="utf-8")
            self._cache = None
            logger.info(f"SOUL.md updated with preference: {preference[:50]}...")
        except Exception as e:
            logger.error(f"Error updating SOUL.md: {e}")


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_loader: WorkspaceLoader | None = None


def get_workspace_loader() -> WorkspaceLoader:
    """Get the singleton WorkspaceLoader."""
    global _loader
    if _loader is None:
        _loader = WorkspaceLoader()
    return _loader


def get_workspace_context(agent_name: str = "supervisor") -> str:
    """Convenience function to get formatted workspace context for an agent."""
    loader = get_workspace_loader()
    ctx = loader.load()
    return ctx.get_agent_context(agent_name)
