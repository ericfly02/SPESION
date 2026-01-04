"""Memory Tools - Herramientas para memoria a largo plazo explícita."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import tool

from src.services.rag_service import get_rag_service

logger = logging.getLogger(__name__)


@tool
def save_important_memory(content: str, category: str = "general", tags: list[str] | None = None) -> str:
    """Guarda un recuerdo importante o dato personal en la memoria a largo plazo.
    
    Usa esto cuando el usuario te dé información personal explícita (e.g., "Mi VO2 max es 55",
    "Tengo una lesión en la rodilla", "Mi objetivo de ahorro es 10k").
    
    Args:
        content: El contenido exacto a recordar.
        category: Categoría (e.g., "health", "finance", "preferences", "personal").
        tags: Etiquetas opcionales para facilitar la búsqueda.
        
    Returns:
        Mensaje de confirmación.
    """
    try:
        rag = get_rag_service()
        metadata = {
            "type": "fact",
            "category": category,
            "priority": "high",
            "tags": ",".join(tags) if tags else ""
        }
        rag.add_memory(content, metadata=metadata)
        return f"✅ Guardado en memoria: '{content}' (Categoría: {category})"
    except Exception as e:
        logger.error(f"Error guardando memoria: {e}")
        return f"Error guardando memoria: {e}"


@tool
def search_memory(query: str, limit: int = 5) -> list[str]:
    """Busca en la memoria a largo plazo.
    
    Args:
        query: Pregunta o términos de búsqueda.
        limit: Número de resultados.
        
    Returns:
        Lista de recuerdos relevantes.
    """
    try:
        rag = get_rag_service()
        return rag.retrieve_context(query, k=limit)
    except Exception as e:
        logger.error(f"Error buscando memoria: {e}")
        return []

def create_memory_tools() -> list:
    """Crea la lista de herramientas de memoria."""
    return [save_important_memory, search_memory]

