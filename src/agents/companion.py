"""Companion Agent - Bienestar emocional y journaling."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.tools import BaseTool

from .base_agent import BaseAgent
from src.core.prompts import get_agent_prompt

if TYPE_CHECKING:
    from src.core.state import AgentState

logger = logging.getLogger(__name__)


class CompanionAgent(BaseAgent):
    """Agente Companion - Psicólogo/compañero emocional.
    
    Responsabilidades:
    - Journaling nocturno guiado
    - Análisis de sentimiento y patrones emocionales
    - Apoyo emocional estoico pero empático
    - Memoria a largo plazo de conversaciones importantes
    
    IMPORTANTE:
    - SIEMPRE usa LLM local por privacidad
    - Guarda insights importantes en ChromaDB
    - Si detecta crisis seria → sugiere ayuda profesional
    
    Contexto del usuario:
    - Ruptura dolorosa hace 2 años
    - Valora honestidad brutal con tacto
    - Prefiere soluciones prácticas sobre consuelo vacío
    """
    
    # Temas sensibles que requieren manejo especial
    SENSITIVE_TOPICS = {
        "breakup", "ruptura", "ex", "soledad", "lonely",
        "anxiety", "ansiedad", "depression", "depresión",
        "stress", "estrés", "overwhelmed", "agobiado",
    }
    
    # Señales de crisis que requieren derivación profesional
    CRISIS_KEYWORDS = {
        "suicid", "harm", "hurt myself", "hacerme daño",
        "no quiero vivir", "end it all", "acabar con todo",
    }
    
    @property
    def name(self) -> str:
        return "companion"
    
    @property
    def description(self) -> str:
        return "Compañero emocional para journaling, reflexión y apoyo psicológico"
    
    def _default_system_prompt(self) -> str:
        return get_agent_prompt("companion")
    
    def invoke(self, state: AgentState) -> AgentState:
        """Procesa interacción emocional/journaling.
        
        Añade lógica especial para:
        - Detectar temas sensibles
        - Actualizar mood state
        - Guardar insights en memoria
        - Detectar señales de crisis
        """
        # Verificar crisis antes de procesar
        if self._check_crisis_signals(state):
            return self._handle_crisis(state)
        
        # Procesar normalmente
        state = super().invoke(state)
        
        # Actualizar mood state basado en la conversación
        self._update_mood_state(state)
        
        # Guardar insights importantes
        self._save_insights(state)
        
        return state
    
    def _check_crisis_signals(self, state: AgentState) -> bool:
        """Verifica si hay señales de crisis en el mensaje.
        
        Returns:
            True si se detectan señales de crisis
        """
        if not state.get("messages"):
            return False
        
        last_message = state["messages"][-1]
        if not hasattr(last_message, "content"):
            return False
        
        content = last_message.content.lower()
        
        for keyword in self.CRISIS_KEYWORDS:
            if keyword in content:
                logger.warning(f"Señal de crisis detectada: '{keyword}'")
                return True
        
        return False
    
    def _handle_crisis(self, state: AgentState) -> AgentState:
        """Maneja una situación de crisis detectada.
        
        Responde con compasión y deriva a recursos profesionales.
        """
        crisis_response = AIMessage(
            content="""Eric, lo que acabas de compartir es muy importante y me preocupo por ti.

Lo que sientes es real y válido, pero quiero asegurarme de que tengas el apoyo adecuado.

🆘 **Recursos inmediatos**:
- Teléfono de la Esperanza: **717 003 717** (24h)
- Emergencias: **112**
- Chat de apoyo: telefonodelaesperanza.org

No tienes que enfrentar esto solo. Un profesional puede ayudarte de maneras que yo no puedo.

¿Hay alguien de confianza con quien puedas hablar ahora mismo? ¿Un amigo, familiar?

Estoy aquí para escucharte, pero por favor, considera contactar uno de estos recursos.""",
            name=self.name,
        )
        
        state["messages"].append(crisis_response)
        state["sender"] = self.name
        state["next_agent"] = None  # Finalizar aquí
        
        # Log para auditoría
        logger.critical("Crisis detectada - Respuesta de derivación enviada")
        
        return state
    
    def _update_mood_state(self, state: AgentState) -> None:
        """Actualiza el estado de ánimo basado en la conversación."""
        if not state.get("messages") or len(state["messages"]) < 2:
            return
        
        # Obtener últimos mensajes para análisis
        recent_messages = state["messages"][-3:]
        
        # Análisis simple de sentimiento basado en keywords
        positive_words = {"bien", "genial", "feliz", "happy", "great", "good", "mejor"}
        negative_words = {"mal", "triste", "sad", "bad", "terrible", "peor", "cansado"}
        
        positive_count = 0
        negative_count = 0
        themes = []
        
        for msg in recent_messages:
            if not hasattr(msg, "content"):
                continue
            content = msg.content.lower()
            
            for word in positive_words:
                if word in content:
                    positive_count += 1
            
            for word in negative_words:
                if word in content:
                    negative_count += 1
            
            # Detectar temas
            for topic in self.SENSITIVE_TOPICS:
                if topic in content and topic not in themes:
                    themes.append(topic)
        
        # Calcular sentiment score (-1 a 1)
        total = positive_count + negative_count
        if total > 0:
            sentiment = (positive_count - negative_count) / total
        else:
            sentiment = 0
        
        # Actualizar estado
        state["mood"]["sentiment_score"] = sentiment
        state["mood"]["recent_themes"] = themes[:5]  # Max 5 temas
        
        if sentiment > 0.3:
            state["mood"]["mood"] = "positive"
        elif sentiment < -0.3:
            state["mood"]["mood"] = "negative"
        else:
            state["mood"]["mood"] = "neutral"
        
        logger.debug(
            f"Mood actualizado: {state['mood']['mood']} "
            f"(score={sentiment:.2f}, themes={themes})"
        )
    
    def _save_insights(self, state: AgentState) -> None:
        """Guarda insights importantes en la memoria a largo plazo."""
        # Solo guardar si hay respuesta del agente
        if not state.get("messages"):
            return
        
        # Buscar el último mensaje del Companion
        for msg in reversed(state["messages"]):
            if hasattr(msg, "name") and msg.name == self.name:
                # Verificar si contiene insight valioso
                # (en una implementación real, usaríamos el LLM para esto)
                if len(msg.content) > 200:  # Respuestas largas suelen tener más valor
                    try:
                        from src.services.memory import get_memory_service
                        memory = get_memory_service()
                        
                        # Guardar como insight
                        memory.save_insight(
                            content=msg.content[:500],  # Truncar si muy largo
                            source="companion_conversation",
                            importance=5,
                            user_id=state.get("user_id", "default"),
                        )
                        logger.debug("Insight guardado en memoria")
                    except Exception as e:
                        logger.warning(f"Error guardando insight: {e}")
                break


def create_companion_agent(
    llm: BaseChatModel,
    tools: list[BaseTool] | None = None,
) -> CompanionAgent:
    """Factory function para crear el CompanionAgent.
    
    IMPORTANTE: El LLM debe ser local (Ollama) por privacidad.
    
    Args:
        llm: Modelo de lenguaje LOCAL
        tools: Herramientas adicionales (opcional)
        
    Returns:
        Instancia configurada del CompanionAgent
    """
    from src.tools.notion_mcp import create_notion_journal_tools
    
    default_tools = create_notion_journal_tools()
    all_tools = default_tools + (tools or [])
    
    return CompanionAgent(llm=llm, tools=all_tools)

