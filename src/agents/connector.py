"""Connector Agent - Networking y gestión de contactos."""

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


class ConnectorAgent(BaseAgent):
    """Agente Connector - Experto en networking y relaciones profesionales.
    
    Responsabilidades:
    - Gestión de contactos para WhoHub (CRM personal)
    - Preparación para eventos de networking
    - Ice-breakers personalizados
    - Simulación de negociaciones
    - Follow-ups estratégicos
    
    Principios:
    - Calidad > Cantidad
    - Give first, ask later
    - Autenticidad > Performance
    """
    
    # Niveles de fuerza de conexión
    CONNECTION_STRENGTH = {
        1: "Conocido casual",
        2: "Contacto profesional",
        3: "Relación activa",
        4: "Contacto de confianza",
        5: "Inner circle",
    }
    
    @property
    def name(self) -> str:
        return "connector"
    
    @property
    def description(self) -> str:
        return "Experto en networking, gestión de contactos y preparación para eventos"
    
    def _default_system_prompt(self) -> str:
        return get_agent_prompt("connector")
    
    def invoke(self, state: AgentState) -> AgentState:
        """Procesa solicitudes de networking."""
        state = super().invoke(state)
        return state
    
    def generate_icebreaker(
        self,
        target_name: str,
        target_role: str,
        target_company: str,
        context: str,
        interests: list[str] | None = None,
    ) -> dict:
        """Genera ice-breakers personalizados para un contacto.
        
        Args:
            target_name: Nombre del contacto
            target_role: Rol/cargo
            target_company: Empresa
            context: Contexto del encuentro (evento, conferencia, etc.)
            interests: Intereses conocidos del contacto
            
        Returns:
            Dict con ice-breakers y consejos
        """
        # Esta función sería llamada por el LLM como herramienta
        # o usada internamente para estructurar la respuesta
        
        return {
            "target": {
                "name": target_name,
                "role": target_role,
                "company": target_company,
            },
            "context": context,
            "interests": interests or [],
            "icebreakers": [],  # Se llenan con el LLM
            "avoid": [],        # Cosas a evitar
            "follow_up_suggestion": None,
        }
    
    def format_contact_card(
        self,
        name: str,
        role: str,
        company: str,
        how_met: str,
        last_interaction: str | None = None,
        strength: int = 2,
        notes: str | None = None,
    ) -> str:
        """Formatea una tarjeta de contacto para visualización.
        
        Args:
            name: Nombre del contacto
            role: Rol/cargo
            company: Empresa
            how_met: Cómo se conocieron
            last_interaction: Última interacción
            strength: Fuerza de conexión (1-5)
            notes: Notas adicionales
            
        Returns:
            String formateado
        """
        strength_label = self.CONNECTION_STRENGTH.get(strength, "Desconocido")
        stars = "⭐" * strength
        
        card = f"""
📇 **{name}**
{role} @ {company}

🤝 Cómo nos conocimos: {how_met}
📅 Última interacción: {last_interaction or 'N/A'}
💪 Fuerza: {stars} ({strength_label})
"""
        if notes:
            card += f"\n📝 Notas: {notes}"
        
        return card.strip()


def create_connector_agent(
    llm: BaseChatModel,
    tools: list[BaseTool] | None = None,
) -> ConnectorAgent:
    """Factory function para crear el ConnectorAgent con sus herramientas.
    
    Args:
        llm: Modelo de lenguaje a usar
        tools: Herramientas adicionales (opcional)
        
    Returns:
        Instancia configurada del ConnectorAgent
    """
    from src.tools.notion_mcp import create_notion_crm_tools
    from src.tools.search_tool import create_search_tools
    from src.tools.image_tools import create_image_tools
    
    default_tools = [
        *create_notion_crm_tools(),
        *create_search_tools(),
        *create_image_tools(),
    ]
    
    all_tools = default_tools + (tools or [])
    
    return ConnectorAgent(llm=llm, tools=all_tools)
