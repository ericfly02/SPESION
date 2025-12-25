"""Base Agent - Abstract base class for all SPESION agents."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool

if TYPE_CHECKING:
    from src.core.state import AgentState

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Abstract base class for all SPESION agents.
    
    Each specialized agent must inherit from this class and implement
    the abstract methods. The class handles tool binding gracefully,
    falling back to plain LLM if tools are not supported.
    """
    
    def __init__(
        self,
        llm: BaseChatModel,
        tools: list[BaseTool] | None = None,
        system_prompt: str | None = None,
    ) -> None:
        """Initialize the agent.
        
        Args:
            llm: Language model to use
            tools: List of available tools
            system_prompt: System prompt for the agent
        """
        self.llm = llm
        self.tools = tools or []
        self._system_prompt = system_prompt
        self._supports_tools = False
        
        # Attempt to bind tools to LLM if available
        if self.tools:
            try:
                self.llm_with_tools = llm.bind_tools(self.tools)
                self._supports_tools = True
                logger.debug(f"Successfully bound {len(self.tools)} tools to LLM")
            except Exception as e:
                # Model doesn't support tools - fall back to plain LLM
                logger.warning(
                    f"Model does not support tools, running without them: {e}"
                )
                self.llm_with_tools = llm
                self._supports_tools = False
        else:
            self.llm_with_tools = llm
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name of the agent."""
        ...
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Brief description for the Supervisor router."""
        ...
    
    @property
    def system_prompt(self) -> str:
        """System prompt for the agent."""
        if self._system_prompt:
            return self._system_prompt
        return self._default_system_prompt()
    
    @abstractmethod
    def _default_system_prompt(self) -> str:
        """Default system prompt if none is provided."""
        ...
    
    @property
    def supports_tools(self) -> bool:
        """Check if the current LLM supports tool calling."""
        return self._supports_tools
    
    def get_tools(self) -> list[BaseTool]:
        """Return the available tools for this agent."""
        return self.tools if self._supports_tools else []
    
    def invoke(self, state: AgentState) -> AgentState:
        """Invoke the agent with the current state.
        
        This is the main method that the LangGraph will call.
        
        Args:
            state: Current graph state
            
        Returns:
            Updated state with the agent's response
        """
        logger.info(f"Agent {self.name} invoked")
        
        try:
            # Build messages with context
            messages = self._build_messages(state)
            
            # Invoke LLM
            response = self.llm_with_tools.invoke(messages)
            
            # Process response
            state = self._process_response(state, response)
            
            # Update sender
            state["sender"] = self.name
            
            logger.info(f"Agent {self.name} completed successfully")
            
        except Exception as e:
            logger.error(f"Error in agent {self.name}: {e}")
            # Add error message to state
            error_message = AIMessage(
                content=f"Error in {self.name}: {str(e)}. Please try again.",
                name=self.name,
            )
            state["messages"].append(error_message)
            state["sender"] = self.name
        
        return state
    
    def _build_messages(self, state: AgentState) -> list:
        """Build the message list for the LLM.
        
        Args:
            state: Current state
            
        Returns:
            List of messages including system prompt and context
        """
        messages = [SystemMessage(content=self.system_prompt)]
        
        # Add RAG context if available
        if state.get("retrieved_context"):
            context = "\n\n".join(state["retrieved_context"])
            context_message = HumanMessage(
                content=f"[Relevant context from memory]:\n{context}"
            )
            messages.append(context_message)
        
        # Add tool availability notice if tools are disabled
        if self.tools and not self._supports_tools:
            notice = HumanMessage(
                content="[System notice: Tools are not available with the current model. "
                "Please provide direct answers based on your knowledge.]"
            )
            messages.append(notice)
        
        # Add message history (last N to not exceed context)
        recent_messages = state.get("messages", [])[-10:]
        messages.extend(recent_messages)
        
        return messages
    
    def _process_response(
        self, 
        state: AgentState, 
        response: AIMessage,
    ) -> AgentState:
        """Process the LLM response.
        
        Args:
            state: Current state
            response: LLM response
            
        Returns:
            Updated state
        """
        # Add agent name to message
        response.name = self.name
        
        # Add response to history
        state["messages"].append(response)
        
        # Check for pending tool calls (only if tools are supported)
        if self._supports_tools and hasattr(response, "tool_calls") and response.tool_calls:
            state["requires_tool_execution"] = True
            state["tool_results"] = None
        else:
            state["requires_tool_execution"] = False
        
        return state
    
    async def ainvoke(self, state: AgentState) -> AgentState:
        """Async version of invoke.
        
        Args:
            state: Current graph state
            
        Returns:
            Updated state with the agent's response
        """
        logger.info(f"Agent {self.name} invoked (async)")
        
        try:
            messages = self._build_messages(state)
            response = await self.llm_with_tools.ainvoke(messages)
            state = self._process_response(state, response)
            state["sender"] = self.name
            logger.info(f"Agent {self.name} completed successfully (async)")
            
        except Exception as e:
            logger.error(f"Error in agent {self.name}: {e}")
            error_message = AIMessage(
                content=f"Error in {self.name}: {str(e)}. Please try again.",
                name=self.name,
            )
            state["messages"].append(error_message)
            state["sender"] = self.name
        
        return state
    
    def __repr__(self) -> str:
        tools_info = f", tools={len(self.tools)}" if self.tools else ""
        return f"{self.__class__.__name__}(name={self.name!r}{tools_info})"
