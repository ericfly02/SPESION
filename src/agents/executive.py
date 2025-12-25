"""Executive Agent - Productivity and time/energy management."""

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
    """Executive Agent - Chief of Staff and productivity manager.
    
    Responsibilities:
    - Calendar management and protection
    - Task prioritization (Eisenhower Matrix)
    - Work/projects/rest balance
    - Integration with Coach energy data
    
    Core Principle: Energy > Time
    When Coach reports low energy, reschedule demanding tasks.
    
    Ideal weekly allocation:
    - NTTData: 40h
    - Civita: 5-8h
    - Creda: 5-8h
    - WhoHub: 3-5h
    - Exercise: 5-7h
    - Rest: 1 full day
    """
    
    # Eisenhower Matrix categories
    EISENHOWER_MATRIX = {
        "do_first": "🔴 Urgent + Important → DO NOW",
        "schedule": "🟠 Important + Not Urgent → BLOCK TIME",
        "delegate": "🟡 Urgent + Not Important → DELEGATE/AUTOMATE",
        "eliminate": "⚪ Neither Urgent nor Important → ELIMINATE",
    }
    
    # Ideal weekly hour allocation
    WEEKLY_ALLOCATION = {
        "nttdata": 40,
        "civita": 7,
        "creda": 7,
        "whohub": 4,
        "sport": 6,
        "rest": 8,  # One full day
    }
    
    @property
    def name(self) -> str:
        return "executive"
    
    @property
    def description(self) -> str:
        return "Chief of Staff for calendar, tasks, and prioritization management"
    
    def _default_system_prompt(self) -> str:
        return get_agent_prompt("executive")
    
    def invoke(self, state: AgentState) -> AgentState:
        """Process productivity requests.
        
        Considers user's energy_level to adjust recommendations.
        """
        # Check energy before suggesting heavy tasks
        energy_level = state.get("energy", {}).get("level", 0.7)
        
        if energy_level < 0.4:
            logger.info(
                f"Low energy ({energy_level:.2f}), "
                "adjusting recommendations"
            )
            # Add low energy context to state
            state["retrieved_context"] = state.get("retrieved_context", []) + [
                f"[ALERT] Low energy level: {energy_level:.0%}. "
                "Prioritize low cognitive effort tasks."
            ]
        
        state = super().invoke(state)
        return state
    
    def categorize_task(
        self,
        urgent: bool,
        important: bool,
    ) -> str:
        """Categorize a task according to the Eisenhower Matrix.
        
        Args:
            urgent: Whether the task is urgent
            important: Whether the task is important
            
        Returns:
            Matrix category key
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
        """Suggest time blocks based on energy and tasks.
        
        Args:
            energy_level: Energy level (0-1)
            tasks: List of tasks with 'name', 'duration', 'cognitive_load'
            available_hours: Available hours
            
        Returns:
            List of suggested blocks
        """
        blocks = []
        
        # Sort tasks by cognitive load
        sorted_tasks = sorted(
            tasks,
            key=lambda t: t.get("cognitive_load", 0.5),
            reverse=True,
        )
        
        # If high energy, start with heavy tasks in the morning
        if energy_level >= 0.7:
            # Deep work first
            for task in sorted_tasks:
                if task.get("cognitive_load", 0.5) >= 0.7:
                    blocks.append({
                        "task": task["name"],
                        "suggested_time": "morning (9-12h)",
                        "duration": task.get("duration", 2),
                        "reason": "High energy → deep work first",
                    })
        else:
            # Light tasks first, heavy if energy improves
            light_tasks = [t for t in sorted_tasks if t.get("cognitive_load", 0.5) < 0.5]
            heavy_tasks = [t for t in sorted_tasks if t.get("cognitive_load", 0.5) >= 0.5]
            
            for task in light_tasks[:2]:
                blocks.append({
                    "task": task["name"],
                    "suggested_time": "morning",
                    "duration": task.get("duration", 1),
                    "reason": "Low energy → start easy",
                })
            
            for task in heavy_tasks:
                blocks.append({
                    "task": task["name"],
                    "suggested_time": "afternoon (if energy improves)",
                    "duration": task.get("duration", 2),
                    "reason": "Consider rescheduling if still low",
                })
        
        return blocks
    
    def format_daily_plan(
        self,
        energy_level: float,
        blocks: list[dict],
        alerts: list[str] | None = None,
    ) -> str:
        """Format the daily plan for user display.
        
        Args:
            energy_level: Energy level
            blocks: Time blocks
            alerts: Important alerts
            
        Returns:
            Formatted plan string
        """
        energy_emoji = "🔋" if energy_level >= 0.7 else "🪫" if energy_level >= 0.4 else "❌"
        energy_status = (
            "Optimal for deep work"
            if energy_level >= 0.7
            else "Moderate"
            if energy_level >= 0.4
            else "Low - prioritize rest"
        )
        
        output = f"""📅 **Today's Plan**

{energy_emoji} Energy: {energy_level:.0%} - {energy_status}

🎯 **Suggested Blocks**:
"""
        for i, block in enumerate(blocks, 1):
            output += f"\n{i}. [{block['suggested_time']}] **{block['task']}** ({block['duration']}h)"
            if block.get("reason"):
                output += f"\n   _{block['reason']}_"
        
        if alerts:
            output += "\n\n⚠️ **Alerts**:\n"
            for alert in alerts:
                output += f"- {alert}\n"
        
        return output


def create_executive_agent(
    llm: BaseChatModel,
    tools: list[BaseTool] | None = None,
) -> ExecutiveAgent:
    """Factory function to create the ExecutiveAgent with its tools.
    
    Args:
        llm: Language model to use
        tools: Additional tools (optional)
        
    Returns:
        Configured ExecutiveAgent instance
    """
    from src.tools.calendar_mcp import create_calendar_tools
    from src.tools.notion_mcp import create_notion_tasks_tools
    
    default_tools = [
        *create_calendar_tools(),
        *create_notion_tasks_tools(),
    ]
    
    all_tools = default_tools + (tools or [])
    
    return ExecutiveAgent(llm=llm, tools=all_tools)
