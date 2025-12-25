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
    
    default_tools = [
        *create_garmin_tools(),
        *create_strava_tools(),
    ]
    
    all_tools = default_tools + (tools or [])
    
    return CoachAgent(llm=llm, tools=all_tools)
