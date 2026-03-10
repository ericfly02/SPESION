"""Supervisor - Router principal del sistema multi-agente."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from src.core.prompts import SUPERVISOR_PROMPT
from src.core.state import INTENT_TO_AGENT

if TYPE_CHECKING:
    from src.core.state import AgentState

logger = logging.getLogger(__name__)


# Agentes disponibles para routing
AVAILABLE_AGENTS = [
    "scholar",
    "coach",
    "tycoon",
    "companion",
    "techlead",
    "connector",
    "executive",
    "sentinel",
]


class Supervisor:
    """Supervisor/Router principal del sistema SPESION.
    
    Responsabilidades:
    - Clasificar el intent del mensaje del usuario
    - Decidir qué agente(s) deben intervenir
    - Coordinar respuestas de múltiples agentes
    - Decidir si usar LLM local o cloud
    """
    
    def __init__(self, llm: BaseChatModel) -> None:
        """Inicializa el Supervisor.
        
        Args:
            llm: Modelo de lenguaje para clasificación
        """
        self.llm = llm
        self._routing_chain = self._create_routing_chain()
    
    def _create_routing_chain(self):
        """Crea la cadena de routing."""
        routing_prompt = ChatPromptTemplate.from_messages([
            ("system", self._get_routing_system_prompt()),
            ("human", "{input}"),
        ])
        
        return routing_prompt | self.llm | StrOutputParser()
    
    def _get_routing_system_prompt(self) -> str:
        """Genera el prompt del sistema para routing."""
        agents_list = "\n".join([
            f"- {agent}: {self._get_agent_description(agent)}"
            for agent in AVAILABLE_AGENTS
        ])
        
        return f"""Eres el router de SPESION. Tu ÚNICA tarea es decidir qué agente debe manejar el mensaje.

Agentes disponibles:
{agents_list}

REGLAS:
1. Responde SOLO con el nombre del agente (una palabra)
2. Si el mensaje es ambiguo o casual, responde "supervisor" para manejarlo tú mismo
3. Si detectas urgencia emocional, prioriza "companion"
4. Si detectas múltiples temas, elige el más importante

Ejemplos:
- "Resumen de papers de IA" → scholar
- "¿Cómo va mi portfolio?" → tycoon
- "Hoy fue un día difícil" → companion
- "Review este PR" → techlead
- "¿Qué tengo hoy?" → executive
- "Hola" → supervisor

