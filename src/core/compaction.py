"""Context Compaction Engine — Intelligent context window management.

When the conversation gets too long for the model's context window,
this engine compresses the history while preserving critical information.

Inspired by OpenClaw's compaction system:
• Detect when approaching token limits
• Summarize older messages via LLM
• Preserve recent messages, tool results, and critical facts
• Maintain compaction metadata
• Never lose important information

Strategy:
1. Keep last N messages verbatim (recent context)
2. Summarize older messages into a condensed "memory" block
3. Always preserve: system prompts, tool results, user decisions
4. Store full history in session store (never truly deleted)
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Token estimation (rough, no tokenizer needed)
# ---------------------------------------------------------------------------

def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English, ~3 for mixed."""
    return max(1, len(text) // 3)


def estimate_messages_tokens(messages: list[BaseMessage]) -> int:
    """Estimate total tokens in a list of messages."""
    total = 0
    for msg in messages:
        content = msg.content if isinstance(msg.content, str) else str(msg.content)
        total += estimate_tokens(content) + 4  # overhead per message
    return total


# ---------------------------------------------------------------------------
# Compaction Engine
# ---------------------------------------------------------------------------

class CompactionEngine:
    """Manages context window compaction for conversations."""

    def __init__(
        self,
        max_context_tokens: int = 6000,     # Target max context size
        keep_recent: int = 8,                # Always keep last N messages verbatim
        compaction_threshold: float = 0.75,  # Trigger at 75% of max
    ) -> None:
        self.max_context_tokens = max_context_tokens
        self.keep_recent = keep_recent
        self.compaction_threshold = compaction_threshold
        self._llm = None

    @property
    def llm(self):
        if self._llm is None:
            from src.core.model_router import get_model_router, Complexity, Privacy
            router = get_model_router()
            self._llm = router.get_llm(
                complexity=Complexity.LIGHT,
                privacy=Privacy.PRIVATE,
            )
        return self._llm

    def needs_compaction(self, messages: list[BaseMessage]) -> bool:
        """Check if the message list needs compaction."""
        tokens = estimate_messages_tokens(messages)
        threshold = int(self.max_context_tokens * self.compaction_threshold)
        return tokens > threshold

    def compact(
        self,
        messages: list[BaseMessage],
        preserve_system: bool = True,
    ) -> list[BaseMessage]:
        """Compact a message list by summarizing older messages.

        Args:
            messages: Full message list
            preserve_system: Keep SystemMessages as-is

        Returns:
            Compacted message list
        """
        if not self.needs_compaction(messages):
            return messages

        # Separate system messages
        system_msgs = [m for m in messages if isinstance(m, SystemMessage)] if preserve_system else []
        non_system = [m for m in messages if not isinstance(m, SystemMessage)]

        if len(non_system) <= self.keep_recent:
            return messages  # Not enough to compact

        # Split: old messages to summarize, recent to keep
        to_summarize = non_system[:-self.keep_recent]
        to_keep = non_system[-self.keep_recent:]

        # Extract critical items from old messages (tool results, decisions)
        critical_items = self._extract_critical(to_summarize)

        # Summarize old messages
        summary = self._summarize(to_summarize)

        # Build compacted list
        result = list(system_msgs)

        # Add summary as a SystemMessage
        summary_content = f"## 📝 CONVERSATION SUMMARY (compacted)\n\n{summary}"
        if critical_items:
            summary_content += f"\n\n### Critical Items Preserved:\n{critical_items}"

        result.append(SystemMessage(content=summary_content))
        result.extend(to_keep)

        old_tokens = estimate_messages_tokens(messages)
        new_tokens = estimate_messages_tokens(result)

        logger.info(
            f"Compaction: {len(messages)} msgs ({old_tokens} tokens) "
            f"→ {len(result)} msgs ({new_tokens} tokens) "
            f"[{(1 - new_tokens/old_tokens)*100:.0f}% reduction]"
        )

        return result

    def _extract_critical(self, messages: list[BaseMessage]) -> str:
        """Extract critical items that should never be lost."""
        critical = []

        for msg in messages:
            content = msg.content if isinstance(msg.content, str) else str(msg.content)

            # Preserve tool results
            if isinstance(msg, ToolMessage):
                name = getattr(msg, "name", "tool")
                critical.append(f"- Tool [{name}]: {content[:200]}")

            # Preserve user decisions (messages with strong intent signals)
            if isinstance(msg, HumanMessage):
                decision_markers = [
                    "sí", "si", "yes", "dale", "hazlo", "quiero", "decide",
                    "compra", "vende", "cancela", "confirma", "acepto",
                ]
                content_lower = content.lower()
                if any(m in content_lower for m in decision_markers):
                    critical.append(f"- User decision: {content[:200]}")

        return "\n".join(critical) if critical else ""

    def _summarize(self, messages: list[BaseMessage]) -> str:
        """Summarize a list of messages into a concise summary."""
        # Build conversation text
        conv_parts = []
        for msg in messages:
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            if isinstance(msg, HumanMessage):
                conv_parts.append(f"User: {content}")
            elif isinstance(msg, AIMessage):
                name = getattr(msg, "name", "assistant")
                conv_parts.append(f"{name}: {content[:300]}")
            elif isinstance(msg, ToolMessage):
                name = getattr(msg, "name", "tool")
                conv_parts.append(f"[Tool {name}]: {content[:200]}")

        conversation = "\n".join(conv_parts)

        # Truncate if too long for summarization
        if len(conversation) > 3000:
            conversation = conversation[:3000] + "\n... (truncated)"

        try:
            prompt = (
                "Summarize this conversation concisely. Preserve:\n"
                "1. Key facts and decisions made\n"
                "2. User's requests and what was accomplished\n"
                "3. Any important data or numbers mentioned\n"
                "4. Emotional context if relevant\n\n"
                "Keep it under 200 words.\n\n"
                f"CONVERSATION:\n{conversation}"
            )

            response = self.llm.invoke([
                SystemMessage(content="You are a conversation summarizer. Be concise and factual."),
                HumanMessage(content=prompt),
            ])

            return response.content.strip()

        except Exception as e:
            logger.warning(f"LLM summarization failed, using extractive: {e}")
            # Fallback: extractive summary (just user messages)
            user_msgs = [
                msg.content[:100] for msg in messages
                if isinstance(msg, HumanMessage) and msg.content
            ]
            return "Previous topics: " + "; ".join(user_msgs[-5:])


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_engine: CompactionEngine | None = None


def get_compaction_engine() -> CompactionEngine:
    global _engine
    if _engine is None:
        _engine = CompactionEngine()
    return _engine
