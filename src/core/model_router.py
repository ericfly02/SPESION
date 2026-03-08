"""Intelligent Model Router — OpenClaw-grade multi-provider routing.

Replaces the simple LLMFactory with:
• Per-agent model configuration (overrides defaults)
• Fallback chains with automatic failover
• Model health monitoring + cooldown on auth failures
• Task-complexity-based provider selection
• Privacy-aware routing (sensitive data → always local)

Architecture (inspired by OpenClaw's ``runWithModelFallback``):

    1.  Resolve candidate list:  agent-override → task-default → global-default
    2.  For each candidate, check health & cooldown
    3.  Attempt inference; on failure, advance to next candidate
    4.  Record health event (success/failure/cooldown)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from langchain_core.language_models import BaseChatModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Provider(str, Enum):
    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class Complexity(str, Enum):
    """Task complexity tiers — determines which provider tier to prefer."""
    TRIVIAL = "trivial"       # greeting, routing decisions → small local
    LIGHT = "light"           # simple Q&A, chat → local 3B
    MODERATE = "moderate"     # summarisation, basic analysis → local 7-8B
    HEAVY = "heavy"           # deep analysis, long context → cloud
    CRITICAL = "critical"     # code gen, research synthesis → best available cloud


class Privacy(str, Enum):
    PUBLIC = "public"         # can go to cloud
    SENSITIVE = "sensitive"   # prefer local, cloud OK if local down
    PRIVATE = "private"       # must stay local, never cloud


# ---------------------------------------------------------------------------
# Model Spec — a single model candidate
# ---------------------------------------------------------------------------

@dataclass
class ModelSpec:
    """One model candidate in a fallback chain."""
    provider: Provider
    model_name: str
    max_tokens: int = 4096
    supports_tools: bool = True
    supports_vision: bool = False
    context_window: int = 8192
    cost_per_1k_input: float = 0.0     # USD, 0 = free (local)
    cost_per_1k_output: float = 0.0

    @property
    def key(self) -> str:
        return f"{self.provider.value}:{self.model_name}"


# ---------------------------------------------------------------------------
# Default Model Catalog
# ---------------------------------------------------------------------------

MODEL_CATALOG: dict[str, ModelSpec] = {
    # Ollama local
    "ollama:llama3.2:3b": ModelSpec(
        provider=Provider.OLLAMA, model_name="llama3.2:3b",
        context_window=8192, cost_per_1k_input=0, cost_per_1k_output=0,
    ),
    "ollama:qwen2.5:7b": ModelSpec(
        provider=Provider.OLLAMA, model_name="qwen2.5:7b",
        context_window=32768, cost_per_1k_input=0, cost_per_1k_output=0,
    ),
    "ollama:llama3.1:8b": ModelSpec(
        provider=Provider.OLLAMA, model_name="llama3.1:8b",
        context_window=131072, cost_per_1k_input=0, cost_per_1k_output=0,
    ),
    "ollama:deepseek-r1:8b": ModelSpec(
        provider=Provider.OLLAMA, model_name="deepseek-r1:8b",
        context_window=65536, cost_per_1k_input=0, cost_per_1k_output=0,
    ),
    # OpenAI cloud
    "openai:gpt-4o": ModelSpec(
        provider=Provider.OPENAI, model_name="gpt-4o",
        context_window=128000, supports_vision=True,
        cost_per_1k_input=0.0025, cost_per_1k_output=0.01,
    ),
    "openai:gpt-4o-mini": ModelSpec(
        provider=Provider.OPENAI, model_name="gpt-4o-mini",
        context_window=128000, supports_vision=True,
        cost_per_1k_input=0.00015, cost_per_1k_output=0.0006,
    ),
    "openai:o3-mini": ModelSpec(
        provider=Provider.OPENAI, model_name="o3-mini",
        context_window=128000,
        cost_per_1k_input=0.0011, cost_per_1k_output=0.0044,
    ),
    # Anthropic cloud
    "anthropic:claude-sonnet-4-20250514": ModelSpec(
        provider=Provider.ANTHROPIC, model_name="claude-sonnet-4-20250514",
        context_window=200000, supports_vision=True,
        cost_per_1k_input=0.003, cost_per_1k_output=0.015,
    ),
    "anthropic:claude-3-5-haiku-20241022": ModelSpec(
        provider=Provider.ANTHROPIC, model_name="claude-3-5-haiku-20241022",
        context_window=200000,
        cost_per_1k_input=0.0008, cost_per_1k_output=0.004,
    ),
}


# ---------------------------------------------------------------------------
# Per-agent default model configs
# ---------------------------------------------------------------------------

# Complexity mapping per agent (what the agent typically handles)
AGENT_COMPLEXITY: dict[str, Complexity] = {
    "supervisor": Complexity.TRIVIAL,     # just routing — use small local
    "sentinel": Complexity.LIGHT,         # PII checks, status — local
    "companion": Complexity.LIGHT,        # journaling — local (privacy)
    "coach": Complexity.LIGHT,            # fitness — local
    "executive": Complexity.MODERATE,     # scheduling — local or light cloud
    "connector": Complexity.MODERATE,     # networking — moderate
    "scholar": Complexity.HEAVY,          # deep research — cloud
    "tycoon": Complexity.HEAVY,           # financial analysis — cloud
    "techlead": Complexity.CRITICAL,      # code generation — best cloud
}

# Privacy classification per agent
AGENT_PRIVACY: dict[str, Privacy] = {
    "companion": Privacy.PRIVATE,    # emotional data stays local
    "coach": Privacy.SENSITIVE,      # health data prefers local
    "sentinel": Privacy.PRIVATE,     # security data stays local
    "scholar": Privacy.PUBLIC,
    "tycoon": Privacy.SENSITIVE,     # financial data prefers local
    "techlead": Privacy.PUBLIC,
    "connector": Privacy.PUBLIC,
    "executive": Privacy.PUBLIC,
    "supervisor": Privacy.PUBLIC,
}


# ---------------------------------------------------------------------------
# Fallback Chains — ordered list of models to try for each complexity tier
# ---------------------------------------------------------------------------

DEFAULT_FALLBACK_CHAINS: dict[Complexity, list[str]] = {
    Complexity.TRIVIAL: [
        "ollama:llama3.2:3b",
    ],
    Complexity.LIGHT: [
        "ollama:llama3.2:3b",
        "ollama:qwen2.5:7b",
    ],
    Complexity.MODERATE: [
        "ollama:qwen2.5:7b",
        "ollama:llama3.1:8b",
        "openai:gpt-4o-mini",
        "anthropic:claude-3-5-haiku-20241022",
    ],
    Complexity.HEAVY: [
        "openai:gpt-4o",
        "anthropic:claude-sonnet-4-20250514",
        "ollama:qwen2.5:7b",
    ],
    Complexity.CRITICAL: [
        "anthropic:claude-sonnet-4-20250514",
        "openai:gpt-4o",
        "openai:o3-mini",
        "ollama:deepseek-r1:8b",
    ],
}

# When privacy forces local-only, use these chains
LOCAL_ONLY_CHAINS: dict[Complexity, list[str]] = {
    Complexity.TRIVIAL: ["ollama:llama3.2:3b"],
    Complexity.LIGHT: ["ollama:llama3.2:3b", "ollama:qwen2.5:7b"],
    Complexity.MODERATE: ["ollama:qwen2.5:7b", "ollama:llama3.1:8b"],
    Complexity.HEAVY: ["ollama:qwen2.5:7b", "ollama:deepseek-r1:8b", "ollama:llama3.1:8b"],
    Complexity.CRITICAL: ["ollama:deepseek-r1:8b", "ollama:qwen2.5:7b", "ollama:llama3.1:8b"],
}


# ---------------------------------------------------------------------------
# Health Tracker — monitors provider/model health and manages cooldowns
# ---------------------------------------------------------------------------

@dataclass
class HealthEntry:
    last_success: float = 0.0
    last_failure: float = 0.0
    consecutive_failures: int = 0
    cooldown_until: float = 0.0
    total_calls: int = 0
    total_failures: int = 0
    total_latency_ms: float = 0.0

    @property
    def avg_latency_ms(self) -> float:
        successful = self.total_calls - self.total_failures
        return self.total_latency_ms / successful if successful > 0 else 0

    @property
    def is_cooled_down(self) -> bool:
        return time.time() < self.cooldown_until

    @property
    def success_rate(self) -> float:
        return (self.total_calls - self.total_failures) / self.total_calls if self.total_calls > 0 else 1.0


class HealthTracker:
    """Tracks model health across providers with exponential backoff cooldowns."""

    COOLDOWN_BASE_S = 30       # 30s base cooldown
    COOLDOWN_MAX_S = 600       # 10min max cooldown
    COOLDOWN_MULTIPLIER = 2.0

    def __init__(self) -> None:
        self._entries: dict[str, HealthEntry] = {}

    def _get(self, key: str) -> HealthEntry:
        if key not in self._entries:
            self._entries[key] = HealthEntry()
        return self._entries[key]

    def is_available(self, model_key: str) -> bool:
        entry = self._get(model_key)
        return not entry.is_cooled_down

    def record_success(self, model_key: str, latency_ms: float) -> None:
        entry = self._get(model_key)
        entry.last_success = time.time()
        entry.consecutive_failures = 0
        entry.cooldown_until = 0.0
        entry.total_calls += 1
        entry.total_latency_ms += latency_ms

    def record_failure(self, model_key: str, error: str = "") -> None:
        entry = self._get(model_key)
        entry.last_failure = time.time()
        entry.consecutive_failures += 1
        entry.total_calls += 1
        entry.total_failures += 1

        # Exponential backoff cooldown
        cooldown = min(
            self.COOLDOWN_BASE_S * (self.COOLDOWN_MULTIPLIER ** (entry.consecutive_failures - 1)),
            self.COOLDOWN_MAX_S,
        )
        entry.cooldown_until = time.time() + cooldown
        logger.warning(
            f"Model {model_key} failed ({entry.consecutive_failures}x). "
            f"Cooldown {cooldown:.0f}s. Error: {error[:100]}"
        )

    def get_status(self) -> dict[str, dict[str, Any]]:
        """Returns health status for all tracked models."""
        status = {}
        for key, entry in self._entries.items():
            status[key] = {
                "available": not entry.is_cooled_down,
                "success_rate": f"{entry.success_rate:.1%}",
                "avg_latency_ms": f"{entry.avg_latency_ms:.0f}",
                "consecutive_failures": entry.consecutive_failures,
                "total_calls": entry.total_calls,
            }
        return status


# ---------------------------------------------------------------------------
# ModelRouter — the main router
# ---------------------------------------------------------------------------

class ModelRouter:
    """Intelligent model router with fallback chains and health monitoring.

    Usage::

        router = get_model_router()
        llm = router.get_llm(agent_name="scholar", temperature=0.7)
        llm = router.get_llm(complexity=Complexity.HEAVY, privacy=Privacy.PUBLIC)
    """

    def __init__(self) -> None:
        from src.core.config import settings
        self.settings = settings
        self.health = HealthTracker()

        # Per-agent model overrides (loaded from config or workspace)
        self._agent_overrides: dict[str, list[str]] = {}

        # Provider availability cache
        self._provider_available: dict[Provider, bool | None] = {
            Provider.OLLAMA: None,
            Provider.OPENAI: None,
            Provider.ANTHROPIC: None,
        }

    # ------------------------------------------------------------------
    # Provider availability
    # ------------------------------------------------------------------

    def _check_provider(self, provider: Provider) -> bool:
        """Check if a provider is configured and reachable."""
        if provider == Provider.OLLAMA:
            return self._check_ollama()
        elif provider == Provider.OPENAI:
            return self._has_api_key("openai")
        elif provider == Provider.ANTHROPIC:
            return self._has_api_key("anthropic")
        return False

    def _check_ollama(self) -> bool:
        import httpx
        try:
            resp = httpx.get(
                f"{self.settings.llm.ollama_base_url}/api/tags",
                timeout=5.0,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def _has_api_key(self, provider: str) -> bool:
        if provider == "openai":
            key = self.settings.llm.openai_api_key
            return key is not None and key.get_secret_value() != ""
        elif provider == "anthropic":
            key = self.settings.llm.anthropic_api_key
            return key is not None and key.get_secret_value() != ""
        return False

    def is_provider_available(self, provider: Provider) -> bool:
        """Cached provider availability check."""
        if self._provider_available[provider] is None:
            self._provider_available[provider] = self._check_provider(provider)
        return self._provider_available[provider]

    def refresh_availability(self) -> None:
        """Force re-check of all providers."""
        self._provider_available = {p: None for p in Provider}

    # ------------------------------------------------------------------
    # Model instantiation
    # ------------------------------------------------------------------

    def _create_llm(self, spec: ModelSpec, temperature: float = 0.7) -> BaseChatModel:
        """Instantiate a LangChain chat model from a ModelSpec."""
        if spec.provider == Provider.OLLAMA:
            from langchain_ollama import ChatOllama
            return ChatOllama(
                base_url=self.settings.llm.ollama_base_url,
                model=spec.model_name,
                temperature=temperature,
            )
        elif spec.provider == Provider.OPENAI:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                api_key=self.settings.llm.openai_api_key.get_secret_value(),
                model=spec.model_name,
                temperature=temperature,
            )
        elif spec.provider == Provider.ANTHROPIC:
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                api_key=self.settings.llm.anthropic_api_key.get_secret_value(),
                model=spec.model_name,
                temperature=temperature,
            )
        raise ValueError(f"Unknown provider: {spec.provider}")

    # ------------------------------------------------------------------
    # Fallback chain resolution
    # ------------------------------------------------------------------

    def _resolve_chain(
        self,
        agent_name: str | None = None,
        complexity: Complexity | None = None,
        privacy: Privacy = Privacy.PUBLIC,
    ) -> list[ModelSpec]:
        """Resolve the ordered fallback chain of model candidates."""
        # 1. Determine complexity
        if complexity is None:
            complexity = AGENT_COMPLEXITY.get(agent_name, Complexity.MODERATE) if agent_name else Complexity.MODERATE

        # 2. Determine privacy
        if agent_name and privacy == Privacy.PUBLIC:
            privacy = AGENT_PRIVACY.get(agent_name, Privacy.PUBLIC)

        # 3. Check agent-level overrides first
        if agent_name and agent_name in self._agent_overrides:
            override_keys = self._agent_overrides[agent_name]
            chain = [MODEL_CATALOG[k] for k in override_keys if k in MODEL_CATALOG]
            if chain:
                # Filter by privacy
                if privacy == Privacy.PRIVATE:
                    chain = [s for s in chain if s.provider == Provider.OLLAMA]
                return chain

        # 4. Select chain based on privacy
        if privacy == Privacy.PRIVATE:
            chain_keys = LOCAL_ONLY_CHAINS.get(complexity, LOCAL_ONLY_CHAINS[Complexity.LIGHT])
        elif privacy == Privacy.SENSITIVE:
            # Prefer local, but allow cloud as last resort
            local_keys = LOCAL_ONLY_CHAINS.get(complexity, [])
            cloud_keys = DEFAULT_FALLBACK_CHAINS.get(complexity, [])
            chain_keys = local_keys + [k for k in cloud_keys if k not in local_keys]
        else:
            chain_keys = DEFAULT_FALLBACK_CHAINS.get(complexity, DEFAULT_FALLBACK_CHAINS[Complexity.MODERATE])

        return [MODEL_CATALOG[k] for k in chain_keys if k in MODEL_CATALOG]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_llm(
        self,
        agent_name: str | None = None,
        complexity: Complexity | None = None,
        privacy: Privacy | None = None,
        temperature: float = 0.7,
    ) -> BaseChatModel:
        """Get the best available LLM, walking the fallback chain.

        Args:
            agent_name: Agent requesting the LLM (for defaults)
            complexity: Override complexity tier
            privacy: Override privacy classification
            temperature: Generation temperature

        Returns:
            A LangChain BaseChatModel ready to use

        Raises:
            RuntimeError: If all candidates in the fallback chain fail
        """
        effective_privacy = privacy or (
            AGENT_PRIVACY.get(agent_name, Privacy.PUBLIC) if agent_name else Privacy.PUBLIC
        )

        chain = self._resolve_chain(
            agent_name=agent_name,
            complexity=complexity,
            privacy=effective_privacy,
        )

        errors: list[str] = []
        for spec in chain:
            # Skip if provider not available
            if not self.is_provider_available(spec.provider):
                errors.append(f"{spec.key}: provider unavailable")
                continue

            # Skip if in cooldown
            if not self.health.is_available(spec.key):
                errors.append(f"{spec.key}: in cooldown")
                continue

            try:
                llm = self._create_llm(spec, temperature=temperature)
                logger.info(
                    f"ModelRouter → {spec.key} "
                    f"(agent={agent_name}, complexity={complexity}, privacy={effective_privacy})"
                )
                return llm
            except Exception as e:
                error_msg = str(e)[:100]
                self.health.record_failure(spec.key, error_msg)
                errors.append(f"{spec.key}: {error_msg}")
                continue

        # All candidates failed — raise with full error chain
        raise RuntimeError(
            f"All model candidates exhausted for agent={agent_name}, "
            f"complexity={complexity}, privacy={effective_privacy}. "
            f"Errors: {'; '.join(errors)}"
        )

    def get_llm_with_record(
        self,
        agent_name: str | None = None,
        complexity: Complexity | None = None,
        privacy: Privacy | None = None,
        temperature: float = 0.7,
    ) -> tuple[BaseChatModel, ModelSpec]:
        """Like get_llm but also returns which model was selected."""
        effective_privacy = privacy or (
            AGENT_PRIVACY.get(agent_name, Privacy.PUBLIC) if agent_name else Privacy.PUBLIC
        )

        chain = self._resolve_chain(
            agent_name=agent_name,
            complexity=complexity,
            privacy=effective_privacy,
        )

        for spec in chain:
            if not self.is_provider_available(spec.provider):
                continue
            if not self.health.is_available(spec.key):
                continue
            try:
                llm = self._create_llm(spec, temperature=temperature)
                return llm, spec
            except Exception as e:
                self.health.record_failure(spec.key, str(e)[:100])
                continue

        raise RuntimeError("All model candidates exhausted")

    def record_success(self, model_key: str, latency_ms: float) -> None:
        """Record a successful inference (called after response received)."""
        self.health.record_success(model_key, latency_ms)

    def record_failure(self, model_key: str, error: str = "") -> None:
        """Record a failed inference."""
        self.health.record_failure(model_key, error)

    def set_agent_override(self, agent_name: str, model_keys: list[str]) -> None:
        """Set per-agent model override chain."""
        self._agent_overrides[agent_name] = model_keys
        logger.info(f"Agent override set: {agent_name} → {model_keys}")

    def get_health_status(self) -> dict:
        """Get full health status report."""
        return {
            "providers": {
                p.value: self.is_provider_available(p) for p in Provider
            },
            "models": self.health.get_status(),
            "agent_overrides": self._agent_overrides,
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_router: ModelRouter | None = None


def get_model_router() -> ModelRouter:
    """Get the singleton ModelRouter instance."""
    global _router
    if _router is None:
        _router = ModelRouter()
    return _router
