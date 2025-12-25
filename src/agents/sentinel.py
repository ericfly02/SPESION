"""Sentinel Agent - DevOps, Security, and Privacy."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool

from .base_agent import BaseAgent
from src.core.prompts import get_agent_prompt

if TYPE_CHECKING:
    from src.core.state import AgentState

logger = logging.getLogger(__name__)


class SentinelAgent(BaseAgent):
    """Sentinel Agent - System guardian and privacy protector.
    
    Responsibilities:
    - Detect and sanitize PII before sending to cloud LLMs
    - Monitor service and MCP status
    - Audit logs and detect anomalies
    - Manage backups and recovery
    
    IMPORTANT: This agent processes ALL messages before
    they're sent to other agents when privacy_mode is active.
    """
    
    # PII patterns to detect
    PII_PATTERNS = {
        "credit_card": r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
        "nie_dni": r"\b[XYZ]?\d{7,8}[A-Z]\b",
        "phone_spain": r"\b(?:\+34|0034)?[6789]\d{8}\b",
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "iban": r"\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}(?:[A-Z0-9]?){0,16}\b",
        "passport": r"\b[A-Z]{2}\d{6,9}\b",
        "address": r"\b(?:calle|carrer|c/|avda|av\.|plaza|pl\.)\s+[A-Za-záéíóúñÁÉÍÓÚÑ\s]+\s+\d+\b",
        "api_key": r"\b(?:sk-|api[-_]?key|token)[-A-Za-z0-9_]{20,}\b",
        "password": r"(?:password|contraseña|pwd|pass)\s*[:=]\s*\S+",
    }
    
    # Redaction labels
    PII_LABELS = {
        "credit_card": "[CARD_REDACTED]",
        "nie_dni": "[NIE_DNI_REDACTED]",
        "phone_spain": "[PHONE_REDACTED]",
        "email": "[EMAIL_REDACTED]",
        "iban": "[IBAN_REDACTED]",
        "passport": "[PASSPORT_REDACTED]",
        "address": "[ADDRESS_REDACTED]",
        "api_key": "[API_KEY_REDACTED]",
        "password": "[PASSWORD_REDACTED]",
    }
    
    @property
    def name(self) -> str:
        return "sentinel"
    
    @property
    def description(self) -> str:
        return "Privacy guardian, system monitoring, and audit"
    
    def _default_system_prompt(self) -> str:
        return get_agent_prompt("sentinel")
    
    def sanitize_text(self, text: str) -> tuple[str, list[dict]]:
        """Detect and redact PII in text.
        
        Args:
            text: Text to sanitize
            
        Returns:
            Tuple of (sanitized text, list of detections)
        """
        sanitized = text
        detections = []
        
        for pii_type, pattern in self.PII_PATTERNS.items():
            matches = re.finditer(pattern, sanitized, re.IGNORECASE)
            for match in matches:
                detections.append({
                    "type": pii_type,
                    "original": match.group()[:10] + "...",  # Truncate for log
                    "position": match.span(),
                })
                sanitized = sanitized.replace(
                    match.group(),
                    self.PII_LABELS[pii_type],
                )
        
        if detections:
            logger.warning(
                f"PII detected and sanitized: {len(detections)} instances"
            )
        
        return sanitized, detections
    
    def process_incoming(self, state: AgentState) -> AgentState:
        """Process incoming message for PII detection.
        
        This method should be called BEFORE the supervisor
        for all new messages.
        
        Args:
            state: Current state
            
        Returns:
            State with privacy_mode updated if PII detected
        """
        if not state.get("messages"):
            return state
        
        last_message = state["messages"][-1]
        if not isinstance(last_message, HumanMessage):
            return state
        
        # Sanitize message
        original_content = last_message.content
        sanitized_content, detections = self.sanitize_text(original_content)
        
        if detections:
            # Update privacy state
            state["privacy"]["pii_detected"] = True
            state["privacy"]["sanitized_content"] = sanitized_content
            state["privacy"]["use_local_llm"] = True
            
            # Determine risk level
            high_risk_types = {"credit_card", "password", "api_key", "iban"}
            detected_types = {d["type"] for d in detections}
            
            if detected_types & high_risk_types:
                state["privacy"]["risk_level"] = "high"
            elif len(detections) > 3:
                state["privacy"]["risk_level"] = "medium"
            else:
                state["privacy"]["risk_level"] = "low"
            
            # Replace message with sanitized version
            state["messages"][-1] = HumanMessage(content=sanitized_content)
            
            logger.info(
                f"Message sanitized: {len(detections)} PII, "
                f"risk={state['privacy']['risk_level']}"
            )
        else:
            state["privacy"]["pii_detected"] = False
        
        return state
    
    def invoke(self, state: AgentState) -> AgentState:
        """Process audit/system requests."""
        # If it's an audit request, respond with system status
        state = super().invoke(state)
        return state
    
    def get_system_status(self) -> dict:
        """Get status of all system services.
        
        Returns:
            Dict with each service status
        """
        status = {
            "services": {},
            "storage": {},
            "external_apis": {},
            "privacy_stats": {},
        }
        
        # Check Ollama
        try:
            from src.services.llm_factory import get_factory
            factory = get_factory()
            status["services"]["ollama"] = {
                "status": "ok" if factory.ollama_available else "error",
                "model": "llama3.2:3b",
            }
        except Exception as e:
            status["services"]["ollama"] = {"status": "error", "error": str(e)}
        
        # Check ChromaDB
        try:
            from src.services.vector_store import get_vector_store
            store = get_vector_store()
            stats = store.get_collection_stats()
            total_vectors = sum(v for v in stats.values() if v > 0)
            status["storage"]["chromadb"] = {
                "status": "ok",
                "collections": stats,
                "total_vectors": total_vectors,
            }
        except Exception as e:
            status["storage"]["chromadb"] = {"status": "error", "error": str(e)}
        
        return status
    
    def format_status_report(self, status: dict) -> str:
        """Format status report for user display.
        
        Args:
            status: System status dict
            
        Returns:
            Formatted string
        """
        output = "🛡️ **System Status Report**\n\n"
        
        # Core services
        output += "**Core Services**:\n"
        for service, info in status.get("services", {}).items():
            emoji = "✅" if info.get("status") == "ok" else "❌"
            output += f"• {service}: {emoji}\n"
        
        # Storage
        output += "\n**Storage**:\n"
        for store, info in status.get("storage", {}).items():
            emoji = "✅" if info.get("status") == "ok" else "❌"
            if info.get("total_vectors"):
                output += f"• {store}: {emoji} ({info['total_vectors']} vectors)\n"
            else:
                output += f"• {store}: {emoji}\n"
        
        return output


def create_sentinel_agent(
    llm: BaseChatModel,
    tools: list[BaseTool] | None = None,
) -> SentinelAgent:
    """Factory function to create SentinelAgent.
    
    Args:
        llm: LOCAL language model
        tools: Additional tools (optional)
        
    Returns:
        Configured SentinelAgent instance
    """
    return SentinelAgent(llm=llm, tools=tools or [])
