"""Coach Agent - Salud, Deporte y Recuperación."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from .base_agent import BaseAgent
from src.core.prompts import get_agent_prompt

if TYPE_CHECKING:
    from src.core.state import AgentState

logger = logging.getLogger(__name__)


class CoachAgent(BaseAgent):
    """Agente Coach - Experto en fitness, recuperación y rendimiento.
    
    Responsabilidades:
    - Analizar datos de Garmin (HRV, sueño, Body Battery)
    - Integrar datos de Strava (actividades, entrenamientos)
    - Sugerir planes de entrenamiento adaptativos
    - Monitorear estado de recuperación
    - Alertar sobre riesgo de sobreentrenamiento
    
    Nota: Este agente SIEMPRE usa LLM local por privacidad de datos de salud.
    """
    
    @property
    def name(self) -> str:
        return "coach"
    
    @property
    def description(self) -> str:
        return "Experto en fitness, análisis de Garmin/Strava y planes de entrenamiento"
    
    def _default_system_prompt(self) -> str:
        return get_agent_prompt("coach")
    
    def invoke(self, state: AgentState) -> AgentState:
        """Procesa solicitudes relacionadas con salud y deporte.
        
        Actualiza el energy_level en el estado basado en los datos disponibles.
        """
        # Prefetch de datos reales para evitar alucinaciones (Garmin/Strava)
        try:
            from langchain_core.messages import HumanMessage
            from src.tools.garmin_mcp import get_garmin_stats, get_garmin_activities
            from src.tools.strava_mcp import get_strava_activities

            last_user = None
            for msg in reversed(state.get("messages", [])):
                if isinstance(msg, HumanMessage):
                    last_user = str(msg.content).lower()
                    break

            if last_user:
                stats_markers = {"hrv", "sueño", "sueno", "body battery", "recuperación", "recuperacion", "resting", "rhr"}
                activity_markers = {"qué entreno", "que entreno", "entreno he", "actividad", "hecho hoy", "hice hoy", "hoy entrené", "hoy entrene"}

                if any(k in last_user for k in stats_markers):
                    gstats = get_garmin_stats.invoke({"date": "hoy"})
                    state["retrieved_context"] = state.get("retrieved_context", []) + [
                        f"[GARMIN_STATS_TODAY]: {gstats}",
                    ]

                if any(k in last_user for k in activity_markers):
                    gacts = get_garmin_activities.invoke({"days": 1})
                    # Fallback a Strava si Garmin no trae nada o devuelve error
                    use_strava = (
                        isinstance(gacts, list)
                        and (len(gacts) == 0 or (len(gacts) == 1 and isinstance(gacts[0], dict) and gacts[0].get("error")))
                    )
                    sacts = get_strava_activities.invoke({"days": 1, "per_page": 10}) if use_strava else None
                    ctx = [f"[GARMIN_ACTIVITIES_LAST_1_DAY]: {gacts}"]
                    if sacts is not None:
                        ctx.append(f"[STRAVA_ACTIVITIES_LAST_1_DAY]: {sacts}")
                    state["retrieved_context"] = state.get("retrieved_context", []) + ctx
        except Exception:
            pass

        state = super().invoke(state)
        
        # Intentar actualizar energy_level si tenemos datos
        self._update_energy_state(state)
        
        return state
    
    def _update_energy_state(self, state: AgentState) -> None:
        """Actualiza el estado de energía basado en métricas.
        
        Esta función analiza las herramientas ejecutadas y sus resultados
        para actualizar el energy state del usuario.
        """
        if not state.get("tool_results"):
            return
        
        for result in state["tool_results"]:
            if result.get("tool") == "get_garmin_stats":
                data = result.get("result", {})
                
                # Actualizar HRV
                if "hrv" in data:
                    state["energy"]["hrv_score"] = data["hrv"]
                
                # Actualizar calidad de sueño
                if "sleep_score" in data:
                    state["energy"]["sleep_quality"] = data["sleep_score"] / 100
                
                # Calcular nivel de energía compuesto
                if "body_battery" in data:
                    state["energy"]["level"] = data["body_battery"] / 100
                
                # Determinar estado de recuperación
                level = state["energy"]["level"]
                if level >= 0.8:
                    state["energy"]["recovery_status"] = "excellent"
                elif level >= 0.6:
                    state["energy"]["recovery_status"] = "good"
                elif level >= 0.4:
                    state["energy"]["recovery_status"] = "fair"
                else:
                    state["energy"]["recovery_status"] = "poor"
                
                from datetime import datetime
                state["energy"]["last_updated"] = datetime.now().isoformat()
                
                logger.info(
                    f"Energy state actualizado: level={level:.2f}, "
                    f"recovery={state['energy']['recovery_status']}"
                )


def create_coach_agent(
    llm: BaseChatModel,
    tools: list[BaseTool] | None = None,
) -> CoachAgent:
    """Factory function para crear el CoachAgent con sus herramientas.
    
    Args:
        llm: Modelo de lenguaje a usar (preferiblemente local)
        tools: Herramientas adicionales (opcional)
        
    Returns:
        Instancia configurada del CoachAgent
    """
    from src.tools.garmin_mcp import create_garmin_tools
    from src.tools.strava_mcp import create_strava_tools
    from src.tools.memory_tools import create_memory_tools
    from src.tools.document_tools import create_document_tools
    from src.tools.notion_mcp import (
        setup_trainings_database,
        log_training_session,
        get_training_for_date,
    )
    
    default_tools = [
        *create_garmin_tools(),
        *create_strava_tools(),
        *create_memory_tools(),
        *create_document_tools(),
        # Plan/registro de entrenos en Notion
        setup_trainings_database,
        log_training_session,
        get_training_for_date,
    ]
    
    all_tools = default_tools + (tools or [])
    
    return CoachAgent(llm=llm, tools=all_tools)
