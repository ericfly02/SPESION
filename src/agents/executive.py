"""Executive Agent - Productividad y gestión de tiempo/energía."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from .base_agent import BaseAgent
from src.core.prompts import get_agent_prompt

if TYPE_CHECKING:
    from src.core.state import AgentState

logger = logging.getLogger(__name__)


class ExecutiveAgent(BaseAgent):
    """Agente Executive - Jefe de gabinete y gestor de productividad.
    
    Responsabilidades:
    - Gestión del calendario
    - Priorización de tareas (Eisenhower Matrix)
    - Balance trabajo/proyectos/descanso
    - Integración con datos de energía del Coach
    
    Principio Core: Energía > Tiempo
    Si el Coach reporta baja energía, reprogramamos tareas pesadas.
    
    Balance semanal ideal:
    - NTTData: 40h
    - Civita: 5-8h
    - Creda: 5-8h
    - WhoHub: 3-5h
    - Deporte: 5-7h
    - Descanso: 1 día completo
    """
    
    # Categorías de la matriz de Eisenhower
    EISENHOWER_MATRIX = {
        "do_first": "🔴 Urgente + Importante → HACER AHORA",
        "schedule": "🟠 Importante + No Urgente → BLOQUEAR TIEMPO",
        "delegate": "🟡 Urgente + No Importante → DELEGAR/AUTOMATIZAR",
        "eliminate": "⚪ Ni Urgente ni Importante → ELIMINAR",
    }
    
    # Asignación de horas semanales ideales
    WEEKLY_ALLOCATION = {
        "nttdata": 40,
        "civita": 7,
        "creda": 7,
        "whohub": 4,
        "sport": 6,
        "rest": 8,  # Un día completo
    }
    
    @property
    def name(self) -> str:
        return "executive"
    
    @property
    def description(self) -> str:
        return "Jefe de gabinete para gestión de calendario, tareas y priorización"
    
    def _default_system_prompt(self) -> str:
        return get_agent_prompt("executive")
    
    def invoke(self, state: AgentState) -> AgentState:
        """Procesa solicitudes de productividad.
        
        Considera el energy_level del usuario para ajustar recomendaciones.
        """
        # Prefetch de datos reales para evitar alucinaciones (agenda/tasks)
        try:
            from langchain_core.messages import HumanMessage
            from src.tools.calendar_mcp import get_calendar_events, get_today_agenda
            from src.tools.notion_mcp import get_tasks

            last_user = None
            for msg in reversed(state.get("messages", [])):
                if isinstance(msg, HumanMessage):
                    last_user = str(msg.content).lower()
                    break

            if last_user:
                agenda_markers = {
                    "agenda", "calendario", "calendar", "reunión", "reunion", "meeting",
                    "lunes", "martes", "miércoles", "miercoles", "jueves", "viernes",
                    "sábado", "sabado", "domingo", "mañana", "manana", "hoy",
                }
                if any(k in last_user for k in agenda_markers):
                    # Siempre traer agenda + próximos eventos (7 días) y tareas
                    agenda_today = get_today_agenda.invoke({})
                    events = get_calendar_events.invoke({"days": 7, "max_results": 25})
                    tasks = get_tasks.invoke({"limit": 20})
                    state["retrieved_context"] = state.get("retrieved_context", []) + [
                        f"[CALENDAR_TODAY_AGENDA]: {agenda_today}",
                        f"[CALENDAR_EVENTS_NEXT_7_DAYS]: {events}",
                        f"[NOTION_TASKS]: {tasks}",
                    ]
        except Exception:
            # Nunca romper Executive por prefetch
            pass

        # Verificar energía antes de sugerir tareas pesadas
        energy_level = state.get("energy", {}).get("level", 0.7)
        
        if energy_level < 0.4:
            logger.info(
                f"Energía baja ({energy_level:.2f}), "
                "ajustando recomendaciones"
            )
            # Añadir contexto de baja energía al estado
            state["retrieved_context"] = state.get("retrieved_context", []) + [
                f"[ALERTA] Nivel de energía bajo: {energy_level:.0%}. "
                "Priorizar tareas de bajo esfuerzo cognitivo."
            ]
        
        state = super().invoke(state)
        return state
    
    def categorize_task(
        self,
        urgent: bool,
        important: bool,
    ) -> str:
        """Categoriza una tarea según la matriz de Eisenhower.
        
        Args:
            urgent: Si la tarea es urgente
            important: Si la tarea es importante
            
        Returns:
            Categoría de la matriz
        """
        if urgent and important:
            return "do_first"
        elif important and not urgent:
            return "schedule"
        elif urgent and not important:
            return "delegate"
        else:
            return "eliminate"
    
    def suggest_time_blocks(
        self,
        energy_level: float,
        tasks: list[dict],
        available_hours: int = 8,
    ) -> list[dict]:
        """Sugiere bloques de tiempo basados en energía y tareas.
        
        Args:
            energy_level: Nivel de energía (0-1)
            tasks: Lista de tareas con 'name', 'duration', 'cognitive_load'
            available_hours: Horas disponibles
            
        Returns:
            Lista de bloques sugeridos
        """
        blocks = []
        
        # Ordenar tareas por carga cognitiva
        sorted_tasks = sorted(
            tasks,
            key=lambda t: t.get("cognitive_load", 0.5),
            reverse=True,
        )
        
        # Si energía alta, empezar con tareas pesadas por la mañana
        if energy_level >= 0.7:
            # Deep work primero
            for task in sorted_tasks:
                if task.get("cognitive_load", 0.5) >= 0.7:
                    blocks.append({
                        "task": task["name"],
                        "suggested_time": "mañana (9-12h)",
                        "duration": task.get("duration", 2),
                        "reason": "Energía alta → deep work primero",
                    })
        else:
            # Tareas ligeras primero, pesadas si hay energía después
            light_tasks = [t for t in sorted_tasks if t.get("cognitive_load", 0.5) < 0.5]
            heavy_tasks = [t for t in sorted_tasks if t.get("cognitive_load", 0.5) >= 0.5]
            
            for task in light_tasks[:2]:
                blocks.append({
                    "task": task["name"],
                    "suggested_time": "mañana",
                    "duration": task.get("duration", 1),
                    "reason": "Energía baja → empezar suave",
                })
            
            for task in heavy_tasks:
                blocks.append({
                    "task": task["name"],
                    "suggested_time": "tarde (si mejora energía)",
                    "duration": task.get("duration", 2),
                    "reason": "Considerar reprogramar si sigue baja",
                })
        
        return blocks
    
    def format_daily_plan(
        self,
        energy_level: float,
        blocks: list[dict],
        alerts: list[str] | None = None,
    ) -> str:
        """Formatea el plan diario para mostrar al usuario.
        
        Args:
            energy_level: Nivel de energía
            blocks: Bloques de tiempo
            alerts: Alertas importantes
            
        Returns:
            String formateado del plan
        """
        energy_emoji = "🔋" if energy_level >= 0.7 else "🪫" if energy_level >= 0.4 else "❌"
        energy_status = (
            "Óptimo para deep work"
            if energy_level >= 0.7
            else "Moderado"
            if energy_level >= 0.4
            else "Bajo - priorizar descanso"
        )
        
        output = f"""📅 **Plan para Hoy**