Responde SOLO con el nombre del agente."""
    
    def _get_agent_description(self, agent: str) -> str:
        """Obtiene descripción corta de un agente."""
        descriptions = {
            "scholar": "Papers, investigación, noticias tech",
            "coach": "Fitness, Garmin, Strava, entrenamiento",
            "tycoon": "Portfolio, inversiones, finanzas, crypto",
            "companion": "Emociones, journaling, apoyo",
            "techlead": "Código, debugging, arquitectura, GitHub",
            "connector": "Networking, contactos, eventos",
            "executive": "Calendario, tareas, productividad, llamadas telefónicas, emails, quejas, acciones autónomas en el mundo real",
            "sentinel": "Sistema, privacidad, auditoría, setup",
        }
        return descriptions.get(agent, "Desconocido")
    
    def route(self, state: AgentState) -> str:
        """Determina qué agente debe manejar el mensaje.
        
        Args:
            state: Estado actual del grafo
            
        Returns:
            Nombre del agente a invocar
        """
        if not state.get("messages"):
            return "supervisor"
        
        last_message = state["messages"][-1]
        if not isinstance(last_message, HumanMessage):
            # Si el último mensaje no es del usuario, finalizar
            return "__end__"
        
        user_input = last_message.content.lower()
        
        # Primero, intentar routing basado en keywords
        agent = self._keyword_routing(user_input)
        if agent:
            logger.info(f"Routing por keyword: {agent}")
            return agent
        
        # Si no hay match por keywords, usar LLM
        try:
            agent = self._llm_routing(last_message.content)
            logger.info(f"Routing por LLM: {agent}")
            return agent
        except Exception as e:
            logger.error(f"Error en LLM routing: {e}")
            return "supervisor"
    
    def _keyword_routing(self, text: str) -> str | None:
        """Routing basado en keywords simples.
        
        Args:
            text: Texto del usuario (lowercase)
            
        Returns:
            Nombre del agente o None si no hay match
        """
        text_lower = text.lower()

        # ---------------------------------------------------------------------
        # Tool-like commands (typed by user in Telegram) must NEVER fall back to
        # conversational supervisor handling.
        # ---------------------------------------------------------------------
        # Examples: "setup_transactions_database", "setup_notion_workspace", "sync_investments_to_notion"
        if text_lower.strip().startswith(("setup_", "sync_", "/setup", "/sync")):
            return "sentinel"

        # Also catch when user embeds the tool name inside a longer sentence.
        if "setup_" in text_lower or "sync_" in text_lower:
            return "sentinel"

        # ---------------------------------------------------------------------
        # Routing explícito y seguro para Notion Setup (EVITAR re-setup accidental)
        # Solo enviar a Sentinel si el usuario pide claramente inicializar/setup.
        # ---------------------------------------------------------------------
        if "notion" in text_lower:
            setup_markers = {"setup", "inicializa", "inicializar", "initialize", "workspace", "hq"}
            if any(k in text_lower for k in setup_markers):
                return "sentinel"

            # Si habla de Notion pero en modo "operación" (crear DB, guardar cosas),
            # mejor Executive (productividad) en lugar de Sentinel.
            build_markers = {
                "base de datos", "database", "tabla", "crear", "crea", "añade", "agrega",
                "libro", "libros", "books", "lectura", "reading",
            }
            if any(k in text_lower for k in build_markers):
                return "executive"

            # Financial Notion queries → tycoon
            finance_markers = {
                "portfolio", "portafolio", "inversión", "inversion", "inversiones",
                "holdings", "posiciones", "rebalance", "rebalanceo", "finanzas",
                "finance", "stocks", "acciones", "crypto", "etf",
            }
            if any(k in text_lower for k in finance_markers):
                return "tycoon"

            # Tasks / agenda in Notion → executive
            task_markers = {"tarea", "tareas", "tasks", "agenda", "calendario"}
            if any(k in text_lower for k in task_markers):
                return "executive"

            # Generic Notion mention → executive (most operational)
            return "executive"
        
        for keyword, agent in INTENT_TO_AGENT.items():
            if keyword in text_lower:
                return agent
        
        # Keywords adicionales específicos
        specific_keywords = {
            "arxiv": "scholar",
            "paper": "scholar",
            "papers": "scholar",
            "research": "scholar",
            "noticias": "scholar",
            "news": "scholar",
            "briefing": "scholar",
            "garmin": "coach",
            "strava": "coach",
            "entreno": "coach",
            "entrena": "coach",
            "gym": "coach",
            "correr": "coach",
            "run": "coach",
            "sleep": "coach",
            "sueño": "coach",
            "hrv": "coach",
            "recovery": "coach",
            "ibkr": "tycoon",
            "crypto": "tycoon",
            "bitcoin": "tycoon",
            "etf": "tycoon",
            "portfolio": "tycoon",
            "portafolio": "tycoon",
            "inversión": "tycoon",
            "inversion": "tycoon",
            "inversiones": "tycoon",
            "rebalanceo": "tycoon",
            "rebalance": "tycoon",
            "finanzas": "tycoon",
            "finance": "tycoon",
            "dca": "tycoon",
            "acciones": "tycoon",
            "stocks": "tycoon",
            "trading": "tycoon",
            "journal": "companion",
            "diario": "companion",
            "triste": "companion",
            "solo": "companion",
            "ánimo": "companion",
            "animo": "companion",
            "siento": "companion",
            "github": "techlead",
            "pr": "techlead",
            "bug": "techlead",
            "error": "techlead",
            "deploy": "techlead",
            "code": "techlead",
            "código": "techlead",
            "linkedin": "connector",
            "contacto": "connector",
            "evento": "connector",
            "meet": "connector",
            "reunión": "executive",
            "reunion": "executive",
            "tarea": "executive",
            "todo": "executive",
            "agenda": "executive",
            "calendario": "executive",
            "calendar": "executive",
            "mañana": "executive",
            "tomorrow": "executive",
            "today": "executive",
            "hoy": "executive",
            "status": "sentinel",
            "backup": "sentinel",
            "sentinel": "sentinel",
            # SPESION 3.0: Autonomous action keywords → executive
            "llama a": "executive",
            "llamar a": "executive",
            "call ": "executive",
            "phone": "executive",
            "email": "executive",
            "envía un email": "executive",
            "envia un email": "executive",
            "send email": "executive",
            "escribe un email": "executive",
            "queja": "executive",
            "reclamación": "executive",
            "reclamacion": "executive",
            "complaint": "executive",
            "factura": "executive",
            "receipt": "executive",
            "reclamo": "executive",
            # NOTION: deliberadamente NO routeamos "notion" por keyword.
            # Solo lo hacemos arriba cuando es explícito (setup) o creación (executive).
        }
        
        for keyword, agent in specific_keywords.items():
            if keyword in text_lower:
                return agent
        
        return None
    
    def _llm_routing(self, user_input: str) -> str:
        """Routing usando LLM para casos ambiguos.
        
        Args:
            user_input: Input del usuario
            
        Returns:
            Nombre del agente
        """
        response = self._routing_chain.invoke({"input": user_input})
        response_lower = response.lower()
        
        # 1. Check exact match
        clean_response = response_lower.strip()
        if clean_response in AVAILABLE_AGENTS:
            return clean_response
            
        # 2. Check if agent name appears in text (Robust fallback)
        # Prioritize longer matches or specific order? 
        # We iterate through AVAILABLE_AGENTS
        for agent in AVAILABLE_AGENTS:
            # Check for "agent name" or "invoke agent name" patterns if needed
            # But simple containment is usually enough if the prompt is specific
            # We check boundaries to avoid partial matches (e.g. "tech" in "techlead")
            if agent in response_lower:
                logger.info(f"Routing fuzzy match: '{agent}' found in '{response_lower}'")
                return agent
        
        return "supervisor"
    
    def invoke(self, state: AgentState) -> AgentState:
        """Procesa el estado y decide el siguiente paso.
        
        Si el supervisor maneja directamente, genera una respuesta.
        Si delega, actualiza next_agent.
        
        Args:
            state: Estado actual
            
        Returns:
            Estado actualizado
        """
        # Respect forced routing (agent_hint from Discord channel or API)
        pre_set = state.get("next_agent")
        valid_agents = {
            "sentinel", "scholar", "coach", "tycoon", "companion",
            "techlead", "connector", "executive",
        }
        if pre_set and pre_set in valid_agents:
            logger.info(f"Forced routing to agent: {pre_set}")
            state["sender"] = "supervisor"
            return state

        next_agent = self.route(state)
        
        if next_agent == "supervisor" or next_agent == "__end__":
            # Manejar directamente con respuesta conversacional
            state = self._handle_directly(state)
            state["next_agent"] = None
        else:
            state["next_agent"] = next_agent
        
        state["sender"] = "supervisor"
        return state
    
    def _handle_directly(self, state: AgentState) -> AgentState:
        """Maneja el mensaje directamente sin delegar.
        
        Usado para saludos, preguntas generales, etc.
        Optimized: uses a concise prompt for fast response.
        
        Args:
            state: Estado actual
            
        Returns:
            Estado con respuesta
        """
        if not state.get("messages"):
            return state
        
        messages = [
            SystemMessage(content=(
                "Eres SPESION, asistente personal. Responde de forma directa, "
                "en español, con personalidad pero conciso. Usa 'tú'."
            )),
            *state["messages"][-5:],  # Últimos 5 mensajes para contexto
        ]
        
        try:
            response = self.llm.invoke(messages)
            response.name = "supervisor"
            state["messages"].append(response)
        except Exception as e:
            logger.error(f"Error en respuesta directa: {e}")
            error_msg = AIMessage(
                content="Disculpa, tuve un problema procesando tu mensaje. ¿Puedes intentar de nuevo?",
                name="supervisor",
            )
            state["messages"].append(error_msg)
        
        return state
    
    def should_continue(self, state: AgentState) -> Literal["continue", "end"]:
        """Determina si el grafo debe continuar o terminar.
        
        Args:
            state: Estado actual
            
        Returns:
            "continue" si hay más agentes que invocar, "end" si terminar
        """
        if state.get("next_agent"):
            return "continue"
        return "end"


def create_supervisor(llm: BaseChatModel | None = None) -> Supervisor:
    """Factory function para crear el Supervisor.
    
    SPESION 3.0: Uses ModelRouter for supervisor LLM selection.
    Supervisor uses TRIVIAL complexity (fast local model for routing).
    
    Args:
        llm: LLM a usar (default: via ModelRouter)
        
    Returns:
        Instancia del Supervisor
    """
    if llm is None:
        try:
            from src.core.model_router import get_model_router
            router = get_model_router()
            llm = router.get_llm(agent_name="supervisor", temperature=0.3)
        except Exception:
            # Fallback to old factory
            from src.services.llm_factory import get_llm, TaskType
            llm = get_llm(task_type=TaskType.GENERAL, temperature=0.3)
    
    return Supervisor(llm=llm)

