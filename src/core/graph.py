"""LangGraph Graph - Grafo de agentes de SPESION.

SPESION 3.0: Uses ModelRouter for intelligent per-agent model selection,
workspace context injection, and cognitive loop integration.
"""

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

    SPESION 3.0: Uses ModelRouter for intelligent per-agent model selection.
    Each agent gets the best available model based on its complexity/privacy needs.
    
    Returns:
        Dict con agentes por nombre
    """
    from src.core.model_router import get_model_router
    
    router = get_model_router()
    
    # Each agent gets its own LLM based on ModelRouter's intelligence:
    # - supervisor/sentinel/companion/coach → local Ollama (privacy + speed)
    # - scholar/tycoon/techlead → cloud if available, fallback to local
    # - connector/executive → moderate (cloud-light or heavy local)

    def get_agent_llm(agent_name: str, temp: float = 0.7):
        try:
            return router.get_llm(agent_name=agent_name, temperature=temp)
        except RuntimeError:
            # Ultimate fallback
            from langchain_ollama import ChatOllama
            return ChatOllama(model="llama3.2:3b", temperature=temp)

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
        "scholar": create_scholar_agent(get_agent_llm("scholar")),
        "coach": create_coach_agent(get_agent_llm("coach")),
        "tycoon": create_tycoon_agent(get_agent_llm("tycoon")),
        "companion": create_companion_agent(get_agent_llm("companion")),
        "techlead": create_techlead_agent(get_agent_llm("techlead")),
        "connector": create_connector_agent(get_agent_llm("connector")),
        "executive": create_executive_agent(get_agent_llm("executive")),
        "sentinel": create_sentinel_agent(get_agent_llm("sentinel"), tools=create_notion_setup_tools()),
    }
    
    # Log which models were selected
    logger.info(f"Creados {len(agents)} agentes via ModelRouter")
    try:
        health = router.get_health_status()
        logger.info(f"Provider status: {health['providers']}")
    except Exception:
        pass

    return agents


class SpesionAssistant:
    """Clase de alto nivel para interactuar con SPESION.

    SPESION 3.0: Integrates workspace context, heartbeat runner, cognitive loop,
    and intelligent model routing. Uses SQLite session persistence.
    Supports ``agent_hint`` for forced routing (Discord channel → agent).
    """

    def __init__(self, enable_heartbeat: bool = False) -> None:
        self.graph = create_spesion_graph()
        self._session_counter = 0
        self._max_history_messages = 20

        # Tracks the last response metadata (used by the API layer)
        self.last_agent: str | None = None
        self.last_session_id: str | None = None

        # Session store (lazy init)
        self._store = None

        # --- SPESION 3.0: New subsystems ---
        self._workspace_loader = None
        self._heartbeat = None
        self._cognitive = None
        self._heartbeat_enabled = enable_heartbeat

        # Pre-load workspace context at startup
        try:
            _ = self.workspace_loader
            logger.info("Workspace context loaded successfully")
        except Exception as e:
            logger.warning(f"Workspace context not available: {e}")

        # Start heartbeat if enabled
        if enable_heartbeat:
            try:
                self._start_heartbeat()
            except Exception as e:
                logger.warning(f"Heartbeat not started: {e}")

    @property
    def store(self):
        if self._store is None:
            from src.persistence.session_store import get_session_store
            self._store = get_session_store()
        return self._store

    @property
    def workspace_loader(self):
        if self._workspace_loader is None:
            from src.core.workspace_loader import WorkspaceLoader
            self._workspace_loader = WorkspaceLoader()
        return self._workspace_loader

    @property
    def cognitive(self):
        if self._cognitive is None:
            from src.cognitive.reflection import CognitiveLoop
            self._cognitive = CognitiveLoop()
        return self._cognitive

    def _start_heartbeat(self):
        """Start the heartbeat runner for proactive tasks."""
        import asyncio
        from src.heartbeat.runner import HeartbeatRunner

        self._heartbeat = HeartbeatRunner()
        # Register a notification callback
        self._heartbeat.on_notification = self._handle_heartbeat_notification
        # Start in background (non-blocking)
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self._heartbeat.start())
            else:
                logger.info("Heartbeat will start when event loop runs")
        except RuntimeError:
            logger.info("Heartbeat deferred — no event loop yet")

    def _handle_heartbeat_notification(self, notification: dict):
        """Handle notifications from the heartbeat system."""
        logger.info(f"Heartbeat notification: {notification.get('type', 'unknown')}")
        # Store for next user interaction
        if not hasattr(self, '_pending_notifications'):
            self._pending_notifications = []
        self._pending_notifications.append(notification)

    def get_pending_notifications(self) -> list[dict]:
        """Get and clear pending heartbeat notifications."""
        if not hasattr(self, '_pending_notifications'):
            return []
        notifications = self._pending_notifications.copy()
        self._pending_notifications.clear()
        return notifications

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _extract_response(self, result: dict) -> str:
        """Pull the final text response out of the graph result."""
        if result.get("messages"):
            for msg in reversed(result["messages"]):
                if hasattr(msg, "content") and msg.content and isinstance(msg.content, str):
                    return msg.content
            last = result["messages"][-1]
            return str(last.content) if hasattr(last, "content") else "..."
        return "No pude procesar tu mensaje. (Respuesta vacía)"

    def _load_history(self, user_id: str, platform: str = "api"):
        """Load recent messages from the session store as LangChain messages."""
        from langchain_core.messages import AIMessage, HumanMessage

        session_id = self.store.get_or_create_session(user_id, platform)
        rows = self.store.get_messages(session_id, limit=self._max_history_messages)

        msgs = []
        for r in rows:
            if r["role"] == "user":
                msgs.append(HumanMessage(content=r["content"]))
            elif r["role"] == "assistant":
                msgs.append(AIMessage(content=r["content"]))
        return session_id, msgs

    def _persist(self, session_id: str, user_msg: str, ai_msg: str, agent: str | None = None):
        """Save user + assistant messages to the session store."""
        self.store.save_message(session_id, "user", user_msg)
        self.store.save_message(session_id, "assistant", ai_msg, agent=agent)
        # Auto-prune very long sessions
        self.store.prune_old_messages(session_id, keep=60)

    # ------------------------------------------------------------------
    # Sync chat (kept for backward-compat with CLI / Telegram blocking)
    # ------------------------------------------------------------------
    def chat(
        self,
        message: str,
        user_id: str = "default",
        telegram_chat_id: int | None = None,
        is_voice: bool = False,
        agent_hint: str | None = None,
    ) -> str:
        from langchain_core.messages import HumanMessage

        platform = "telegram" if telegram_chat_id else "api"
        session_id, history = self._load_history(user_id, platform)
        self.last_session_id = session_id

        state = create_initial_state(
            user_id=user_id,
            session_id=session_id,
            telegram_chat_id=telegram_chat_id,
        )

        # SPESION 3.0: Inject workspace context into state
        try:
            ws_ctx = self.workspace_loader.load()
            state["workspace_context"] = ws_ctx.get("combined", "")
        except Exception:
            pass

        # Prepend any pending heartbeat notifications
        notification_prefix = ""
        notifications = self.get_pending_notifications()
        if notifications:
            items = [n.get("message", "") for n in notifications if n.get("message")]
            if items:
                notification_prefix = "[SYSTEM NOTIFICATIONS]\n" + "\n".join(f"• {m}" for m in items) + "\n\n"

        user_content = notification_prefix + message if notification_prefix else message
        state["messages"] = [*history, HumanMessage(content=user_content)]
        state["original_query"] = message
        state["is_voice_message"] = is_voice
        if agent_hint:
            state["next_agent"] = agent_hint

        try:
            result = self.graph.invoke(state)
            response = self._extract_response(result)
            self.last_agent = result.get("sender", "supervisor")
            self._persist(session_id, message, response, agent=self.last_agent)
            return response
        except Exception as e:
            logger.error(f"Error en grafo: {e}", exc_info=True)
            return f"Error procesando el mensaje: {str(e)}"

    # ------------------------------------------------------------------
    # Async chat (used by API + bots)
    # ------------------------------------------------------------------
    async def achat(
        self,
        message: str,
        user_id: str = "default",
        telegram_chat_id: int | None = None,
        is_voice: bool = False,
        agent_hint: str | None = None,
    ) -> str:
        from langchain_core.messages import HumanMessage

        platform = "telegram" if telegram_chat_id else "api"
        session_id, history = self._load_history(user_id, platform)
        self.last_session_id = session_id

        state = create_initial_state(
            user_id=user_id,
            session_id=session_id,
            telegram_chat_id=telegram_chat_id,
        )

        # SPESION 3.0: Inject workspace context into state
        try:
            ws_ctx = self.workspace_loader.load()
            state["workspace_context"] = ws_ctx.get("combined", "")
        except Exception:
            pass

        # Prepend any pending heartbeat notifications
        notification_prefix = ""
        notifications = self.get_pending_notifications()
        if notifications:
            items = [n.get("message", "") for n in notifications if n.get("message")]
            if items:
                notification_prefix = "[SYSTEM NOTIFICATIONS]\n" + "\n".join(f"• {m}" for m in items) + "\n\n"

        user_content = notification_prefix + message if notification_prefix else message
        state["messages"] = [*history, HumanMessage(content=user_content)]
        state["original_query"] = message
        state["is_voice_message"] = is_voice
        if agent_hint:
            state["next_agent"] = agent_hint

        try:
            result = await self.graph.ainvoke(state)
            response = self._extract_response(result)
            self.last_agent = result.get("sender", "supervisor")
            self._persist(session_id, message, response, agent=self.last_agent)
            return response
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
