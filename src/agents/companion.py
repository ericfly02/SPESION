"""Companion Agent - Emotional wellbeing and journaling."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.tools import BaseTool

from .base_agent import BaseAgent
from src.core.prompts import get_agent_prompt

if TYPE_CHECKING:
    from src.core.state import AgentState

logger = logging.getLogger(__name__)


class CompanionAgent(BaseAgent):
    """Companion Agent - Emotional support and journaling companion.
    
    Responsibilities:
    - Guided nightly journaling
    - Sentiment analysis and emotional patterns
    - Stoic but empathetic emotional support
    - Long-term memory of important conversations
    
    IMPORTANT:
    - ALWAYS uses local LLM for privacy
    - Saves important insights to ChromaDB
    - If serious crisis detected → suggests professional help
    
    User Context:
    - Painful breakup 2 years ago
    - Values brutal honesty with tact
    - Prefers practical solutions over empty comfort
    """
    
    # Sensitive topics requiring special handling
    SENSITIVE_TOPICS = {
        "breakup", "ruptura", "ex", "soledad", "lonely",
        "anxiety", "ansiedad", "depression", "depresión",
        "stress", "estrés", "overwhelmed", "agobiado",
    }
    
    # Crisis signals requiring professional referral
    CRISIS_KEYWORDS = {
        "suicid", "harm", "hurt myself", "hacerme daño",
        "no quiero vivir", "end it all", "acabar con todo",
    }
    
    @property
    def name(self) -> str:
        return "companion"
    
    @property
    def description(self) -> str:
        return "Emotional companion for journaling, reflection, and psychological support"
    
    def _default_system_prompt(self) -> str:
        return get_agent_prompt("companion")
    
    def invoke(self, state: AgentState) -> AgentState:
        """Process emotional/journaling interaction.
        
        Adds special logic for:
        - Detecting sensitive topics
        - Updating mood state
        - Saving insights to memory
        - Detecting crisis signals
        """
        # Check for crisis before processing
        if self._check_crisis_signals(state):
            return self._handle_crisis(state)
        
        # Process normally
        state = super().invoke(state)
        
        # Update mood state based on conversation
        self._update_mood_state(state)
        
        # Save important insights
        self._save_insights(state)
        
        return state
    
    def _check_crisis_signals(self, state: AgentState) -> bool:
        """Check if there are crisis signals in the message.
        
        Returns:
            True if crisis signals detected
        """
        if not state.get("messages"):
            return False
        
        last_message = state["messages"][-1]
        if not hasattr(last_message, "content"):
            return False
        
        content = last_message.content.lower()
        
        for keyword in self.CRISIS_KEYWORDS:
            if keyword in content:
                logger.warning(f"Crisis signal detected: '{keyword}'")
                return True
        
        return False
    
    def _handle_crisis(self, state: AgentState) -> AgentState:
        """Handle a detected crisis situation.
        
        Responds with compassion and refers to professional resources.
        """
        crisis_response = AIMessage(
            content="""Eric, what you just shared is very important and I care about you.

What you're feeling is real and valid, but I want to make sure you have the right support.

🆘 **Immediate Resources**:
- Teléfono de la Esperanza: **717 003 717** (24h)
- Emergency: **112**
- Support chat: telefonodelaesperanza.org

You don't have to face this alone. A professional can help you in ways I cannot.

Is there someone you trust you can talk to right now? A friend, family member?

I'm here to listen, but please consider reaching out to one of these resources.""",
            name=self.name,
        )
        
        state["messages"].append(crisis_response)
        state["sender"] = self.name
        state["next_agent"] = None  # End here
        
        # Log for audit
        logger.critical("Crisis detected - Referral response sent")
        
        return state
    
    def _update_mood_state(self, state: AgentState) -> None:
        """Update mood state based on conversation."""
        if not state.get("messages") or len(state["messages"]) < 2:
            return
        
        # Get recent messages for analysis
        recent_messages = state["messages"][-3:]
        
        # Simple sentiment analysis based on keywords
        positive_words = {"bien", "genial", "feliz", "happy", "great", "good", "mejor", "better"}
        negative_words = {"mal", "triste", "sad", "bad", "terrible", "peor", "cansado", "tired"}
        
        positive_count = 0
        negative_count = 0
        themes = []
        
        for msg in recent_messages:
            if not hasattr(msg, "content"):
                continue
            content = msg.content.lower()
            
            for word in positive_words:
                if word in content:
                    positive_count += 1
            
            for word in negative_words:
                if word in content:
                    negative_count += 1
            
            # Detect themes
            for topic in self.SENSITIVE_TOPICS:
                if topic in content and topic not in themes:
                    themes.append(topic)
        
        # Calculate sentiment score (-1 to 1)
        total = positive_count + negative_count
        if total > 0:
            sentiment = (positive_count - negative_count) / total
        else:
            sentiment = 0
        
        # Update state
        state["mood"]["sentiment_score"] = sentiment
        state["mood"]["recent_themes"] = themes[:5]  # Max 5 themes
        
        if sentiment > 0.3:
            state["mood"]["mood"] = "positive"
        elif sentiment < -0.3:
            state["mood"]["mood"] = "negative"
        else:
            state["mood"]["mood"] = "neutral"
        
        logger.debug(
            f"Mood updated: {state['mood']['mood']} "
            f"(score={sentiment:.2f}, themes={themes})"
        )
    
    def _save_insights(self, state: AgentState) -> None:
        """Save important insights to long-term memory."""
        # Only save if there's an agent response
        if not state.get("messages"):
            return
        
        # Find the last Companion message
        for msg in reversed(state["messages"]):
            if hasattr(msg, "name") and msg.name == self.name:
                # Check if it contains valuable insight
                # (in a real implementation, we'd use LLM for this)
                if len(msg.content) > 200:  # Long responses tend to have more value
                    try:
                        from src.services.memory import get_memory_service
                        memory = get_memory_service()
                        
                        # Save as insight
                        memory.save_insight(
                            content=msg.content[:500],  # Truncate if too long
                            source="companion_conversation",
                            importance=5,
                            user_id=state.get("user_id", "default"),
                        )
                        logger.debug("Insight saved to memory")
                    except Exception as e:
                        logger.warning(f"Error saving insight: {e}")
                break


def create_companion_agent(
    llm: BaseChatModel,
    tools: list[BaseTool] | None = None,
) -> CompanionAgent:
    """Factory function to create CompanionAgent.
    
    IMPORTANT: LLM should be local (Ollama) for privacy.
    
    Args:
        llm: LOCAL language model
        tools: Additional tools (optional)
        
    Returns:
        Configured CompanionAgent instance
    """
    from src.tools.notion_mcp import create_notion_journal_tools
    
    default_tools = create_notion_journal_tools()
    all_tools = default_tools + (tools or [])
    
    return CompanionAgent(llm=llm, tools=all_tools)