{energy_emoji} Energía: {energy_level:.0%} - {energy_status}

🎯 **Bloques sugeridos**:
"""
        for i, block in enumerate(blocks, 1):
            output += f"\n{i}. [{block['suggested_time']}] **{block['task']}** ({block['duration']}h)"
            if block.get("reason"):
                output += f"\n   _{block['reason']}_"
        
        if alerts:
            output += "\n\n⚠️ **Alertas**:\n"
            for alert in alerts:
                output += f"- {alert}\n"
        
        return output


def create_executive_agent(
    llm: BaseChatModel,
    tools: list[BaseTool] | None = None,
) -> ExecutiveAgent:
    """Factory function para crear el ExecutiveAgent con sus herramientas.
    
    Args:
        llm: Modelo de lenguaje a usar
        tools: Herramientas adicionales (opcional)
        
    Returns:
        Instancia configurada del ExecutiveAgent
    """
    from src.tools.calendar_mcp import create_calendar_tools
    from src.tools.notion_mcp import create_notion_tasks_tools
    from src.tools.notion_mcp import (
        setup_books_database,
        setup_trainings_database,
        add_book,
        log_training_session,
        get_training_for_date,
    )
    
    default_tools = [
        *create_calendar_tools(),
        *create_notion_tasks_tools(),
        # Notion extra DBs / operations (sin re-ejecutar setup completo)
        setup_books_database,
        setup_trainings_database,
        add_book,
        log_training_session,
        get_training_for_date,
    ]
    
    all_tools = default_tools + (tools or [])
    
    return ExecutiveAgent(llm=llm, tools=all_tools)
