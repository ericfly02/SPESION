"""TechLead Agent - Ingeniería Senior y Code Review."""

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


class TechLeadAgent(BaseAgent):
    """Agente TechLead - Senior Engineer y arquitecto de sistemas.
    
    Responsabilidades:
    - Code reviews detallados
    - Debugging de problemas complejos
    - Decisiones de arquitectura
    - Ayuda con algoritmos
    - Ejecución segura de código (sandbox)
    
    Stack del usuario:
    - Backend: Python (Django, FastAPI), MQL5
    - Frontend: React, TypeScript
    - DBs: PostgreSQL, Supabase, SQLite
    - Infra: Docker, AWS básico
    - IA/ML: LangChain, LangGraph, RAG
    """
    
    # Prioridades de feedback en code review
    FEEDBACK_PRIORITIES = {
        "critical": "🔴 Crítico - Bloquea deploy",
        "important": "🟠 Importante - Debería fixearse",
        "suggestion": "🟡 Sugerencia - Nice to have",
        "nitpick": "⚪ Nitpick - Estilo/preferencia",
    }
    
    @property
    def name(self) -> str:
        return "techlead"
    
    @property
    def description(self) -> str:
        return "Senior Engineer para code review, debugging, arquitectura y algoritmos"
    
    def _default_system_prompt(self) -> str:
        return get_agent_prompt("techlead")
    
    def invoke(self, state: AgentState) -> AgentState:
        """Procesa solicitudes de ingeniería."""
        state = super().invoke(state)
        return state
    
    def format_code_review(
        self,
        findings: list[dict],
    ) -> str:
        """Formatea los hallazgos de un code review.
        
        Args:
            findings: Lista de hallazgos con keys:
                - priority: critical/important/suggestion/nitpick
                - line: Número de línea (opcional)
                - description: Descripción del problema
                - suggestion: Código sugerido (opcional)
                
        Returns:
            String formateado del code review
        """
        if not findings:
            return "✅ No se encontraron issues. Código limpio!"
        
        # Agrupar por prioridad
        grouped = {"critical": [], "important": [], "suggestion": [], "nitpick": []}
        for f in findings:
            priority = f.get("priority", "suggestion")
            grouped[priority].append(f)
        
        output_parts = []
        
        for priority, items in grouped.items():
            if not items:
                continue
            
            header = self.FEEDBACK_PRIORITIES[priority]
            output_parts.append(f"\n### {header}\n")
            
            for i, item in enumerate(items, 1):
                line_info = f" (línea {item['line']})" if item.get("line") else ""
                output_parts.append(f"{i}. **{item['description']}**{line_info}")
                
                if item.get("suggestion"):
                    output_parts.append(f"   ```\n   {item['suggestion']}\n   ```")
        
        return "\n".join(output_parts)


def create_techlead_agent(
    llm: BaseChatModel,
    tools: list[BaseTool] | None = None,
) -> TechLeadAgent:
    """Factory function para crear el TechLeadAgent con sus herramientas.
    
    Args:
        llm: Modelo de lenguaje a usar (preferiblemente GPT-4)
        tools: Herramientas adicionales (opcional)
        
    Returns:
        Instancia configurada del TechLeadAgent
    """
    from src.tools.github_mcp import create_github_tools
    from src.tools.code_sandbox import create_sandbox_tools
    
    default_tools = [
        *create_github_tools(),
        *create_sandbox_tools(),
    ]
    
    all_tools = default_tools + (tools or [])
    
    return TechLeadAgent(llm=llm, tools=all_tools)
