"""Base Agent - Clase abstracta para todos los agentes de SPESION."""

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
    """Clase base abstracta para todos los agentes de SPESION.
    
    Cada agente especializado debe heredar de esta clase e implementar
    los métodos abstractos.
    """
    
    def __init__(
        self,
        llm: BaseChatModel,
        tools: list[BaseTool] | None = None,
        system_prompt: str | None = None,
    ) -> None:
        """Inicializa el agente.
        
        Args:
            llm: Modelo de lenguaje a usar
            tools: Lista de herramientas disponibles
            system_prompt: Prompt del sistema para el agente
        """
        self.llm = llm
        self.tools = tools or []
        self._system_prompt = system_prompt
        
        # Bind tools al LLM si están disponibles
        if self.tools:
            self.llm_with_tools = llm.bind_tools(self.tools)
        else:
            self.llm_with_tools = llm
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre único del agente."""
        ...
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Descripción breve del agente para el Supervisor."""
        ...
    
    @property
    def system_prompt(self) -> str:
        """Prompt del sistema del agente."""
        if self._system_prompt:
            return self._system_prompt
        return self._default_system_prompt()
    
    @abstractmethod
    def _default_system_prompt(self) -> str:
        """Prompt del sistema por defecto si no se proporciona uno."""
        ...
    
    def get_tools(self) -> list[BaseTool]:
        """Retorna las herramientas disponibles para este agente."""
        return self.tools
    
    def invoke(self, state: AgentState) -> AgentState:
        """Invoca el agente con el estado actual.
        
        Este es el método principal que el grafo LangGraph llamará.
        
        Args:
            state: Estado actual del grafo
            
        Returns:
            Estado actualizado con la respuesta del agente
        """
        logger.info(f"Agente {self.name} invocado")
        
        try:
            # Construir mensajes con contexto
            messages = self._build_messages(state)
            
            # Invocar LLM
            response = self.llm_with_tools.invoke(messages)
            
            # Procesar respuesta
            state = self._process_response(state, response)
            
            # Actualizar sender
            state["sender"] = self.name
            
            logger.info(f"Agente {self.name} completado exitosamente")
            
        except Exception as e:
            logger.error(f"Error en agente {self.name}: {e}")
            # Añadir mensaje de error al estado
            error_message = AIMessage(
                content=f"Error en {self.name}: {str(e)}. Por favor, intenta de nuevo.",
                name=self.name,
            )
            state["messages"].append(error_message)
            state["sender"] = self.name
        
        return state
    
    def _build_messages(self, state: AgentState) -> list:
        """Construye la lista de mensajes para el LLM.
        
        Args:
            state: Estado actual
            
        Returns:
            Lista de mensajes incluyendo system prompt y contexto
        """
        messages = [SystemMessage(content=self.system_prompt)]
        
        # Añadir contexto RAG si existe
        if state.get("retrieved_context"):
            context = "\n\n".join(state["retrieved_context"])
            context_message = HumanMessage(
                content=f"[Contexto relevante de la memoria]:\n{context}"
            )
            messages.append(context_message)
        
        # Añadir historial de mensajes (últimos N para no exceder contexto)
        recent_messages = state.get("messages", [])[-10:]
        messages.extend(recent_messages)
        
        return messages
    
    def _process_response(
        self, 
        state: AgentState, 
        response: AIMessage,
    ) -> AgentState:
        """Procesa la respuesta del LLM.
        
        Args:
            state: Estado actual
            response: Respuesta del LLM
            
        Returns:
            Estado actualizado
        """
        # Añadir nombre del agente al mensaje
        response.name = self.name
        
        # Añadir respuesta al historial
        state["messages"].append(response)
        
        # Verificar si hay tool calls pendientes
        if hasattr(response, "tool_calls") and response.tool_calls:
            state["requires_tool_execution"] = True
            state["tool_results"] = None
        else:
            state["requires_tool_execution"] = False
        
        return state
    
    async def ainvoke(self, state: AgentState) -> AgentState:
        """Versión asíncrona de invoke.
        
        Args:
            state: Estado actual del grafo
            
        Returns:
            Estado actualizado con la respuesta del agente
        """
        logger.info(f"Agente {self.name} invocado (async)")
        
        try:
            messages = self._build_messages(state)
            response = await self.llm_with_tools.ainvoke(messages)
            state = self._process_response(state, response)
            state["sender"] = self.name
            logger.info(f"Agente {self.name} completado exitosamente (async)")
            
        except Exception as e:
            logger.error(f"Error en agente {self.name}: {e}")
            error_message = AIMessage(
                content=f"Error en {self.name}: {str(e)}. Por favor, intenta de nuevo.",
                name=self.name,
            )
            state["messages"].append(error_message)
            state["sender"] = self.name
        
        return state
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"
