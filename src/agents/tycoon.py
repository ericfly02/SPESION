"""Tycoon Agent - Personal finance and investments."""

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
    """Tycoon Agent - Personal finance and investment expert.
    
    Responsibilities:
    - Portfolio tracking (IBKR + Crypto)
    - Allocation analysis (50% Core, 35% Thematic, 15% Crypto)
    - Rebalancing suggestions
    - Monthly DCA reminders
    - Investment opportunity analysis
    
    User's Strategy:
    - Long-term (10+ year horizon)
    - Monthly DCA €700-900
    - No market timing
    """
    
    # User's target allocation
    TARGET_ALLOCATION = {
        "core": 0.50,      # Global ETFs (VWCE, IWDA)
        "thematic": 0.35,  # Tech, AI, semiconductors
        "crypto": 0.15,    # BTC, ETH primarily
    }
    
    # Deviation tolerance before alerting
    REBALANCE_THRESHOLD = 0.05  # 5%
    
    @property
    def name(self) -> str:
        return "tycoon"
    
    @property
    def description(self) -> str:
        return "Portfolio management, investments, and personal finance expert"
    
    def _default_system_prompt(self) -> str:
        return get_agent_prompt("tycoon")
    
    def invoke(self, state: AgentState) -> AgentState:
        """Process financial requests."""
        state = super().invoke(state)
        return state
    
    def check_allocation_deviation(
        self,
        current_allocation: dict[str, float],
    ) -> dict[str, any]:
        """Check portfolio allocation deviations.
        
        Args:
            current_allocation: Dict with current allocation (core, thematic, crypto)
            
        Returns:
            Dict with deviation analysis and suggestions
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
                        f"Reduce {category} by {abs(deviation)*100:.1f}%"
                    )
                else:
                    suggestions.append(
                        f"Increase {category} by {abs(deviation)*100:.1f}%"
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
        """Calculate how to distribute monthly contribution.
        
        Prioritizes underweight categories to maintain balance.
        
        Args:
            monthly_amount: Amount to invest this month
            current_allocation: Current allocation
            
        Returns:
            Dict with suggested amount per category
        """
        # Calculate deviations
        deviations = {}
        for category, target in self.TARGET_ALLOCATION.items():
            current = current_allocation.get(category, target)
            deviations[category] = target - current  # Positive if underweight
        
        # Normalize so they sum to 1 (only underweight categories)
        positive_devs = {k: max(0, v) for k, v in deviations.items()}
        total_positive = sum(positive_devs.values())
        
        if total_positive == 0:
            # No underweight, use normal targets
            return {
                category: monthly_amount * target
                for category, target in self.TARGET_ALLOCATION.items()
            }
        
        # Allocate proportionally to underweight
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
    """Factory function to create TycoonAgent with its tools.
    
    Args:
        llm: Language model to use
        tools: Additional tools (optional)
        
    Returns:
        Configured TycoonAgent instance
    """
    from src.tools.finance_tool import create_finance_tools
    
    default_tools = create_finance_tools()
    all_tools = default_tools + (tools or [])
    
    return TycoonAgent(llm=llm, tools=all_tools)
