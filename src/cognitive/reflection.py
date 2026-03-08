"""Cognitive Loop — Reflection, Pattern Detection & Idea Generation.

This is the engine that makes SPESION "keep getting smarter."

Inspired by OpenClaw's Retain/Recall/Reflect operational loop, but extended:

1. **Session Reflection** — After meaningful interactions, extract key learnings
2. **Pattern Detection** — Spot recurring themes across conversations
3. **Opinion Evolution** — Update confidence scores based on new evidence
4. **Idea Engine** — Connect disparate memories to generate novel insights
5. **Memory Curation** — Promote important memories to MEMORY.md

The Cognitive Loop runs:
- After every conversation (lightweight reflection)
- During heartbeats (pattern detection, idea generation)
- Weekly (deep compaction, opinion review)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, date
from typing import Any

from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)


class CognitiveLoop:
    """The brain behind SPESION's continuous learning."""

    def __init__(self) -> None:
        self._llm = None  # Lazy-loaded

    @property
    def llm(self):
        """Get a local LLM for reflection (privacy-safe)."""
        if self._llm is None:
            from src.core.model_router import get_model_router, Complexity, Privacy
            router = get_model_router()
            self._llm = router.get_llm(
                complexity=Complexity.MODERATE,
                privacy=Privacy.PRIVATE,  # Reflection stays local
            )
        return self._llm

    # ------------------------------------------------------------------
    # 1. SESSION REFLECTION — runs after each conversation
    # ------------------------------------------------------------------

    def reflect_on_session(
        self,
        user_message: str,
        agent_response: str,
        agent_name: str,
    ) -> dict[str, Any]:
        """Extract learnings from a single interaction.

        This runs after every meaningful exchange (>10 chars) and:
        - Extracts key facts mentioned
        - Identifies user preferences shown
        - Detects emotional state changes
        - Flags important decisions made

        Returns dict with extracted items.
        """
        from src.memory.evolving_memory import get_memory_bank, get_daily_log

        bank = get_memory_bank()
        daily = get_daily_log()

        # Skip trivial interactions
        if len(user_message) < 20 and len(agent_response) < 50:
            return {"skipped": True, "reason": "too_short"}

        prompt = f"""Analyze this interaction and extract structured learnings.

USER MESSAGE: {user_message}

AGENT ({agent_name}) RESPONSE: {agent_response[:500]}

Extract the following (respond in JSON):
{{
    "facts": ["list of factual statements the user made or confirmed"],
    "preferences": ["list of user preferences revealed"],
    "decisions": ["any decisions the user made"],
    "goals_mentioned": ["any goals or aspirations mentioned"],
    "entities": ["people, companies, or projects mentioned"],
    "mood_signal": "positive|neutral|negative|none",
    "importance": 1-10,
    "summary": "one-line summary of what happened"
}}

If nothing notable, return {{"facts": [], "preferences": [], "decisions": [], "goals_mentioned": [], "entities": [], "mood_signal": "none", "importance": 1, "summary": "routine interaction"}}"""

        try:
            response = self.llm.invoke([
                SystemMessage(content="You are a memory extraction engine. Respond ONLY with valid JSON."),
                HumanMessage(content=prompt),
            ])

            # Parse JSON from response
            raw = response.content.strip()
            # Handle markdown code blocks
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()

            extracted = json.loads(raw)

        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Reflection extraction failed: {e}")
            extracted = {
                "facts": [], "preferences": [], "decisions": [],
                "goals_mentioned": [], "entities": [],
                "mood_signal": "none", "importance": 3,
                "summary": f"Conversation with {agent_name}",
            }

        # Store extracted items in the memory bank
        stored_ids = []

        for fact in extracted.get("facts", []):
            if fact and len(fact) > 5:
                mid = bank.retain(fact, memory_type="fact", importance=extracted.get("importance", 5))
                stored_ids.append(mid)

        for pref in extracted.get("preferences", []):
            if pref and len(pref) > 5:
                mid = bank.retain(pref, memory_type="preference", importance=7)
                stored_ids.append(mid)

        for decision in extracted.get("decisions", []):
            if decision and len(decision) > 5:
                mid = bank.retain(decision, memory_type="decision", importance=8)
                stored_ids.append(mid)

        for goal in extracted.get("goals_mentioned", []):
            if goal and len(goal) > 5:
                mid = bank.retain(goal, memory_type="goal", importance=9)
                stored_ids.append(mid)

        for entity in extracted.get("entities", []):
            if entity and len(entity) > 2:
                mid = bank.retain(entity, memory_type="entity", importance=5)
                stored_ids.append(mid)

        # Link related memories
        if len(stored_ids) > 1:
            for i in range(len(stored_ids) - 1):
                bank.link(stored_ids[i], stored_ids[i + 1], "same_session")

        # Append to daily log
        summary = extracted.get("summary", "interaction")
        daily.append(
            f"**{agent_name}**: {summary}\n"
            f"- Facts: {len(extracted.get('facts', []))}\n"
            f"- Preferences: {len(extracted.get('preferences', []))}\n"
            f"- Mood: {extracted.get('mood_signal', 'none')}",
            category=agent_name,
        )

        logger.info(
            f"Reflection: {len(stored_ids)} memories stored from {agent_name} session"
        )

        return {
            "stored_memories": len(stored_ids),
            "memory_ids": stored_ids,
            "extracted": extracted,
        }

    # ------------------------------------------------------------------
    # 2. PATTERN DETECTION — runs during heartbeats
    # ------------------------------------------------------------------

    def detect_patterns(self, days: int = 7) -> list[dict[str, Any]]:
        """Analyze recent memories to detect recurring patterns.

        Looks for:
        - Repeated topics or concerns
        - Behavioral cycles (e.g., mood drops on Mondays)
        - Emerging interests or shifting priorities
        - Relationship patterns
        """
        from src.memory.evolving_memory import get_memory_bank

        bank = get_memory_bank()
        recent = bank.get_recent(hours=days * 24, limit=100)

        if len(recent) < 5:
            return []

        # Group by type for analysis
        by_type: dict[str, list[str]] = {}
        for mem in recent:
            by_type.setdefault(mem.memory_type, []).append(mem.content)

        # Build analysis prompt
        memory_summary = ""
        for mtype, contents in by_type.items():
            memory_summary += f"\n## {mtype} ({len(contents)} items)\n"
            for c in contents[:10]:
                memory_summary += f"- {c}\n"

        prompt = f"""Analyze these memories from the last {days} days and detect patterns.

{memory_summary}

Identify:
1. Recurring themes or concerns
2. Behavioral patterns (time-based, mood-based)
3. Emerging interests (new topics appearing frequently)
4. Shifting priorities (goals that are getting more/less attention)

Respond in JSON:
{{
    "patterns": [
        {{
            "description": "description of the pattern",
            "type": "recurring_theme|behavioral|emerging_interest|priority_shift",
            "confidence": 0.0-1.0,
            "evidence": ["specific memories that support this"],
            "recommendation": "what to do about it"
        }}
    ]
}}"""

        try:
            response = self.llm.invoke([
                SystemMessage(content="You are a pattern detection engine. Respond ONLY with valid JSON."),
                HumanMessage(content=prompt),
            ])

            raw = response.content.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()

            result = json.loads(raw)
            patterns = result.get("patterns", [])

            # Store detected patterns as memories
            for pattern in patterns:
                if pattern.get("confidence", 0) > 0.5:
                    bank.retain(
                        content=pattern["description"],
                        memory_type="pattern",
                        confidence=pattern["confidence"],
                        importance=7,
                        source="reflection",
                        tags=[pattern.get("type", "unknown")],
                        evidence=pattern.get("evidence", []),
                    )

            logger.info(f"Pattern detection: {len(patterns)} patterns found")
            return patterns

        except Exception as e:
            logger.warning(f"Pattern detection failed: {e}")
            return []

    # ------------------------------------------------------------------
    # 3. IDEA ENGINE — connects dots to generate insights
    # ------------------------------------------------------------------

    def generate_ideas(self, focus_area: str | None = None) -> list[dict[str, str]]:
        """Generate novel ideas by connecting disparate memories.

        This is the "aha moment" engine. It:
        - Pulls memories from different domains
        - Asks the LLM to find unexpected connections
        - Produces actionable ideas
        """
        from src.memory.evolving_memory import get_memory_bank

        bank = get_memory_bank()

        # Get diverse memories (different types)
        facts = bank.recall(memory_type="fact", limit=10)
        goals = bank.recall(memory_type="goal", limit=5)
        patterns = bank.recall(memory_type="pattern", limit=5)
        experiences = bank.recall(memory_type="experience", limit=10)
        opinions = bank.recall(memory_type="opinion", limit=5)

        all_memories = facts + goals + patterns + experiences + opinions
        if len(all_memories) < 5:
            return []

        memory_dump = "\n".join([
            f"- [{m.memory_type}] {m.content} (confidence: {m.confidence:.1f})"
            for m in all_memories
        ])

        focus = f"\nFocus area: {focus_area}" if focus_area else ""

        prompt = f"""You are an innovation engine. Given these diverse memories about a user,
generate creative ideas by connecting disparate concepts.{focus}

MEMORIES:
{memory_dump}

Generate 3-5 novel ideas that:
1. Connect concepts from different domains
2. Are actionable (can be started this week)
3. Leverage the user's existing skills and knowledge
4. Address their goals or emerging patterns

Respond in JSON:
{{
    "ideas": [
        {{
            "title": "Short title",
            "description": "2-3 sentence description",
            "connections": ["memory1", "memory2"],
            "effort": "low|medium|high",
            "impact": "low|medium|high",
            "first_step": "Concrete first action"
        }}
    ]
}}"""

        try:
            response = self.llm.invoke([
                SystemMessage(content="You are a creative innovation engine. Respond ONLY with valid JSON."),
                HumanMessage(content=prompt),
            ])

            raw = response.content.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()

            result = json.loads(raw)
            ideas = result.get("ideas", [])

            # Store high-impact ideas as insights
            for idea in ideas:
                if idea.get("impact") in ("medium", "high"):
                    bank.retain(
                        content=f"{idea['title']}: {idea['description']}",
                        memory_type="insight",
                        importance=8,
                        source="idea_engine",
                        tags=["generated_idea", idea.get("effort", "medium")],
                    )

            logger.info(f"Idea engine: {len(ideas)} ideas generated")
            return ideas

        except Exception as e:
            logger.warning(f"Idea generation failed: {e}")
            return []

    # ------------------------------------------------------------------
    # 4. MEMORY CURATION — promote to MEMORY.md
    # ------------------------------------------------------------------

    def curate_memory_file(self) -> str:
        """Generate updated MEMORY.md content from the memory bank.

        Promotes the most important and confident memories to the
        workspace MEMORY.md file for workspace context injection.
        """
        from src.memory.evolving_memory import get_memory_bank

        bank = get_memory_bank()
        stats = bank.stats()

        # Get top memories by type
        sections = {
            "User Core Facts": bank.recall(memory_type="fact", min_importance=6, limit=15),
            "Key Decisions": bank.recall(memory_type="decision", min_importance=6, limit=10),
            "Active Projects": bank.recall(memory_type="entity", limit=10, tags=["project"]),
            "Recurring Patterns": bank.recall(memory_type="pattern", limit=10),
            "Important Relationships": bank.recall(memory_type="entity", limit=10),
            "Strategic Goals": bank.recall(memory_type="goal", limit=10),
        }

        lines = ["# MEMORY — Curated Long-Term Memory\n"]
        lines.append("> Auto-generated by the Cognitive Loop. Do not edit manually.\n")

        for section_name, memories in sections.items():
            lines.append(f"\n## {section_name}\n")
            if memories:
                for mem in memories:
                    conf = f" (conf: {mem.confidence:.0%})" if mem.confidence < 1.0 else ""
                    lines.append(f"- {mem.content}{conf}")
            else:
                lines.append("*No data yet.*")

        lines.append(f"\n---\n")
        lines.append(f"*Last updated: {datetime.now().isoformat()}*")
        lines.append(f"*Total memories in bank: {stats['total_memories']}*")
        lines.append(f"*Active: {stats['active_memories']} | Superseded: {stats['superseded']}*")
        lines.append(f"*Avg confidence: {stats['avg_confidence']:.0%}*")

        content = "\n".join(lines)

        # Write to workspace
        try:
            from src.core.workspace_loader import get_workspace_loader
            loader = get_workspace_loader()
            loader.update_memory(content)
        except Exception as e:
            logger.error(f"Failed to update MEMORY.md: {e}")

        return content

    # ------------------------------------------------------------------
    # 5. FULL REFLECTION CYCLE — runs during deep reflection
    # ------------------------------------------------------------------

    def run_full_cycle(self, focus_area: str | None = None) -> dict[str, Any]:
        """Run a complete cognitive cycle:
        1. Detect patterns in recent memories
        2. Generate ideas from connected memories
        3. Curate MEMORY.md with top memories
        4. Clean up low-confidence memories

        Returns summary of what was done.
        """
        from src.memory.evolving_memory import get_memory_bank

        bank = get_memory_bank()

        results = {
            "timestamp": datetime.now().isoformat(),
            "patterns": [],
            "ideas": [],
            "memory_stats": {},
            "cleaned_up": 0,
        }

        # 1. Pattern detection
        try:
            patterns = self.detect_patterns(days=7)
            results["patterns"] = patterns
        except Exception as e:
            logger.error(f"Pattern detection failed in full cycle: {e}")

        # 2. Idea generation
        try:
            ideas = self.generate_ideas(focus_area=focus_area)
            results["ideas"] = ideas
        except Exception as e:
            logger.error(f"Idea generation failed in full cycle: {e}")

        # 3. Curate MEMORY.md
        try:
            self.curate_memory_file()
        except Exception as e:
            logger.error(f"Memory curation failed in full cycle: {e}")

        # 4. Cleanup
        try:
            cleaned = bank.cleanup_low_confidence(threshold=0.1)
            results["cleaned_up"] = cleaned
        except Exception as e:
            logger.error(f"Memory cleanup failed in full cycle: {e}")

        results["memory_stats"] = bank.stats()

        logger.info(
            f"Full cognitive cycle complete: "
            f"{len(results['patterns'])} patterns, "
            f"{len(results['ideas'])} ideas, "
            f"{results['cleaned_up']} archived"
        )

        return results


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_cognitive: CognitiveLoop | None = None


def get_cognitive_loop() -> CognitiveLoop:
    global _cognitive
    if _cognitive is None:
        _cognitive = CognitiveLoop()
    return _cognitive
