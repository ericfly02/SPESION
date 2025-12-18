"""ArXiv Tool - Búsqueda y resumen de papers académicos."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
def search_arxiv(
    query: str,
    max_results: int = 5,
    categories: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Busca papers en ArXiv.
    
    Args:
        query: Términos de búsqueda
        max_results: Número máximo de resultados (default 5)
        categories: Categorías de ArXiv a filtrar (e.g., ['cs.AI', 'cs.LG'])
        
    Returns:
        Lista de papers con título, autores, resumen y link
    """
    try:
        import arxiv
        
        # Construir query con categorías
        search_query = query
        if categories:
            cat_filter = " OR ".join([f"cat:{cat}" for cat in categories])
            search_query = f"({query}) AND ({cat_filter})"
        
        logger.info(f"Buscando en ArXiv: {search_query}")
        
        search = arxiv.Search(
            query=search_query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
        )
        
        results = []
        for paper in search.results():
            results.append({
                "title": paper.title,
                "authors": [a.name for a in paper.authors[:5]],  # Limitar autores
                "summary": paper.summary[:500] + "..." if len(paper.summary) > 500 else paper.summary,
                "published": paper.published.strftime("%Y-%m-%d"),
                "arxiv_id": paper.entry_id.split("/")[-1],
                "pdf_url": paper.pdf_url,
                "categories": paper.categories,
            })
        
        logger.info(f"Encontrados {len(results)} papers")
        return results
        
    except ImportError:
        logger.error("Módulo arxiv no instalado. pip install arxiv")
        return [{"error": "Módulo arxiv no instalado"}]
    except Exception as e:
        logger.error(f"Error buscando en ArXiv: {e}")
        return [{"error": str(e)}]


@tool
def get_arxiv_paper(arxiv_id: str) -> dict[str, Any]:
    """Obtiene detalles completos de un paper de ArXiv.
    
    Args:
        arxiv_id: ID del paper (e.g., '2301.00001')
        
    Returns:
        Diccionario con detalles del paper
    """
    try:
        import arxiv
        
        search = arxiv.Search(id_list=[arxiv_id])
        paper = next(search.results())
        
        return {
            "title": paper.title,
            "authors": [a.name for a in paper.authors],
            "summary": paper.summary,
            "published": paper.published.strftime("%Y-%m-%d"),
            "updated": paper.updated.strftime("%Y-%m-%d"),
            "arxiv_id": arxiv_id,
            "pdf_url": paper.pdf_url,
            "categories": paper.categories,
            "primary_category": paper.primary_category,
            "comment": paper.comment,
            "doi": paper.doi,
        }
        
    except StopIteration:
        return {"error": f"Paper {arxiv_id} no encontrado"}
    except Exception as e:
        logger.error(f"Error obteniendo paper {arxiv_id}: {e}")
        return {"error": str(e)}


@tool
def get_recent_papers(
    category: str = "cs.AI",
    days: int = 7,
    max_results: int = 10,
) -> list[dict[str, Any]]:
    """Obtiene papers recientes de una categoría.
    
    Args:
        category: Categoría de ArXiv (default 'cs.AI')
        days: Papers de los últimos N días
        max_results: Número máximo de resultados
        
    Returns:
        Lista de papers recientes
    """
    try:
        import arxiv
        from datetime import datetime, timedelta
        
        # ArXiv no soporta búsqueda por fecha directamente,
        # así que buscamos por categoría y filtramos
        search = arxiv.Search(
            query=f"cat:{category}",
            max_results=max_results * 3,  # Pedir más para filtrar
            sort_by=arxiv.SortCriterion.SubmittedDate,
        )
        
        cutoff_date = datetime.now() - timedelta(days=days)
        results = []
        
        for paper in search.results():
            # Hacer timezone-naive para comparación
            paper_date = paper.published.replace(tzinfo=None)
            if paper_date >= cutoff_date:
                results.append({
                    "title": paper.title,
                    "authors": [a.name for a in paper.authors[:3]],
                    "published": paper.published.strftime("%Y-%m-%d"),
                    "arxiv_id": paper.entry_id.split("/")[-1],
                    "summary": paper.summary[:300] + "...",
                })
            
            if len(results) >= max_results:
                break
        
        return results
        
    except Exception as e:
        logger.error(f"Error obteniendo papers recientes: {e}")
        return [{"error": str(e)}]


def create_arxiv_tools() -> list:
    """Crea las herramientas de ArXiv.
    
    Returns:
        Lista de herramientas
    """
    return [
        search_arxiv,
        get_arxiv_paper,
        get_recent_papers,
    ]

