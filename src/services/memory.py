"""Memory Service - Servicio de memoria a largo plazo para SPESION."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class MemoryService:
    """Servicio de memoria que integra ChromaDB con contexto de conversación.
    
    Proporciona una API de alto nivel para:
    - Guardar y recuperar memorias
    - Journaling y análisis de sentimiento
    - Búsqueda semántica de contexto
    """
    
    def __init__(self) -> None:
        """Inicializa el servicio de memoria."""
        from .vector_store import get_vector_store
        self.store = get_vector_store()
    
    def save_journal_entry(
        self,
        content: str,
        mood_score: float | None = None,
        themes: list[str] | None = None,
        user_id: str = "default",
    ) -> str:
        """Guarda una entrada de diario.
        
        Args:
            content: Contenido de la entrada
            mood_score: Puntuación de ánimo (-1 a 1)
            themes: Temas detectados
            user_id: ID del usuario
            
        Returns:
            ID de la entrada creada
        """
        metadata = {
            "type": "journal",
            "user_id": user_id,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "timestamp": datetime.now().isoformat(),
        }
        
        if mood_score is not None:
            metadata["mood_score"] = mood_score
        
        if themes:
            metadata["themes"] = ", ".join(themes)
        
        doc_id = self.store.add_memory(
            content=content,
            memory_type="journal",
            metadata=metadata,
        )
        
        logger.info(f"Journal entry guardada: {doc_id}")
        return doc_id
    
    def save_insight(
        self,
        content: str,
        source: str = "conversation",
        importance: int = 5,
        user_id: str = "default",
    ) -> str:
        """Guarda un insight o aprendizaje importante.
        
        Args:
            content: Contenido del insight
            source: Origen del insight
            importance: Importancia (1-10)
            user_id: ID del usuario
            
        Returns:
            ID del insight creado
        """
        metadata = {
            "type": "insight",
            "source": source,
            "importance": importance,
            "user_id": user_id,
            "timestamp": datetime.now().isoformat(),
        }
        
        doc_id = self.store.add_memory(
            content=content,
            memory_type="insight",
            metadata=metadata,
        )
        
        logger.info(f"Insight guardado: {doc_id}")
        return doc_id
    
    def save_event(
        self,
        description: str,
        event_type: str,
        participants: list[str] | None = None,
        location: str | None = None,
        user_id: str = "default",
    ) -> str:
        """Guarda un evento o momento importante.
        
        Args:
            description: Descripción del evento
            event_type: Tipo de evento
            participants: Personas involucradas
            location: Ubicación
            user_id: ID del usuario
            
        Returns:
            ID del evento creado
        """
        metadata = {
            "type": "event",
            "event_type": event_type,
            "user_id": user_id,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "timestamp": datetime.now().isoformat(),
        }
        
        if participants:
            metadata["participants"] = ", ".join(participants)
        
        if location:
            metadata["location"] = location
        
        doc_id = self.store.add_memory(
            content=description,
            memory_type="event",
            metadata=metadata,
        )
        
        logger.info(f"Evento guardado: {doc_id}")
        return doc_id
    
    def search_memories(
        self,
        query: str,
        memory_types: list[str] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        n_results: int = 5,
    ) -> list[dict[str, Any]]:
        """Busca memorias relevantes.
        
        Args:
            query: Texto de búsqueda
            memory_types: Filtrar por tipos (journal, insight, event)
            date_from: Fecha inicial (YYYY-MM-DD)
            date_to: Fecha final (YYYY-MM-DD)
            n_results: Número de resultados
            
        Returns:
            Lista de memorias con contenido y metadatos
        """
        # Construir filtro where
        where_filter = None
        if memory_types:
            if len(memory_types) == 1:
                where_filter = {"type": memory_types[0]}
            else:
                where_filter = {"type": {"$in": memory_types}}
        
        results = self.store.query(
            collection_name="memories",
            query_text=query,
            n_results=n_results,
            where=where_filter,
            include_distances=True,
        )
        
        memories = []
        for doc, meta, dist in zip(
            results["documents"],
            results["metadatas"],
            results["distances"],
        ):
            # Filtrar por fecha si se especifica
            if date_from or date_to:
                doc_date = meta.get("date", "")
                if date_from and doc_date < date_from:
                    continue
                if date_to and doc_date > date_to:
                    continue
            
            memories.append({
                "content": doc,
                "metadata": meta,
                "relevance": 1 - (dist / 2),  # Convertir distancia a relevancia
            })
        
        return memories
    
    def get_recent_journals(
        self,
        days: int = 7,
        n_results: int = 10,
    ) -> list[dict[str, Any]]:
        """Obtiene las entradas de journal más recientes.
        
        Args:
            days: Número de días hacia atrás
            n_results: Número máximo de resultados
            
        Returns:
            Lista de entradas de journal
        """
        from datetime import timedelta
        
        date_from = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        # Buscar con query genérico para obtener todos
        results = self.store.query(
            collection_name="memories",
            query_text="journal entry reflexión día",
            n_results=n_results * 2,  # Pedir más para filtrar
            where={"type": "journal"},
            include_distances=False,
        )
        
        journals = []
        for doc, meta in zip(results["documents"], results["metadatas"]):
            if meta.get("date", "") >= date_from:
                journals.append({
                    "content": doc,
                    "metadata": meta,
                })
        
        # Ordenar por fecha descendente
        journals.sort(
            key=lambda x: x["metadata"].get("timestamp", ""),
            reverse=True,
        )
        
        return journals[:n_results]
    
    def analyze_mood_trends(
        self,
        days: int = 30,
    ) -> dict[str, Any]:
        """Analiza tendencias de ánimo basadas en journals.
        
        Args:
            days: Número de días a analizar
            
        Returns:
            Diccionario con análisis de tendencias
        """
        journals = self.get_recent_journals(days=days, n_results=100)
        
        if not journals:
            return {
                "average_mood": None,
                "trend": "unknown",
                "common_themes": [],
                "entries_count": 0,
            }
        
        mood_scores = []
        all_themes = []
        
        for journal in journals:
            meta = journal["metadata"]
            if "mood_score" in meta:
                try:
                    mood_scores.append(float(meta["mood_score"]))
                except (ValueError, TypeError):
                    pass
            
            if "themes" in meta:
                themes = meta["themes"].split(", ")
                all_themes.extend(themes)
        
        # Calcular promedio
        avg_mood = sum(mood_scores) / len(mood_scores) if mood_scores else None
        
        # Determinar tendencia (comparar primera mitad vs segunda mitad)
        trend = "stable"
        if len(mood_scores) >= 4:
            mid = len(mood_scores) // 2
            first_half_avg = sum(mood_scores[:mid]) / mid
            second_half_avg = sum(mood_scores[mid:]) / (len(mood_scores) - mid)
            
            diff = second_half_avg - first_half_avg
            if diff > 0.2:
                trend = "improving"
            elif diff < -0.2:
                trend = "declining"
        
        # Contar temas más comunes
        from collections import Counter
        theme_counts = Counter(all_themes)
        common_themes = [theme for theme, _ in theme_counts.most_common(5)]
        
        return {
            "average_mood": avg_mood,
            "trend": trend,
            "common_themes": common_themes,
            "entries_count": len(journals),
            "mood_samples": len(mood_scores),
        }
    
    def get_context_for_agent(
        self,
        agent_name: str,
        query: str,
        n_results: int = 3,
    ) -> list[str]:
        """Obtiene contexto relevante para un agente específico.
        
        Args:
            agent_name: Nombre del agente
            query: Query de búsqueda
            n_results: Número de resultados
            
        Returns:
            Lista de textos de contexto
        """
        # Mapeo de agentes a colecciones relevantes
        agent_collections = {
            "companion": ["memories"],
            "scholar": ["papers", "knowledge"],
            "techlead": ["knowledge", "conversations"],
            "tycoon": ["knowledge"],
            "coach": ["memories"],
            "executive": ["knowledge", "conversations"],
            "connector": ["knowledge", "conversations"],
            "sentinel": ["conversations"],
        }
        
        collections = agent_collections.get(agent_name, list(self.store.COLLECTIONS.keys()))
        
        return self.store.retrieve_context(
            query=query,
            collections=collections,
            n_results=n_results,
        )


# Singleton
_memory_service: MemoryService | None = None


def get_memory_service() -> MemoryService:
    """Obtiene la instancia singleton del MemoryService."""
    global _memory_service
    if _memory_service is None:
        _memory_service = MemoryService()
    return _memory_service

