"""RAG Service - Servicio de memoria y recuperación holística."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

from src.core.config import settings

logger = logging.getLogger(__name__)


class RAGService:
    """Servicio de RAG para SPESION."""

    def __init__(self) -> None:
        """Inicializa el servicio RAG."""
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        self.vector_store = Chroma(
            collection_name="spesion_memory",
            embedding_function=self.embeddings,
            persist_directory=str(settings.storage.chroma_persist_dir),
        )

    def add_memory(self, content: str, metadata: dict[str, Any] | None = None) -> None:
        """Añade un recuerdo a la memoria a largo plazo."""
        try:
            doc = Document(
                page_content=content,
                metadata=metadata or {"source": "user_interaction"},
            )
            self.vector_store.add_documents([doc])
            logger.info("Memoria añadida exitosamente")
        except Exception as e:
            logger.error(f"Error añadiendo memoria: {e}")

    def retrieve_context(self, query: str, k: int = 3) -> list[str]:
        """Recupera contexto relevante para una query."""
        try:
            docs = self.vector_store.similarity_search(query, k=k)
            return [doc.page_content for doc in docs]
        except Exception as e:
            logger.error(f"Error recuperando contexto: {e}")
            return []


# Singleton
_rag_service: RAGService | None = None


def get_rag_service() -> RAGService:
    """Obtiene la instancia del servicio RAG."""
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service

