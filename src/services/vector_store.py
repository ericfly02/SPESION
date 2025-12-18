"""Vector Store - ChromaDB manager para RAG."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


class VectorStore:
    """Manager de ChromaDB para almacenamiento de vectores y RAG.
    
    Gestiona múltiples colecciones:
    - memories: Memorias a largo plazo del Companion
    - papers: Resúmenes de papers de ArXiv
    - knowledge: Notas y conocimiento general
    - conversations: Historial de conversaciones relevantes
    """
    
    COLLECTIONS = {
        "memories": "Memorias personales y journals del usuario",
        "papers": "Resúmenes de papers académicos",
        "knowledge": "Notas y conocimiento general",
        "conversations": "Conversaciones relevantes archivadas",
    }
    
    def __init__(
        self,
        persist_directory: str | Path | None = None,
        embedding_model: str = "all-MiniLM-L6-v2",
    ) -> None:
        """Inicializa el VectorStore.
        
        Args:
            persist_directory: Directorio de persistencia
            embedding_model: Modelo de embeddings a usar
        """
        from src.core.config import settings
        
        self.persist_directory = Path(
            persist_directory or settings.storage.chroma_persist_dir
        )
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        
        self.embedding_model = embedding_model
        self._client: chromadb.ClientAPI | None = None
        self._embedding_function: Any = None
        self._collections: dict[str, chromadb.Collection] = {}
    
    @property
    def client(self) -> chromadb.ClientAPI:
        """Cliente de ChromaDB (lazy initialization)."""
        if self._client is None:
            self._client = chromadb.PersistentClient(
                path=str(self.persist_directory),
                settings=ChromaSettings(
                    anonymized_telemetry=False,
                    allow_reset=True,
                ),
            )
            logger.info(f"ChromaDB inicializado en {self.persist_directory}")
        return self._client
    
    @property
    def embedding_function(self) -> Any:
        """Función de embedding (lazy initialization)."""
        if self._embedding_function is None:
            from chromadb.utils import embedding_functions
            
            self._embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=self.embedding_model
            )
            logger.info(f"Embedding function inicializada: {self.embedding_model}")
        return self._embedding_function
    
    def get_collection(self, name: str) -> chromadb.Collection:
        """Obtiene o crea una colección.
        
        Args:
            name: Nombre de la colección
            
        Returns:
            Colección de ChromaDB
        """
        if name not in self._collections:
            if name not in self.COLLECTIONS:
                logger.warning(f"Colección '{name}' no está predefinida")
            
            self._collections[name] = self.client.get_or_create_collection(
                name=name,
                embedding_function=self.embedding_function,
                metadata={"description": self.COLLECTIONS.get(name, "")},
            )
            logger.debug(f"Colección '{name}' obtenida/creada")
        
        return self._collections[name]
    
    def add_documents(
        self,
        collection_name: str,
        documents: list[str],
        metadatas: list[dict[str, Any]] | None = None,
        ids: list[str] | None = None,
    ) -> list[str]:
        """Añade documentos a una colección.
        
        Args:
            collection_name: Nombre de la colección
            documents: Lista de textos a añadir
            metadatas: Metadatos opcionales por documento
            ids: IDs opcionales (se generan si no se proporcionan)
            
        Returns:
            Lista de IDs de los documentos añadidos
        """
        import uuid
        from datetime import datetime
        
        collection = self.get_collection(collection_name)
        
        # Generar IDs si no se proporcionan
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in documents]
        
        # Añadir timestamp a metadatos
        if metadatas is None:
            metadatas = [{} for _ in documents]
        
        for meta in metadatas:
            if "created_at" not in meta:
                meta["created_at"] = datetime.now().isoformat()
        
        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids,
        )
        
        logger.info(f"Añadidos {len(documents)} documentos a '{collection_name}'")
        return ids
    
    def query(
        self,
        collection_name: str,
        query_text: str,
        n_results: int = 5,
        where: dict[str, Any] | None = None,
        include_distances: bool = True,
    ) -> dict[str, Any]:
        """Busca documentos similares en una colección.
        
        Args:
            collection_name: Nombre de la colección
            query_text: Texto de búsqueda
            n_results: Número de resultados a retornar
            where: Filtros opcionales de metadatos
            include_distances: Si incluir distancias en resultados
            
        Returns:
            Diccionario con documentos, metadatos y distancias
        """
        collection = self.get_collection(collection_name)
        
        include = ["documents", "metadatas"]
        if include_distances:
            include.append("distances")
        
        results = collection.query(
            query_texts=[query_text],
            n_results=n_results,
            where=where,
            include=include,
        )
        
        logger.debug(
            f"Query en '{collection_name}': '{query_text[:50]}...' "
            f"→ {len(results['documents'][0])} resultados"
        )
        
        return {
            "documents": results["documents"][0] if results["documents"] else [],
            "metadatas": results["metadatas"][0] if results["metadatas"] else [],
            "distances": results.get("distances", [[]])[0] if include_distances else [],
        }
    
    def retrieve_context(
        self,
        query: str,
        collections: list[str] | None = None,
        n_results: int = 5,
        max_distance: float = 1.5,
    ) -> list[str]:
        """Recupera contexto relevante para RAG.
        
        Esta es la función principal para RAG. Busca en múltiples colecciones
        y retorna los documentos más relevantes.
        
        Args:
            query: Pregunta o texto de búsqueda
            collections: Colecciones a buscar (default: todas)
            n_results: Número de resultados por colección
            max_distance: Distancia máxima para considerar relevante
            
        Returns:
            Lista de textos relevantes ordenados por relevancia
        """
        if collections is None:
            collections = list(self.COLLECTIONS.keys())
        
        all_results: list[tuple[str, float, dict]] = []
        
        for coll_name in collections:
            try:
                results = self.query(
                    collection_name=coll_name,
                    query_text=query,
                    n_results=n_results,
                    include_distances=True,
                )
                
                for doc, meta, dist in zip(
                    results["documents"],
                    results["metadatas"],
                    results["distances"],
                ):
                    if dist <= max_distance:
                        all_results.append((doc, dist, meta))
                        
            except Exception as e:
                logger.warning(f"Error buscando en '{coll_name}': {e}")
                continue
        
        # Ordenar por distancia (menor = más relevante)
        all_results.sort(key=lambda x: x[1])
        
        # Retornar solo los textos, limitados
        context = [doc for doc, _, _ in all_results[:n_results]]
        
        logger.info(
            f"retrieve_context: '{query[:30]}...' → {len(context)} docs relevantes"
        )
        
        return context
    
    def add_memory(
        self,
        content: str,
        memory_type: str = "general",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Añade una memoria a la colección de memorias.
        
        Args:
            content: Contenido de la memoria
            memory_type: Tipo de memoria (journal, insight, event, etc.)
            metadata: Metadatos adicionales
            
        Returns:
            ID de la memoria creada
        """
        meta = metadata or {}
        meta["type"] = memory_type
        
        ids = self.add_documents(
            collection_name="memories",
            documents=[content],
            metadatas=[meta],
        )
        
        return ids[0]
    
    def add_paper_summary(
        self,
        title: str,
        summary: str,
        arxiv_id: str | None = None,
        authors: list[str] | None = None,
        categories: list[str] | None = None,
    ) -> str:
        """Añade un resumen de paper a la colección.
        
        Args:
            title: Título del paper
            summary: Resumen generado
            arxiv_id: ID de ArXiv
            authors: Lista de autores
            categories: Categorías del paper
            
        Returns:
            ID del documento creado
        """
        content = f"# {title}\n\n{summary}"
        
        metadata = {
            "title": title,
            "arxiv_id": arxiv_id or "",
            "authors": ", ".join(authors) if authors else "",
            "categories": ", ".join(categories) if categories else "",
        }
        
        ids = self.add_documents(
            collection_name="papers",
            documents=[content],
            metadatas=[metadata],
        )
        
        return ids[0]
    
    def get_collection_stats(self) -> dict[str, int]:
        """Obtiene estadísticas de todas las colecciones.
        
        Returns:
            Diccionario con nombre de colección y número de documentos
        """
        stats = {}
        for name in self.COLLECTIONS:
            try:
                collection = self.get_collection(name)
                stats[name] = collection.count()
            except Exception as e:
                logger.warning(f"Error obteniendo stats de '{name}': {e}")
                stats[name] = -1
        return stats
    
    def delete_collection(self, name: str) -> None:
        """Elimina una colección.
        
        Args:
            name: Nombre de la colección a eliminar
        """
        self.client.delete_collection(name)
        if name in self._collections:
            del self._collections[name]
        logger.info(f"Colección '{name}' eliminada")
    
    def reset(self) -> None:
        """Elimina todas las colecciones y reinicia el store."""
        self.client.reset()
        self._collections = {}
        logger.warning("VectorStore reseteado completamente")


# Singleton para uso global
_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    """Obtiene la instancia singleton del VectorStore."""
    global _store
    if _store is None:
        _store = VectorStore()
    return _store


def retrieve_context(
    query: str,
    collections: list[str] | None = None,
    n_results: int = 5,
) -> list[str]:
    """Función de conveniencia para recuperar contexto RAG.
    
    Args:
        query: Texto de búsqueda
        collections: Colecciones a buscar
        n_results: Número de resultados
        
    Returns:
        Lista de textos relevantes
    """
    return get_vector_store().retrieve_context(
        query=query,
        collections=collections,
        n_results=n_results,
    )

