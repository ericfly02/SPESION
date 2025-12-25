"""TechLead Agent - Senior Engineering and Code Review."""

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
    """TechLead Agent - Senior Engineer and system architect.
    
    Responsibilities:
    - Detailed code reviews
    - Complex debugging
    - Architecture decisions
    - Algorithm help
    - Secure code execution (sandbox)
    
    User's Stack:
    - Backend: Python (Django, FastAPI), MQL5
    - Frontend: React, TypeScript
    - DBs: PostgreSQL, Supabase, SQLite
    - Infra: Docker, basic AWS
    - AI/ML: LangChain, LangGraph, RAG
    """
    
    # Code review feedback priorities
    FEEDBACK_PRIORITIES = {
        "critical": "🔴 Critical - Blocks deploy",
        "important": "🟠 Important - Should be fixed",
        "suggestion": "🟡 Suggestion - Nice to have",
        "nitpick": "⚪ Nitpick - Style/preference",
    }
    
    @property
    def name(self) -> str:
        return "techlead"
    
    @property
    def description(self) -> str:
        return "Senior Engineer for code review, debugging, architecture, and algorithms"
    
    def _default_system_prompt(self) -> str:
        return get_agent_prompt("techlead")
    
    def invoke(self, state: AgentState) -> AgentState:
        """Process engineering requests."""
        state = super().invoke(state)
        return state
    
    def format_code_review(
        self,
        findings: list[dict],
    ) -> str:
        """Format code review findings.
        
        Args:
            findings: List of findings with keys:
                - priority: critical/important/suggestion/nitpick
                - line: Line number (optional)
                - description: Problem description
                - suggestion: Suggested code (optional)
                
        Returns:
            Formatted code review string
        """
        if not findings:
            return "✅ No issues found. Clean code!"
        
        # Group by priority
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
                line_info = f" (line {item['line']})" if item.get("line") else ""
                output_parts.append(f"{i}. **{item['description']}**{line_info}")
                
                if item.get("suggestion"):
                    output_parts.append(f"   ```\n   {item['suggestion']}\n   ```")
        
        return "\n".join(output_parts)


def create_techlead_agent(
    llm: BaseChatModel,
    tools: list[BaseTool] | None = None,
) -> TechLeadAgent:
    """Factory function to create TechLeadAgent with its tools.
    
    Args:
        llm: Language model to use (preferably GPT-4)
        tools: Additional tools (optional)
        
    Returns:
        Configured TechLeadAgent instance
    """
    from src.tools.github_mcp import create_github_tools
    from src.tools.code_sandbox import create_sandbox_tools
    
    default_tools = [
        *create_github_tools(),
        *create_sandbox_tools(),
    ]
    
    all_tools = default_tools + (tools or [])
    
    return TechLeadAgent(llm=llm, tools=all_tools)
