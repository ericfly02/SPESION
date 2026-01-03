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
        
        # 1. Recuperar contexto RAG automáticamente basado en el último mensaje
        last_human_message = None
        for msg in reversed(state.get("messages", [])):
            if isinstance(msg, HumanMessage):
                last_human_message = msg.content
                break
        
        if last_human_message:
            try:
                from src.services.rag_service import get_rag_service
                rag = get_rag_service()
                # Buscar contexto relevante
                context_docs = rag.retrieve_context(str(last_human_message), k=3)
                
                if context_docs:
                    context_str = "\n\n".join(context_docs)
                    # Inyectar contexto ANTES del historial
                    messages.append(SystemMessage(
                        content=f"## MEMORIA A LARGO PLAZO (Contexto Recuperado):\n{context_str}\n\nUsa esta información para personalizar tu respuesta y recordar detalles pasados."
                    ))
            except Exception as e:
                logger.warning(f"No se pudo recuperar contexto RAG: {e}")

        # 2. Añadir contexto explícito del estado si existe (legacy)
        if state.get("retrieved_context"):
            context = "\n\n".join(state["retrieved_context"])
            context_message = HumanMessage(
                content=f"[Contexto adicional]:\n{context}"
            )
            messages.append(context_message)
        
        # 3. Añadir historial de mensajes
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
        
        # Guardar interacción en memoria RAG
        if state["messages"] and isinstance(state["messages"][-1], HumanMessage):
             try:
                from src.services.rag_service import get_rag_service
                rag = get_rag_service()
                user_msg = state["messages"][-1].content
                # Solo guardar si es relevante y no muy corto
                if len(str(user_msg)) > 10:
                    rag.add_memory(
                        content=f"User: {user_msg}\nAssistant ({self.name}): {response.content}",
                        metadata={"agent": self.name, "type": "conversation"}
                    )
             except Exception as e:
                logger.warning(f"No se pudo guardar memoria RAG: {e}")

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
