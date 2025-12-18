"""LLM Factory - Selector híbrido entre Ollama (local) y Cloud (OpenAI/Anthropic)."""

from __future__ import annotations

import logging
from enum import Enum
from functools import lru_cache
from typing import Literal

from langchain_core.language_models import BaseChatModel

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    """Proveedores de LLM disponibles."""
    
    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class TaskType(str, Enum):
    """Tipos de tarea que determinan qué LLM usar."""
    
    # Tareas que requieren privacidad → Local
    JOURNAL = "journal"
    EMOTIONAL = "emotional"
    HEALTH = "health"
    PRIVATE = "private"
    
    # Tareas que pueden ir a cloud → Cloud
    RESEARCH = "research"
    CODING = "coding"
    ANALYSIS = "analysis"
    GENERAL = "general"


# Mapeo de tipos de tarea a preferencia de proveedor
TASK_TO_PROVIDER: dict[TaskType, LLMProvider] = {
    TaskType.JOURNAL: LLMProvider.OLLAMA,
    TaskType.EMOTIONAL: LLMProvider.OLLAMA,
    TaskType.HEALTH: LLMProvider.OLLAMA,
    TaskType.PRIVATE: LLMProvider.OLLAMA,
    TaskType.RESEARCH: LLMProvider.OPENAI,
    TaskType.CODING: LLMProvider.OPENAI,
    TaskType.ANALYSIS: LLMProvider.OPENAI,
    TaskType.GENERAL: LLMProvider.OLLAMA,  # Default a local para eficiencia
}


