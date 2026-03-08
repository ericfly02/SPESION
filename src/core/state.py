"""AgentState definition for LangGraph."""

from __future__ import annotations

from typing import Annotated, Literal, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class UserProfile(TypedDict):
    """Perfil del usuario para contexto."""
    
    name: str
    age: int
    location: str
    occupation: str
    company: str
    interests: list[str]
    projects: list[str]
    fitness_goals: list[str]


class EnergyState(TypedDict):
    """Estado de energía del usuario (del Coach)."""
    
    level: float  # 0.0 - 1.0
    hrv_score: float | None
    sleep_quality: float | None
    recovery_status: Literal["poor", "fair", "good", "excellent"] | None
    last_updated: str | None


class MoodState(TypedDict):
    """Estado emocional del usuario (del Companion)."""
    
    mood: Literal["negative", "neutral", "positive"] | None
    sentiment_score: float  # -1.0 to 1.0
    recent_themes: list[str]
    last_journal_date: str | None


class PrivacyState(TypedDict):
    """Estado de privacidad (del Sentinel)."""
    
    pii_detected: bool
    sanitized_content: str | None
    risk_level: Literal["low", "medium", "high"]
    use_local_llm: bool


class CognitiveState(TypedDict):
    """State for the cognitive loop (SPESION 3.0)."""

    reflection_pending: bool
    last_reflection: str | None
    patterns_detected: list[str]
    ideas_generated: list[str]
    compaction_count: int


class AgentState(TypedDict):
    """Estado compartido del grafo LangGraph.
    
    Este TypedDict define el estado que fluye entre todos los nodos
    del grafo. Cada agente puede leer y modificar este estado.

    SPESION 3.0: Added workspace_context, cognitive state, model tracking.
    """
    
    # Mensajes de la conversación (con reducción automática)
    messages: Annotated[list[BaseMessage], add_messages]
    
    # Control de flujo
    sender: str  # Agente que envió el último mensaje
    next_agent: str | None  # Siguiente agente a invocar (None = finalizar)
    
    # Contexto del usuario
    user_id: str
    user_profile: UserProfile | None
    
    # Estados de sub-sistemas
    energy: EnergyState
    mood: MoodState
    privacy: PrivacyState
    
    # RAG Context
    retrieved_context: list[str]
    
    # Workspace context (SPESION 3.0) — injected from workspace files
    workspace_context: str
    
    # Cognitive loop state (SPESION 3.0)
    cognitive: CognitiveState
    
    # Model tracking (SPESION 3.0) — which model is being used
    model_key: str | None
    
    # Autonomous execution (SPESION 3.0) — plan tracking
    active_plan_id: str | None
    pending_approval_step: str | None
    
    # Metadatos de la sesión
    session_id: str
    telegram_chat_id: int | None
    is_voice_message: bool
    original_query: str
    
    # Flags de control
    requires_tool_execution: bool
    tool_results: list[dict] | None


def create_initial_state(
    user_id: str,
    session_id: str,
    telegram_chat_id: int | None = None,
) -> AgentState:
    """Crea un estado inicial vacío para una nueva conversación."""
    return AgentState(
        messages=[],
        sender="user",
        next_agent="supervisor",
        user_id=user_id,
        user_profile=None,
        energy=EnergyState(
            level=0.7,
            hrv_score=None,
            sleep_quality=None,
            recovery_status=None,
            last_updated=None,
        ),
        mood=MoodState(
            mood=None,
            sentiment_score=0.0,
            recent_themes=[],
            last_journal_date=None,
        ),
        privacy=PrivacyState(
            pii_detected=False,
            sanitized_content=None,
            risk_level="low",
            use_local_llm=False,
        ),
        retrieved_context=[],
        workspace_context="",
        cognitive=CognitiveState(
            reflection_pending=False,
            last_reflection=None,
            patterns_detected=[],
            ideas_generated=[],
            compaction_count=0,
        ),
        model_key=None,
        session_id=session_id,
        telegram_chat_id=telegram_chat_id,
        is_voice_message=False,
        original_query="",
        requires_tool_execution=False,
        tool_results=None,
    )


# Definición de los agentes disponibles
AGENT_NAMES = Literal[
    "supervisor",
    "scholar",
    "coach", 
    "tycoon",
    "companion",
    "techlead",
    "connector",
    "executive",
    "sentinel",
]

# Mapeo de intents a agentes
INTENT_TO_AGENT: dict[str, str] = {
    "research": "scholar",
    "papers": "scholar",
    "news": "scholar",
    "arxiv": "scholar",
    "health": "coach",
    "fitness": "coach",
    "workout": "coach",
    "training": "coach",
    "running": "coach",
    "sleep": "coach",
    "finance": "tycoon",
    "portfolio": "tycoon",
    "investment": "tycoon",
    "stocks": "tycoon",
    "crypto": "tycoon",
    "emotional": "companion",
    "journal": "companion",
    "feelings": "companion",
    "mood": "companion",
    "therapy": "companion",
    "coding": "techlead",
    "code": "techlead",
    "review": "techlead",
    "debug": "techlead",
    "architecture": "techlead",
    "algorithm": "techlead",
    "networking": "connector",
    "contacts": "connector",
    "linkedin": "connector",
    "crm": "connector",
    "events": "connector",
    "productivity": "executive",
    "calendar": "executive",
    "tasks": "executive",
    "schedule": "executive",
    "priorities": "executive",
    "security": "sentinel",
    "privacy": "sentinel",
    "audit": "sentinel",
    "system": "sentinel",
}

