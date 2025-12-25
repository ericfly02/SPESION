"""Coach Agent - Health, Fitness, and Recovery."""

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


class CoachAgent(BaseAgent):
    """Coach Agent - Fitness, recovery, and performance expert.
    
    Responsibilities:
    - Analyze Garmin data (HRV, sleep, Body Battery)
    - Integrate Strava data (activities, workouts)
    - Suggest adaptive training plans
    - Monitor recovery status
    - Alert about overtraining risk
    
    Note: This agent ALWAYS uses local LLM for health data privacy.
    """
    
    @property
    def name(self) -> str:
        return "coach"
    
    @property
    def description(self) -> str:
        return "Fitness expert for Garmin/Strava analysis and training plans"
    
    def _default_system_prompt(self) -> str:
        return get_agent_prompt("coach")
    
    def invoke(self, state: AgentState) -> AgentState:
        """Process health and sports related requests.
        
        Updates energy_level in state based on available data.
        """
        state = super().invoke(state)
        
        # Try to update energy_level if we have data
        self._update_energy_state(state)
        
        return state
    
    def _update_energy_state(self, state: AgentState) -> None:
        """Update energy state based on metrics.
        
        This function analyzes executed tools and their results
        to update the user's energy state.
        """
        if not state.get("tool_results"):
            return
        
        for result in state["tool_results"]:
            if result.get("tool") == "get_garmin_stats":
                data = result.get("result", {})
                
                # Update HRV
                if "hrv" in data:
                    state["energy"]["hrv_score"] = data["hrv"]
                
                # Update sleep quality
                if "sleep_score" in data:
                    state["energy"]["sleep_quality"] = data["sleep_score"] / 100
                
                # Calculate composite energy level
                if "body_battery" in data:
                    state["energy"]["level"] = data["body_battery"] / 100
                
                # Determine recovery status
                level = state["energy"]["level"]
                if level >= 0.8:
                    state["energy"]["recovery_status"] = "excellent"
                elif level >= 0.6:
                    state["energy"]["recovery_status"] = "good"
                elif level >= 0.4:
                    state["energy"]["recovery_status"] = "fair"
                else:
                    state["energy"]["recovery_status"] = "poor"
                
                from datetime import datetime
                state["energy"]["last_updated"] = datetime.now().isoformat()
                
                logger.info(
                    f"Energy state updated: level={level:.2f}, "
                    f"recovery={state['energy']['recovery_status']}"
                )


def create_coach_agent(
    llm: BaseChatModel,
    tools: list[BaseTool] | None = None,
) -> CoachAgent:
    """Factory function to create CoachAgent with its tools.
    
    Args:
        llm: Language model to use (preferably local for privacy)
        tools: Additional tools (optional)
        
    Returns:
        Configured CoachAgent instance
    """
    from src.tools.garmin_mcp import create_garmin_tools
    from src.tools.strava_mcp import create_strava_tools
    
    default_tools = [
        *create_garmin_tools(),
        *create_strava_tools(),
    ]
    
    all_tools = default_tools + (tools or [])
    
    return CoachAgent(llm=llm, tools=all_tools)
