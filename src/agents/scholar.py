"""Scholar Agent - Research and knowledge synthesis."""

from __future__ import annotations

from typing import TYPE_CHECKING

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from .base_agent import BaseAgent
from src.core.prompts import get_agent_prompt

if TYPE_CHECKING:
    from src.core.state import AgentState


class ScholarAgent(BaseAgent):
    """Scholar Agent - Research specialist in AI, Quant Finance, and Neuroscience.
    
    Responsibilities:
    - Search and summarize ArXiv papers
    - Monitor relevant tech news and trends
    - Create executive summaries
    - Maintain knowledge base updated
    """
    
    @property
    def name(self) -> str:
        return "scholar"
    
    @property
    def description(self) -> str:
        return "Research specialist for ArXiv papers, tech news, and AI/Quant/Neuro trends"
    
    def _default_system_prompt(self) -> str:
        return get_agent_prompt("scholar")
    
    def invoke(self, state: AgentState) -> AgentState:
        """Process research requests.
        
        Specializes invoke to add search and summary logic.
        """
        # Call base invoke
        state = super().invoke(state)
        
        # If there are tool calls, the graph will handle execution
        # Post-processing logic can be added here if needed
        
        return state


def create_scholar_agent(
    llm: BaseChatModel,
    tools: list[BaseTool] | None = None,
) -> ScholarAgent:
    """Factory function to create ScholarAgent with its tools.
    
    Args:
        llm: Language model to use
        tools: Additional tools (optional)
        
    Returns:
        Configured ScholarAgent instance
    """
    from src.tools.arxiv_tool import create_arxiv_tools
    from src.tools.search_tool import create_search_tools
    
    # Combine default tools with provided ones
    default_tools = [
        *create_arxiv_tools(),
        *create_search_tools(),
    ]
    
    all_tools = default_tools + (tools or [])
    
    return ScholarAgent(llm=llm, tools=all_tools)
