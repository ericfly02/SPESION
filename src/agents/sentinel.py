"""Sentinel Agent - DevOps, Seguridad y Privacidad."""

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
    """Agente Sentinel - Guardián del sistema y protector de privacidad.
    
    Responsabilidades:
    - Detectar y sanitizar PII antes de enviar a LLMs cloud
    - Monitorizar estado de servicios y MCPs
    - Auditar logs y detectar anomalías
    - Gestionar backups y recuperación
    
    IMPORTANTE: Este agente procesa TODOS los mensajes antes
    de ser enviados a otros agentes cuando privacy_mode está activo.
    """
    
    # Patrones de PII a detectar
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
    
    # Labels para redacción
    PII_LABELS = {
        "credit_card": "[TARJETA_REDACTED]",
        "nie_dni": "[NIE_DNI_REDACTED]",
        "phone_spain": "[TELEFONO_REDACTED]",
        "email": "[EMAIL_REDACTED]",
        "iban": "[IBAN_REDACTED]",
        "passport": "[PASAPORTE_REDACTED]",
        "address": "[DIRECCION_REDACTED]",
        "api_key": "[API_KEY_REDACTED]",
        "password": "[PASSWORD_REDACTED]",
    }
    
    @property
    def name(self) -> str:
        return "sentinel"
    
    @property
    def description(self) -> str:
        return "Guardián de privacidad, monitorización de sistema y auditoría"
    
    def _default_system_prompt(self) -> str:
        return get_agent_prompt("sentinel")
    
    def sanitize_text(self, text: str) -> tuple[str, list[dict]]:
        """Detecta y redacta PII en un texto.
        
        Args:
            text: Texto a sanitizar
            
        Returns:
            Tuple de (texto sanitizado, lista de detecciones)
        """
        sanitized = text
        detections = []
        
        for pii_type, pattern in self.PII_PATTERNS.items():
            matches = re.finditer(pattern, sanitized, re.IGNORECASE)
            for match in matches:
                detections.append({
                    "type": pii_type,
                    "original": match.group()[:10] + "...",  # Truncar para log
                    "position": match.span(),
                })
                sanitized = sanitized.replace(
                    match.group(),
                    self.PII_LABELS[pii_type],
                )
        
        if detections:
            logger.warning(
                f"PII detectado y sanitizado: {len(detections)} instancias"
            )
        
        return sanitized, detections
    
    def process_incoming(self, state: AgentState) -> AgentState:
        """Procesa un mensaje entrante para detectar PII.
        
        Este método debe ser llamado ANTES del supervisor
        para todos los mensajes nuevos.
        
        Args:
            state: Estado actual
            
        Returns:
            Estado con privacy_mode actualizado si se detecta PII
        """
        if not state.get("messages"):
            return state
        
        last_message = state["messages"][-1]
        if not isinstance(last_message, HumanMessage):
            return state
        
        # Sanitizar mensaje
        original_content = last_message.content
        sanitized_content, detections = self.sanitize_text(original_content)
        
        if detections:
            # Actualizar estado de privacidad
            state["privacy"]["pii_detected"] = True
            state["privacy"]["sanitized_content"] = sanitized_content
            state["privacy"]["use_local_llm"] = True
            
            # Determinar nivel de riesgo
            high_risk_types = {"credit_card", "password", "api_key", "iban"}
            detected_types = {d["type"] for d in detections}
            
            if detected_types & high_risk_types:
                state["privacy"]["risk_level"] = "high"
            elif len(detections) > 3:
                state["privacy"]["risk_level"] = "medium"
            else:
                state["privacy"]["risk_level"] = "low"
            
            # Reemplazar mensaje con versión sanitizada
            state["messages"][-1] = HumanMessage(content=sanitized_content)
            
            logger.info(
                f"Mensaje sanitizado: {len(detections)} PII, "
                f"risk={state['privacy']['risk_level']}"
            )
        else:
            state["privacy"]["pii_detected"] = False
        
        return state
    
    def invoke(self, state: AgentState) -> AgentState:
        """Procesa solicitudes de auditoría/sistema."""
        # Si es una solicitud de auditoría, responder con estado del sistema
        state = super().invoke(state)
        return state
    
    def get_system_status(self) -> dict:
        """Obtiene el estado de todos los servicios del sistema.
        
        Returns:
            Dict con estado de cada servicio
        """
        status = {
            "services": {},
            "storage": {},
            "external_apis": {},
            "privacy_stats": {},
        }
        
        # Verificar Ollama
        try:
            from src.services.llm_factory import get_factory
            factory = get_factory()
            status["services"]["ollama"] = {
                "status": "ok" if factory.ollama_available else "error",
                "model": "phi3:mini",
            }
        except Exception as e:
            status["services"]["ollama"] = {"status": "error", "error": str(e)}
        
        # Verificar ChromaDB
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
        """Formatea el reporte de estado para mostrar al usuario.
        
        Args:
            status: Dict de estado del sistema
            
        Returns:
            String formateado
        """
        output = "🛡️ **System Status Report**\n\n"
        
        # Servicios core
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
    """Factory function para crear el SentinelAgent.
    
    Args:
        llm: Modelo de lenguaje LOCAL
        tools: Herramientas adicionales (opcional)
        
    Returns:
        Instancia configurada del SentinelAgent
    """
    return SentinelAgent(llm=llm, tools=tools or [])