class LLMFactory:
    """Factory para crear instancias de LLM según el contexto."""
    
    def __init__(self) -> None:
        """Inicializa el factory con la configuración."""
        from src.core.config import settings
        self.settings = settings
        self._ollama_available: bool | None = None
        self._openai_available: bool | None = None
        self._anthropic_available: bool | None = None
    
    @property
    def ollama_available(self) -> bool:
        """Verifica si Ollama está disponible."""
        if self._ollama_available is None:
            self._ollama_available = self._check_ollama()
        return self._ollama_available
    
    @property
    def openai_available(self) -> bool:
        """Verifica si OpenAI está configurado."""
        if self._openai_available is None:
            self._openai_available = (
                self.settings.llm.openai_api_key is not None
                and self.settings.llm.openai_api_key.get_secret_value() != ""
            )
        return self._openai_available
    
    @property
    def anthropic_available(self) -> bool:
        """Verifica si Anthropic está configurado."""
        if self._anthropic_available is None:
            self._anthropic_available = (
                self.settings.llm.anthropic_api_key is not None
                and self.settings.llm.anthropic_api_key.get_secret_value() != ""
            )
        return self._anthropic_available
    
    def _check_ollama(self) -> bool:
        """Verifica si Ollama está corriendo y accesible."""
        import httpx
        
        try:
            response = httpx.get(
                f"{self.settings.llm.ollama_base_url}/api/tags",
                timeout=5.0,
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Ollama no disponible: {e}")
            return False
    
    def get_ollama(
        self, 
        model: str | None = None,
        temperature: float = 0.7,
    ) -> BaseChatModel:
        """Crea una instancia de ChatOllama.
        
        Args:
            model: Nombre del modelo (default: phi3:mini)
            temperature: Temperatura de generación
            
        Returns:
            Instancia de ChatOllama
        """
        from langchain_ollama import ChatOllama
        
        model = model or self.settings.llm.ollama_model_light
        
        return ChatOllama(
            base_url=self.settings.llm.ollama_base_url,
            model=model,
            temperature=temperature,
        )
    
    def get_openai(
        self,
        model: str | None = None,
        temperature: float = 0.7,
    ) -> BaseChatModel:
        """Crea una instancia de ChatOpenAI.
        
        Args:
            model: Nombre del modelo (default: gpt-4o)
            temperature: Temperatura de generación
            
        Returns:
            Instancia de ChatOpenAI
        """
        from langchain_openai import ChatOpenAI
        
        if not self.openai_available:
            raise ValueError("OpenAI API key no configurada")
        
        model = model or self.settings.llm.openai_model
        
        return ChatOpenAI(
            api_key=self.settings.llm.openai_api_key.get_secret_value(),
            model=model,
            temperature=temperature,
        )
    
    def get_anthropic(
        self,
        model: str | None = None,
        temperature: float = 0.7,
    ) -> BaseChatModel:
        """Crea una instancia de ChatAnthropic.
        
        Args:
            model: Nombre del modelo (default: claude-3-5-sonnet)
            temperature: Temperatura de generación
            
        Returns:
            Instancia de ChatAnthropic
        """
        from langchain_anthropic import ChatAnthropic
        
        if not self.anthropic_available:
            raise ValueError("Anthropic API key no configurada")
        
        model = model or self.settings.llm.anthropic_model
        
        return ChatAnthropic(
            api_key=self.settings.llm.anthropic_api_key.get_secret_value(),
            model=model,
            temperature=temperature,
        )
    
    def get_cloud_llm(self, temperature: float = 0.7) -> BaseChatModel:
        """Obtiene el LLM cloud preferido según configuración.
        
        Args:
            temperature: Temperatura de generación
            
        Returns:
            Instancia del LLM cloud configurado
        """
        provider = self.settings.llm.cloud_provider
        
        if provider == "anthropic" and self.anthropic_available:
            return self.get_anthropic(temperature=temperature)
        elif self.openai_available:
            return self.get_openai(temperature=temperature)
        elif self.anthropic_available:
            return self.get_anthropic(temperature=temperature)
        else:
            raise ValueError("No hay LLM cloud disponible. Configura OPENAI_API_KEY o ANTHROPIC_API_KEY")
    
    def get_llm(
        self,
        task_type: TaskType | str = TaskType.GENERAL,
        privacy_required: bool = False,
        temperature: float = 0.7,
    ) -> BaseChatModel:
        """Obtiene el LLM apropiado según el tipo de tarea y requisitos de privacidad.
        
        Esta es la función principal que decide qué LLM usar basándose en:
        1. Si se requiere privacidad → Siempre local (Ollama)
        2. Tipo de tarea → Según mapeo TASK_TO_PROVIDER
        3. Disponibilidad → Fallback a lo que esté disponible
        
        Args:
            task_type: Tipo de tarea a realizar
            privacy_required: Si True, fuerza uso de LLM local
            temperature: Temperatura de generación
            
        Returns:
            Instancia del LLM apropiado
        """
        # Convertir string a enum si es necesario
        if isinstance(task_type, str):
            try:
                task_type = TaskType(task_type)
            except ValueError:
                task_type = TaskType.GENERAL
        
        # Determinar proveedor preferido
        if privacy_required:
            preferred_provider = LLMProvider.OLLAMA
        else:
            preferred_provider = TASK_TO_PROVIDER.get(task_type, LLMProvider.OLLAMA)
        
        logger.debug(
            f"Seleccionando LLM para task={task_type}, "
            f"privacy={privacy_required}, provider={preferred_provider}"
        )
        
        # Intentar obtener el LLM preferido
        try:
            if preferred_provider == LLMProvider.OLLAMA:
                if self.ollama_available:
                    return self.get_ollama(temperature=temperature)
                else:
                    logger.warning("Ollama no disponible, intentando cloud...")
                    if not privacy_required:
                        return self.get_cloud_llm(temperature=temperature)
                    raise ValueError("Se requiere privacidad pero Ollama no está disponible")
            
            elif preferred_provider in (LLMProvider.OPENAI, LLMProvider.ANTHROPIC):
                try:
                    return self.get_cloud_llm(temperature=temperature)
                except ValueError:
                    logger.warning("Cloud no disponible, usando Ollama...")
                    if self.ollama_available:
                        return self.get_ollama(temperature=temperature)
                    raise
        
        except Exception as e:
            logger.error(f"Error obteniendo LLM: {e}")
            raise
    
    def get_llm_for_agent(
        self,
        agent_name: str,
        privacy_mode: bool = False,
        temperature: float = 0.7,
    ) -> BaseChatModel:
        """Obtiene el LLM apropiado para un agente específico.
        
        Args:
            agent_name: Nombre del agente
            privacy_mode: Si el modo privacidad está activo
            temperature: Temperatura de generación
            
        Returns:
            Instancia del LLM apropiado para el agente
        """
        from src.core.prompts import should_use_local_llm
        
        # Determinar si usar local basado en el agente
        use_local = should_use_local_llm(agent_name) or privacy_mode
        
        if use_local:
            return self.get_llm(
                task_type=TaskType.PRIVATE,
                privacy_required=True,
                temperature=temperature,
            )
        else:
            return self.get_llm(
                task_type=TaskType.GENERAL,
                privacy_required=False,
                temperature=temperature,
            )


# Singleton para uso global
_factory: LLMFactory | None = None


def get_factory() -> LLMFactory:
    """Obtiene la instancia singleton del LLMFactory."""
    global _factory
    if _factory is None:
        _factory = LLMFactory()
    return _factory


def get_llm(
    task_type: TaskType | str = TaskType.GENERAL,
    privacy_required: bool = False,
    temperature: float = 0.7,
) -> BaseChatModel:
    """Función de conveniencia para obtener un LLM.
    
    Args:
        task_type: Tipo de tarea
        privacy_required: Si se requiere privacidad
        temperature: Temperatura de generación
        
    Returns:
        Instancia del LLM apropiado
    """
    return get_factory().get_llm(
        task_type=task_type,
        privacy_required=privacy_required,
        temperature=temperature,
    )

