"""LangGraph Graph - Grafo de agentes de SPESION."""

from __future__ import annotations

import logging
from typing import Literal

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.core.state import AgentState, create_initial_state
from src.core.supervisor import Supervisor, create_supervisor

logger = logging.getLogger(__name__)


def create_spesion_graph() -> CompiledStateGraph:
    """Crea el grafo principal de SPESION.
    
    El grafo tiene la siguiente estructura:
    
    1. Entrada → Sentinel (sanitización PII)
    2. Sentinel → Supervisor (routing)
    3. Supervisor → Agente específico o END
    4. Agente → Supervisor (consolidación)
    5. Supervisor → END
    
    Returns:
        Grafo compilado listo para ejecutar
    """
    # Crear el grafo
    graph = StateGraph(AgentState)
    
    # Crear supervisor
    supervisor = create_supervisor()
    
    # Crear agentes (lazy loading)
    agents = _create_agents()
    
    # ==========================================================================
    # DEFINIR NODOS
    # ==========================================================================
    
    # Nodo Sentinel (entrada - sanitización)
    def sentinel_node(state: AgentState) -> AgentState:
        """Nodo de entrada que sanitiza PII."""
        logger.debug("Ejecutando nodo Sentinel")
        return agents["sentinel"].process_incoming(state)
    
    # Nodo Supervisor (router)
    def supervisor_node(state: AgentState) -> AgentState:
        """Nodo supervisor que decide el routing."""
        logger.debug("Ejecutando nodo Supervisor")
        return supervisor.invoke(state)
    
    # Nodos de agentes
    def scholar_node(state: AgentState) -> AgentState:
        logger.debug("Ejecutando nodo Scholar")
        return agents["scholar"].invoke(state)
    
    def coach_node(state: AgentState) -> AgentState:
        logger.debug("Ejecutando nodo Coach")
        return agents["coach"].invoke(state)
    
    def tycoon_node(state: AgentState) -> AgentState:
        logger.debug("Ejecutando nodo Tycoon")
        return agents["tycoon"].invoke(state)
    
    def companion_node(state: AgentState) -> AgentState:
        logger.debug("Ejecutando nodo Companion")
        return agents["companion"].invoke(state)
    
    def techlead_node(state: AgentState) -> AgentState:
        logger.debug("Ejecutando nodo TechLead")
        return agents["techlead"].invoke(state)
    
    def connector_node(state: AgentState) -> AgentState:
        logger.debug("Ejecutando nodo Connector")
        return agents["connector"].invoke(state)
    
    def executive_node(state: AgentState) -> AgentState:
        logger.debug("Ejecutando nodo Executive")
        return agents["executive"].invoke(state)
    
    # Nodo de consolidación post-agente
    def consolidate_node(state: AgentState) -> AgentState:
        """Consolida la respuesta del agente."""
        logger.debug("Ejecutando nodo de consolidación")
        # Marcar que no hay siguiente agente (terminar)
        state["next_agent"] = None
        return state
    
    # ==========================================================================
    # AÑADIR NODOS AL GRAFO
    # ==========================================================================
    
    graph.add_node("sentinel", sentinel_node)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("scholar", scholar_node)
    graph.add_node("coach", coach_node)
    graph.add_node("tycoon", tycoon_node)
    graph.add_node("companion", companion_node)
    graph.add_node("techlead", techlead_node)
    graph.add_node("connector", connector_node)
    graph.add_node("executive", executive_node)
    graph.add_node("consolidate", consolidate_node)
    
    # ==========================================================================
    # DEFINIR ARISTAS
    # ==========================================================================
    
    # Entrada siempre va a Sentinel
    graph.set_entry_point("sentinel")
    
    # Sentinel siempre va a Supervisor
    graph.add_edge("sentinel", "supervisor")
    
    # Router condicional del Supervisor
    def route_from_supervisor(state: AgentState) -> Literal[
        "scholar", "coach", "tycoon", "companion",
        "techlead", "connector", "executive", "end"
    ]:
        """Determina el siguiente nodo basado en next_agent."""
        next_agent = state.get("next_agent")
        
        if next_agent is None:
            return "end"
        
        valid_agents = {
            "scholar", "coach", "tycoon", "companion",
            "techlead", "connector", "executive",
        }
        
        if next_agent in valid_agents:
            return next_agent
        
        logger.warning(f"Agente desconocido: {next_agent}, finalizando")
        return "end"
    
    graph.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            "scholar": "scholar",
            "coach": "coach",
            "tycoon": "tycoon",
            "companion": "companion",
            "techlead": "techlead",
            "connector": "connector",
            "executive": "executive",
            "end": END,
        },
    )
    
    # Todos los agentes van a consolidación
    for agent in ["scholar", "coach", "tycoon", "companion", 
                  "techlead", "connector", "executive"]:
        graph.add_edge(agent, "consolidate")
    
    # Consolidación termina
    graph.add_edge("consolidate", END)
    
    # ==========================================================================
    # COMPILAR Y RETORNAR
    # ==========================================================================
    
    compiled = graph.compile()
    logger.info("Grafo SPESION compilado exitosamente")
    
    return compiled


