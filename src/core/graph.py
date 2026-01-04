"""LangGraph Graph - Grafo de agentes de SPESION."""

from __future__ import annotations

import logging
from typing import Literal

from langchain_core.messages import ToolMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.core.state import AgentState, create_initial_state
from src.core.supervisor import Supervisor, create_supervisor

logger = logging.getLogger(__name__)


def create_spesion_graph() -> CompiledStateGraph:
    """Crea el grafo principal de SPESION.
    
    El grafo tiene la siguiente estructura:
    
    1. Entrada (Guard) → Sanitización PII
    2. Guard → Supervisor (routing)
    3. Supervisor → Agente específico (incluido Sentinel como agente) o END
    4. Agente → Tools (opcional) → Agente
    5. Agente → Consolidación → END
    
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
    
    # Nodo de Entrada (Sanitización)
    def input_guard(state: AgentState) -> AgentState:
        """Nodo de entrada que sanitiza PII."""
        logger.debug("Ejecutando nodo Guard (Sentinel PII check)")
        return agents["sentinel"].process_incoming(state)
    
    # Nodo Supervisor (router)
    def supervisor_node(state: AgentState) -> AgentState:
        """Nodo supervisor que decide el routing."""
        logger.debug("Ejecutando nodo Supervisor")
        return supervisor.invoke(state)
    
    # Nodos de agentes
    def sentinel_node(state: AgentState) -> AgentState:
        """Nodo del agente Sentinel (Setup, Status, etc)."""
        logger.debug("Ejecutando nodo Sentinel (Agente)")
        return agents["sentinel"].invoke(state)

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
    
    # Nodo de Ejecución de Herramientas
    def tools_node(state: AgentState) -> AgentState:
        """Ejecuta las herramientas solicitadas por el agente."""
        logger.debug("Ejecutando nodo de Herramientas")
        sender_name = state.get("sender")
        if not sender_name or sender_name not in agents:
            logger.error(f"Sender desconocido para tools: {sender_name}")
            return state

        agent = agents[sender_name]
        tools_list = agent.get_tools() if hasattr(agent, "get_tools") else agent.tools
        tools_map = {t.name: t for t in tools_list}
        
        last_message = state["messages"][-1]
        if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
            return state
            
        tool_calls = last_message.tool_calls
        
        results = []
        for tool_call in tool_calls:
            tool_name = tool_call["name"]
            tool = tools_map.get(tool_name)
            
            if tool:
                logger.info(f"Ejecutando herramienta: {tool_name}")
                try:
                    # Invocar herramienta
                    output = tool.invoke(tool_call["args"])
                    
                    # Crear mensaje de respuesta de tool
                    results.append(ToolMessage(
                        tool_call_id=tool_call["id"],
                        content=str(output),
                        name=tool_name
                    ))
                except Exception as e:
                    logger.error(f"Error en tool {tool_name}: {e}")
                    results.append(ToolMessage(
                        tool_call_id=tool_call["id"],
                        content=f"Error ejecutando {tool_name}: {str(e)}",
                        name=tool_name,
                        status="error"
                    ))
            else:
                logger.warning(f"Herramienta no encontrada: {tool_name}")
                results.append(ToolMessage(
                    tool_call_id=tool_call["id"],
                    content=f"Error: Herramienta {tool_name} no disponible",
                    name=tool_name,
                    status="error"
                ))
        
        return {"messages": results, "requires_tool_execution": False}

    # Nodo de consolidación post-agente
    def consolidate_node(state: AgentState) -> AgentState:
        """Consolida la respuesta del agente."""
        logger.debug("Ejecutando nodo de consolidación")
        state["next_agent"] = None
        return state
    
    # ==========================================================================
    # AÑADIR NODOS AL GRAFO
    # ==========================================================================
    
    graph.add_node("guard", input_guard)  # Entry point (Sanitización)
    graph.add_node("supervisor", supervisor_node)
    
    # Agentes
    graph.add_node("sentinel", sentinel_node)  # Action node
    graph.add_node("scholar", scholar_node)
    graph.add_node("coach", coach_node)
    graph.add_node("tycoon", tycoon_node)
    graph.add_node("companion", companion_node)
    graph.add_node("techlead", techlead_node)
    graph.add_node("connector", connector_node)
    graph.add_node("executive", executive_node)
    
    graph.add_node("tools", tools_node)
    graph.add_node("consolidate", consolidate_node)
    
    # ==========================================================================
    # DEFINIR ARISTAS
    # ==========================================================================
    
    # Entrada siempre va a Guard
    graph.set_entry_point("guard")
    
    # Guard siempre va a Supervisor
    graph.add_edge("guard", "supervisor")
    
    # Router condicional del Supervisor
    def route_from_supervisor(state: AgentState) -> Literal[
        "sentinel", "scholar", "coach", "tycoon", "companion",
        "techlead", "connector", "executive", "end"
    ]:
        """Determina el siguiente nodo basado en next_agent."""
        next_agent = state.get("next_agent")
        
        if next_agent is None:
            return "end"
        
        valid_agents = {
            "sentinel", "scholar", "coach", "tycoon", "companion",
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
            "sentinel": "sentinel",
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
    
    # Lógica de routing post-agente (Tools o Consolidate)
    def route_from_agent(state: AgentState) -> Literal["tools", "consolidate"]:
        if state.get("requires_tool_execution"):
            return "tools"
        return "consolidate"

    # Definir edges para TODOS los agentes
    agent_names = [
        "sentinel", "scholar", "coach", "tycoon", "companion", 
        "techlead", "connector", "executive"
    ]
    
    for agent in agent_names:
        graph.add_conditional_edges(
            agent,
            route_from_agent,
            {
                "tools": "tools",
                "consolidate": "consolidate"
            }
        )
    
    # El nodo tools debe volver al agente que lo llamó
    def route_from_tools(state: AgentState) -> str:
        sender = state.get("sender")
        if sender and sender in agent_names:
            return sender
        return "consolidate"

    # Mapping para tools -> agentes
    tool_destinations = {name: name for name in agent_names}
    tool_destinations["consolidate"] = "consolidate"
    
    graph.add_conditional_edges(
        "tools",
        route_from_tools,
        tool_destinations
    )
    
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

    # Importar tools
    from src.tools.notion_mcp import create_notion_setup_tools
    
    agents = {
        "scholar": create_scholar_agent(cloud_llm),
        "coach": create_coach_agent(local_llm),
        "tycoon": create_tycoon_agent(cloud_llm),
        "companion": create_companion_agent(local_llm),
        "techlead": create_techlead_agent(cloud_llm),
        "connector": create_connector_agent(cloud_llm),
        "executive": create_executive_agent(local_llm),
        "sentinel": create_sentinel_agent(local_llm, tools=create_notion_setup_tools()),
    }
    
    logger.info(f"Creados {len(agents)} agentes")
    return agents


class SpesionAssistant:
    """Clase de alto nivel para interactuar con SPESION."""
    
    def __init__(self) -> None:
        """Inicializa el asistente."""
        self.graph = create_spesion_graph()
        self._session_counter = 0
        # Historial por usuario para dar contexto conversacional real (además del RAG)
        self._history: dict[str, list] = {}
        self._max_history_messages = 20
    
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
        from langchain_core.messages import AIMessage, HumanMessage
        
        # Crear estado inicial
        self._session_counter += 1
        session_id = f"{user_id}_{self._session_counter}"
        
        state = create_initial_state(
            user_id=user_id,
            session_id=session_id,
            telegram_chat_id=telegram_chat_id,
        )
        
        # Añadir historial + mensaje del usuario (contexto conversacional real)
        history = self._history.get(user_id, [])
        state["messages"] = [*history, HumanMessage(content=message)]
        state["original_query"] = message
        state["is_voice_message"] = is_voice
        
        # Ejecutar grafo
        try:
            result = self.graph.invoke(state)
            
            # Extraer respuesta
            if result.get("messages"):
                # Buscar el último mensaje con contenido real
                for msg in reversed(result["messages"]):
                    if hasattr(msg, "content") and msg.content and isinstance(msg.content, str):
                        # Persistir en historial
                        history = state["messages"][-self._max_history_messages :]
                        history.append(AIMessage(content=msg.content))
                        self._history[user_id] = history[-self._max_history_messages :]
                        return msg.content
                
                last = result["messages"][-1]
                final = str(last.content) if hasattr(last, "content") else "..."
                history = state["messages"][-self._max_history_messages :]
                history.append(AIMessage(content=final))
                self._history[user_id] = history[-self._max_history_messages :]
                return final
            
            return "No pude procesar tu mensaje. (Respuesta vacía)"
            
        except Exception as e:
            logger.error(f"Error en grafo: {e}", exc_info=True)
            return f"Error procesando el mensaje: {str(e)}"
    
    async def achat(
        self,
        message: str,
        user_id: str = "default",
        telegram_chat_id: int | None = None,
        is_voice: bool = False,
    ) -> str:
        """Versión asíncrona de chat."""
        from langchain_core.messages import AIMessage, HumanMessage
        
        self._session_counter += 1
        session_id = f"{user_id}_{self._session_counter}"
        
        state = create_initial_state(
            user_id=user_id,
            session_id=session_id,
            telegram_chat_id=telegram_chat_id,
        )
        
        history = self._history.get(user_id, [])
        state["messages"] = [*history, HumanMessage(content=message)]
        state["original_query"] = message
        state["is_voice_message"] = is_voice
        
        try:
            result = await self.graph.ainvoke(state)
            
            if result.get("messages"):
                for msg in reversed(result["messages"]):
                    if hasattr(msg, "content") and msg.content and isinstance(msg.content, str):
                        history = state["messages"][-self._max_history_messages :]
                        history.append(AIMessage(content=msg.content))
                        self._history[user_id] = history[-self._max_history_messages :]
                        return msg.content
                
                last = result["messages"][-1]
                final = str(last.content) if hasattr(last, "content") else "..."
                history = state["messages"][-self._max_history_messages :]
                history.append(AIMessage(content=final))
                self._history[user_id] = history[-self._max_history_messages :]
                return final
            
            return "No pude procesar tu mensaje. (Respuesta vacía)"
            
        except Exception as e:
            logger.error(f"Error en grafo async: {e}", exc_info=True)
            return f"Error procesando el mensaje: {str(e)}"


# Singleton
_assistant: SpesionAssistant | None = None


def get_assistant() -> SpesionAssistant:
    """Obtiene la instancia del asistente."""
    global _assistant
    if _assistant is None:
        _assistant = SpesionAssistant()
    return _assistant
