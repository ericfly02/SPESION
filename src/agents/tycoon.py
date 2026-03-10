"""Tycoon Agent - Finanzas personales e inversiones."""

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


class TycoonAgent(BaseAgent):
    """Agente Tycoon - Experto en finanzas personales e inversiones.
    
    Responsabilidades:
    - Tracking del portfolio (IBKR + Crypto)
    - Análisis de asignación (50% Core, 35% Temático, 15% Crypto)
    - Sugerencias de rebalanceo
    - Recordatorios de DCA mensual
    - Análisis de oportunidades de inversión
    
    Estrategia del usuario:
    - Long-term (horizonte 10+ años)
    - DCA mensual 700-900€
    - No timing del mercado
    """
    
    # Targets de asignación del usuario
    TARGET_ALLOCATION = {
        "core": 0.50,      # ETFs globales (VWCE, IWDA)
        "thematic": 0.35,  # Tech, IA, semiconductores
        "crypto": 0.15,    # BTC, ETH principalmente
    }
    
    # Tolerancia de desviación antes de alertar
    REBALANCE_THRESHOLD = 0.05  # 5%
    
    @property
    def name(self) -> str:
        return "tycoon"
    
    @property
    def description(self) -> str:
        return "Experto en portfolio management, inversiones y finanzas personales"
    
    def _default_system_prompt(self) -> str:
        return get_agent_prompt("tycoon")
    
    def invoke(self, state: AgentState) -> AgentState:
        """Procesa solicitudes financieras.
        
        Prefetches portfolio data for faster autonomous responses.
        """
        # Prefetch portfolio data to avoid hallucination
        try:
            from langchain_core.messages import HumanMessage
            from src.tools.notion_mcp import get_portfolio_holdings

            last_user = None
            for msg in reversed(state.get("messages", [])):
                if isinstance(msg, HumanMessage):
                    last_user = str(msg.content).lower()
                    break

            if last_user:
                finance_markers = {
                    "portfolio", "portafolio", "inversión", "inversion", "inversiones",
                    "rebalanceo", "rebalance", "holdings", "posiciones", "asignación",
                    "allocation", "cómo va", "como va", "resumen", "cuánto tengo",
                    "cuanto tengo", "rendimiento", "performance", "estado",
                }
                if any(k in last_user for k in finance_markers):
                    holdings = get_portfolio_holdings.invoke({})
                    state["retrieved_context"] = state.get("retrieved_context", []) + [
                        f"[PORTFOLIO_HOLDINGS]: {holdings}",
                    ]
        except Exception:
            pass

        state = super().invoke(state)
        return state
    
    def check_allocation_deviation(
        self,
        current_allocation: dict[str, float],
    ) -> dict[str, any]:
        """Verifica desviaciones en la asignación del portfolio.
        
        Args:
            current_allocation: Dict con asignación actual (core, thematic, crypto)
            
        Returns:
            Dict con análisis de desviaciones y sugerencias
        """
        deviations = {}
        suggestions = []
        needs_rebalance = False
        
        for category, target in self.TARGET_ALLOCATION.items():
            current = current_allocation.get(category, 0)
            deviation = current - target
            deviations[category] = {
                "current": current,
                "target": target,
                "deviation": deviation,
                "deviation_pct": abs(deviation) * 100,
            }
            
            if abs(deviation) > self.REBALANCE_THRESHOLD:
                needs_rebalance = True
                if deviation > 0:
                    suggestions.append(
                        f"Reducir {category} en {abs(deviation)*100:.1f}%"
                    )
                else:
                    suggestions.append(
                        f"Aumentar {category} en {abs(deviation)*100:.1f}%"
                    )
        
        return {
            "deviations": deviations,
            "needs_rebalance": needs_rebalance,
            "suggestions": suggestions,
        }
    
    def calculate_dca_allocation(
        self,
        monthly_amount: float,
        current_allocation: dict[str, float],
    ) -> dict[str, float]:
        """Calcula cómo distribuir la aportación mensual.
        
        Prioriza las categorías infraponderadas para mantener el balance.
        
        Args:
            monthly_amount: Cantidad a invertir este mes
            current_allocation: Asignación actual
            
        Returns:
            Dict con cantidad sugerida por categoría
        """
        # Calcular desviaciones
        deviations = {}
        for category, target in self.TARGET_ALLOCATION.items():
            current = current_allocation.get(category, target)
            deviations[category] = target - current  # Positivo si infraponderado
        
        # Normalizar para que sume 1 (solo categorías infraponderadas)
        positive_devs = {k: max(0, v) for k, v in deviations.items()}
        total_positive = sum(positive_devs.values())
        
        if total_positive == 0:
            # No hay infraponderación, usar targets normales
            return {
                category: monthly_amount * target
                for category, target in self.TARGET_ALLOCATION.items()
            }
        
        # Asignar proporcionalmente a la infraponderación
        allocation = {}
        for category, dev in positive_devs.items():
            if dev > 0:
                allocation[category] = monthly_amount * (dev / total_positive)
            else:
                allocation[category] = 0
        
        return allocation


def create_tycoon_agent(
    llm: BaseChatModel,
    tools: list[BaseTool] | None = None,
) -> TycoonAgent:
    """Factory function para crear el TycoonAgent con sus herramientas.
    
    Args:
        llm: Modelo de lenguaje a usar
        tools: Herramientas adicionales (opcional)
        
    Returns:
        Instancia configurada del TycoonAgent
    """
    from src.tools.finance_tools import create_finance_tools
    from src.tools.notion_mcp import create_notion_finance_tools, check_notion_connection
    from src.tools.investments_sync import create_investment_sync_tools
    from src.tools.autonomous_tools import create_autonomous_tools
    from src.tools.browser_tool import create_browser_tools
    from src.tools.search_tool import create_search_tools
    
    default_tools = (
        create_finance_tools()
        + create_notion_finance_tools()
        + create_investment_sync_tools()
        + create_autonomous_tools()
        + create_browser_tools()
        + create_search_tools()
        + [check_notion_connection]
    )
    all_tools = default_tools + (tools or [])
    
    return TycoonAgent(llm=llm, tools=all_tools)
