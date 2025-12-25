"""Connector Agent - Networking and contact management."""

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
    """Connector Agent - Networking and professional relationships expert.
    
    Responsibilities:
    - Contact management for WhoHub (personal CRM)
    - Event preparation for networking
    - Personalized ice-breakers
    - Negotiation simulation
    - Strategic follow-ups
    
    Principles:
    - Quality > Quantity
    - Give first, ask later
    - Authenticity > Performance
    """
    
    # Connection strength levels
    CONNECTION_STRENGTH = {
        1: "Casual acquaintance",
        2: "Professional contact",
        3: "Active relationship",
        4: "Trusted contact",
        5: "Inner circle",
    }
    
    @property
    def name(self) -> str:
        return "connector"
    
    @property
    def description(self) -> str:
        return "Networking expert for contact management and event preparation"
    
    def _default_system_prompt(self) -> str:
        return get_agent_prompt("connector")
    
    def invoke(self, state: AgentState) -> AgentState:
        """Process networking requests."""
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
        """Generate personalized ice-breakers for a contact.
        
        Args:
            target_name: Contact name
            target_role: Role/title
            target_company: Company
            context: Meeting context (event, conference, etc.)
            interests: Known contact interests
            
        Returns:
            Dict with ice-breakers and tips
        """
        # This function would be called by LLM as a tool
        # or used internally to structure the response
        
        return {
            "target": {
                "name": target_name,
                "role": target_role,
                "company": target_company,
            },
            "context": context,
            "interests": interests or [],
            "icebreakers": [],  # Filled by LLM
            "avoid": [],        # Things to avoid
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
        """Format a contact card for display.
        
        Args:
            name: Contact name
            role: Role/title
            company: Company
            how_met: How you met
            last_interaction: Last interaction
            strength: Connection strength (1-5)
            notes: Additional notes
            
        Returns:
            Formatted string
        """
        strength_label = self.CONNECTION_STRENGTH.get(strength, "Unknown")
        stars = "⭐" * strength
        
        card = f"""
📇 **{name}**
{role} @ {company}

🤝 How we met: {how_met}
📅 Last interaction: {last_interaction or 'N/A'}
💪 Strength: {stars} ({strength_label})
"""
        if notes:
            card += f"\n📝 Notes: {notes}"
        
        return card.strip()


def create_connector_agent(
    llm: BaseChatModel,
    tools: list[BaseTool] | None = None,
) -> ConnectorAgent:
    """Factory function to create ConnectorAgent with its tools.
    
    Args:
        llm: Language model to use
        tools: Additional tools (optional)
        
    Returns:
        Configured ConnectorAgent instance
    """
    from src.tools.notion_mcp import create_notion_crm_tools
    from src.tools.search_tool import create_search_tools
    
    default_tools = [
        *create_notion_crm_tools(),
        *create_search_tools(),
    ]
    
    all_tools = default_tools + (tools or [])
    
    return ConnectorAgent(llm=llm, tools=all_tools)