def _create_agents() -> dict:
    """Crea todos los agentes del sistema.
    
    Returns:
        Dict con agentes por nombre
    """
    from src.services.llm_factory import get_factory, TaskType
    
    factory = get_factory()
    
    # Obtener LLMs
    local_llm = factory.get_llm(task_type=TaskType.PRIVATE, temperature=0.7)
    cloud_llm = factory.get_llm(task_type=TaskType.ANALYSIS, temperature=0.7)
    
    # Importar agentes
    from src.agents import (
        ScholarAgent,
        CoachAgent,
        TycoonAgent,
        CompanionAgent,
        TechLeadAgent,
        ConnectorAgent,
        ExecutiveAgent,
        SentinelAgent,
    )
    from src.agents.scholar import create_scholar_agent
    from src.agents.coach import create_coach_agent
    from src.agents.tycoon import create_tycoon_agent
    from src.agents.companion import create_companion_agent
    from src.agents.techlead import create_techlead_agent
    from src.agents.connector import create_connector_agent
    from src.agents.executive import create_executive_agent
    from src.agents.sentinel import create_sentinel_agent
    
    agents = {
        "scholar": create_scholar_agent(cloud_llm),
        "coach": create_coach_agent(local_llm),  # Local por privacidad
        "tycoon": create_tycoon_agent(cloud_llm),
        "companion": create_companion_agent(local_llm),  # Local por privacidad
        "techlead": create_techlead_agent(cloud_llm),
        "connector": create_connector_agent(cloud_llm),
        "executive": create_executive_agent(local_llm),
        "sentinel": create_sentinel_agent(local_llm),  # Local por privacidad
    }
    
    logger.info(f"Creados {len(agents)} agentes")
    return agents


class SpesionAssistant:
    """Clase de alto nivel para interactuar con SPESION."""
    
    def __init__(self) -> None:
        """Inicializa el asistente."""
        self.graph = create_spesion_graph()
        self._session_counter = 0
    
    def chat(
        self,
        message: str,
        user_id: str = "default",
        telegram_chat_id: int | None = None,
        is_voice: bool = False,
    ) -> str:
        """Procesa un mensaje y retorna la respuesta.
        
        Args:
            message: Mensaje del usuario
            user_id: ID del usuario
            telegram_chat_id: ID del chat de Telegram
            is_voice: Si el mensaje viene de voz
            
        Returns:
            Respuesta del asistente
        """
        from langchain_core.messages import HumanMessage
        
        # Crear estado inicial
        self._session_counter += 1
        session_id = f"{user_id}_{self._session_counter}"
        
        state = create_initial_state(
            user_id=user_id,
            session_id=session_id,
            telegram_chat_id=telegram_chat_id,
        )
        
        # Añadir mensaje del usuario
        state["messages"] = [HumanMessage(content=message)]
        state["original_query"] = message
        state["is_voice_message"] = is_voice
        
        # Ejecutar grafo
        try:
            result = self.graph.invoke(state)
            
            # Extraer respuesta
            if result.get("messages"):
                last_message = result["messages"][-1]
                if hasattr(last_message, "content"):
                    return last_message.content
            
            return "No pude procesar tu mensaje. ¿Puedes intentar de nuevo?"
            
        except Exception as e:
            logger.error(f"Error en grafo: {e}")
            return f"Error procesando el mensaje: {str(e)}"
    
    async def achat(
        self,
        message: str,
        user_id: str = "default",
        telegram_chat_id: int | None = None,
        is_voice: bool = False,
    ) -> str:
        """Versión asíncrona de chat.
        
        Args:
            message: Mensaje del usuario
            user_id: ID del usuario
            telegram_chat_id: ID del chat de Telegram
            is_voice: Si el mensaje viene de voz
            
        Returns:
            Respuesta del asistente
        """
        from langchain_core.messages import HumanMessage
        
        self._session_counter += 1
        session_id = f"{user_id}_{self._session_counter}"
        
        state = create_initial_state(
            user_id=user_id,
            session_id=session_id,
            telegram_chat_id=telegram_chat_id,
        )
        
        state["messages"] = [HumanMessage(content=message)]
        state["original_query"] = message
        state["is_voice_message"] = is_voice
        
        try:
            result = await self.graph.ainvoke(state)
            
            if result.get("messages"):
                last_message = result["messages"][-1]
                if hasattr(last_message, "content"):
                    return last_message.content
            
            return "No pude procesar tu mensaje. ¿Puedes intentar de nuevo?"
            
        except Exception as e:
            logger.error(f"Error en grafo async: {e}")
            return f"Error procesando el mensaje: {str(e)}"


# Singleton
_assistant: SpesionAssistant | None = None


def get_assistant() -> SpesionAssistant:
    """Obtiene la instancia del asistente."""
    global _assistant
    if _assistant is None:
        _assistant = SpesionAssistant()
    return _assistant

