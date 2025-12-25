"""Scholar Agent - Investigador y síntesis de conocimiento."""

from __future__ import annotations

from typing import TYPE_CHECKING

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from .base_agent import BaseAgent
from src.core.prompts import get_agent_prompt

if TYPE_CHECKING:
    from src.core.state import AgentState


class ScholarAgent(BaseAgent):
    """Agente Scholar - Investigador especializado en IA, Quant y Neurociencia.
    
    Responsabilidades:
    - Buscar y resumir papers de ArXiv
    - Monitorear noticias relevantes
    - Crear resúmenes ejecutivos
    - Mantener actualizada la base de conocimiento
    """
    
    @property
    def name(self) -> str:
        return "scholar"
    
    @property
    def description(self) -> str:
        return "Investigador de papers ArXiv, noticias tech y tendencias IA/Quant/Neuro"
    
    def _default_system_prompt(self) -> str:
        return get_agent_prompt("scholar")
    
    def invoke(self, state: AgentState) -> AgentState:
        """Procesa la solicitud de investigación.
        
        Especializa el invoke para añadir lógica de búsqueda y resumen.
        """
        # Llamar al invoke base
        state = super().invoke(state)
        
        # Si hay tool calls, el grafo manejará la ejecución
        # Aquí podemos añadir lógica post-procesamiento si necesario
        
        return state


def create_scholar_agent(
    llm: BaseChatModel,
    tools: list[BaseTool] | None = None,
) -> ScholarAgent:
    """Factory function para crear el ScholarAgent con sus herramientas.
    
    Args:
        llm: Modelo de lenguaje a usar
        tools: Herramientas adicionales (opcional)
        
    Returns:
        Instancia configurada del ScholarAgent
    """
    from src.tools.arxiv_tool import create_arxiv_tools
    from src.tools.search_tool import create_search_tools
    
    # Combinar herramientas default con las proporcionadas
    default_tools = [
        *create_arxiv_tools(),
        *create_search_tools(),
    ]
    
    all_tools = default_tools + (tools or [])
    
    return ScholarAgent(llm=llm, tools=all_tools)
