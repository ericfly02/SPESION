"""Search Tool - Búsqueda web con Tavily o DuckDuckGo."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
def web_search(
    query: str,
    max_results: int = 5,
    search_type: str = "general",
) -> list[dict[str, Any]]:
    """Realiza una búsqueda web.
    
    Args:
        query: Términos de búsqueda
        max_results: Número máximo de resultados
        search_type: Tipo de búsqueda ('general', 'news', 'tech')
        
    Returns:
        Lista de resultados con título, url y snippet
    """
    from src.core.config import settings
    
    # Intentar Tavily primero si está configurado
    if settings.search.tavily_api_key:
        return _search_tavily(query, max_results, search_type)
    
    # Fallback a DuckDuckGo
    return _search_duckduckgo(query, max_results)


def _search_tavily(
    query: str,
    max_results: int,
    search_type: str,
) -> list[dict[str, Any]]:
    """Búsqueda usando Tavily API."""
    try:
        from tavily import TavilyClient
        from src.core.config import settings
        
        client = TavilyClient(
            api_key=settings.search.tavily_api_key.get_secret_value()
        )
        
        # Mapear tipo de búsqueda
        topic = "general"
        if search_type == "news":
            topic = "news"
        
        response = client.search(
            query=query,
            search_depth="advanced",
            topic=topic,
            max_results=max_results,
        )
        
        results = []
        for item in response.get("results", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("content", "")[:300],
                "score": item.get("score", 0),
            })
        
        logger.info(f"Tavily: {len(results)} resultados para '{query}'")
        return results
        
    except ImportError:
        logger.warning("Tavily no instalado, usando DuckDuckGo")
        return _search_duckduckgo(query, max_results)
    except Exception as e:
        logger.error(f"Error en Tavily: {e}")
        return _search_duckduckgo(query, max_results)


def _search_duckduckgo(
    query: str,
    max_results: int,
) -> list[dict[str, Any]]:
    """Búsqueda usando DuckDuckGo (sin API key)."""
    try:
        from duckduckgo_search import DDGS
        
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", "")[:300],
                })
        
        logger.info(f"DuckDuckGo: {len(results)} resultados para '{query}'")
        return results
        
    except ImportError:
        logger.error("duckduckgo-search no instalado")
        return [{"error": "duckduckgo-search no instalado"}]
    except Exception as e:
        logger.error(f"Error en DuckDuckGo: {e}")
        return [{"error": str(e)}]


@tool
def search_news(
    query: str,
    max_results: int = 5,
    region: str = "es-es",
) -> list[dict[str, Any]]:
    """Busca noticias recientes.
    
    Args:
        query: Términos de búsqueda
        max_results: Número máximo de resultados
        region: Región de noticias (default 'es-es')
        
    Returns:
        Lista de noticias
    """
    try:
        from duckduckgo_search import DDGS
        
        results = []
        with DDGS() as ddgs:
            for r in ddgs.news(query, max_results=max_results, region=region):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("body", "")[:200],
                    "date": r.get("date", ""),
                    "source": r.get("source", ""),
                })
        
        logger.info(f"Noticias: {len(results)} resultados para '{query}'")
        return results
        
    except Exception as e:
        logger.error(f"Error buscando noticias: {e}")
        return [{"error": str(e)}]


def create_search_tools() -> list:
    """Crea las herramientas de búsqueda web.
    
    Returns:
        Lista de herramientas
    """
    return [
        web_search,
        search_news,
    ]

