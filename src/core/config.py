"""Configuration management using Pydantic Settings."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    """Configuración de LLMs."""
    
    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    # Ollama (Local)
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="URL base de Ollama",
    )
    ollama_model_light: str = Field(
        default="llama3.2:3b",
        description="Modelo ligero para tareas simples/privadas",
    )
    ollama_model_heavy: str = Field(
        default="llama3.1:8b",
        description="Modelo más potente para tareas complejas locales",
    )
    
    # OpenAI
    openai_api_key: SecretStr | None = Field(
        default=None,
        description="API Key de OpenAI",
    )
    openai_model: str = Field(
        default="gpt-4o",
        description="Modelo de OpenAI a usar",
    )
    
    # Anthropic
    anthropic_api_key: SecretStr | None = Field(
        default=None,
        description="API Key de Anthropic",
    )
    anthropic_model: str = Field(
        default="claude-3-5-sonnet-20241022",
        description="Modelo de Anthropic a usar",
    )
    
    # Preferencia de proveedor cloud
    cloud_provider: Literal["openai", "anthropic"] = Field(
        default="openai",
        description="Proveedor cloud preferido",
    )


class TelegramSettings(BaseSettings):
    """Configuración de Telegram."""
    
    model_config = SettingsConfigDict(
        env_prefix="TELEGRAM_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    bot_token: SecretStr = Field(
        ...,
        description="Token del bot de Telegram",
    )
    allowed_user_ids: list[int] = Field(
        default_factory=list,
        description="IDs de usuarios permitidos (vacío = todos)",
    )


class NotionSettings(BaseSettings):
    """Configuración de Notion."""
    
    model_config = SettingsConfigDict(
        env_prefix="NOTION_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    api_key: SecretStr | None = Field(
        default=None,
        description="API Key de Notion",
    )
    tasks_database_id: str | None = Field(
        default=None,
        description="ID de la base de datos de Tasks",
    )
    knowledge_database_id: str | None = Field(
        default=None,
        description="ID de la base de datos de Knowledge",
    )
    crm_database_id: str | None = Field(
        default=None,
        description="ID de la base de datos de CRM/Finance",
    )


class GarminSettings(BaseSettings):
    """Configuración de Garmin Connect."""
    
    model_config = SettingsConfigDict(
        env_prefix="GARMIN_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    email: str | None = Field(
        default=None,
        description="Email de Garmin Connect",
    )
    password: SecretStr | None = Field(
        default=None,
        description="Password de Garmin Connect",
    )


class StravaSettings(BaseSettings):
    """Configuración de Strava."""
    
    model_config = SettingsConfigDict(
        env_prefix="STRAVA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    client_id: str | None = Field(
        default=None,
        description="Client ID de Strava",
    )
    client_secret: SecretStr | None = Field(
        default=None,
        description="Client Secret de Strava",
    )
    refresh_token: SecretStr | None = Field(
        default=None,
        description="Refresh Token de Strava",
    )


class GitHubSettings(BaseSettings):
    """Configuración de GitHub."""
    
    model_config = SettingsConfigDict(
        env_prefix="GITHUB_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    token: SecretStr | None = Field(
        default=None,
        description="Personal Access Token de GitHub",
    )
    default_owner: str | None = Field(
        default=None,
        description="Owner/organización por defecto",
    )


class GoogleSettings(BaseSettings):
    """Configuración de Google Calendar."""
    
    model_config = SettingsConfigDict(
        env_prefix="GOOGLE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    credentials_path: Path | None = Field(
        default=None,
        description="Ruta al archivo de credenciales de Google",
    )
    calendar_id: str = Field(
        default="primary",
        description="ID del calendario a usar",
    )


class SearchSettings(BaseSettings):
    """Configuración de búsqueda web."""
    
    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    tavily_api_key: SecretStr | None = Field(
        default=None,
        description="API Key de Tavily",
    )
    search_provider: Literal["tavily", "duckduckgo"] = Field(
        default="duckduckgo",
        description="Proveedor de búsqueda preferido",
    )


class StorageSettings(BaseSettings):
    """Configuración de almacenamiento."""
    
    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    chroma_persist_dir: Path = Field(
        default=Path("./data/chroma"),
        description="Directorio de persistencia de ChromaDB",
    )
    sqlite_db_path: Path = Field(
        default=Path("./data/spesion.db"),
        description="Ruta a la base de datos SQLite",
    )
    
    @field_validator("chroma_persist_dir", "sqlite_db_path", mode="before")
    @classmethod
    def ensure_path(cls, v: str | Path) -> Path:
        """Convierte strings a Path."""
        return Path(v) if isinstance(v, str) else v


class WhisperSettings(BaseSettings):
    """Configuración de Whisper para transcripción."""
    
    model_config = SettingsConfigDict(
        env_prefix="WHISPER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    model_size: Literal["tiny", "base", "small", "medium", "large-v3"] = Field(
        default="base",
        description="Tamaño del modelo Whisper",
    )
    device: Literal["cpu", "cuda", "auto"] = Field(
        default="cpu",
        description="Dispositivo para inferencia",
    )
    compute_type: Literal["int8", "float16", "float32"] = Field(
        default="int8",
        description="Tipo de computación (int8 para CPU)",
    )
    language: str = Field(
        default="es",
        description="Idioma por defecto",
    )


class Settings(BaseSettings):
    """Configuración principal de SPESION."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    # Modo de ejecución
    debug: bool = Field(
        default=False,
        description="Modo debug",
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="Nivel de logging",
    )
    
    # Sub-configuraciones
    llm: LLMSettings = Field(default_factory=LLMSettings)
    telegram: TelegramSettings = Field(default_factory=TelegramSettings)
    notion: NotionSettings = Field(default_factory=NotionSettings)
    garmin: GarminSettings = Field(default_factory=GarminSettings)
    strava: StravaSettings = Field(default_factory=StravaSettings)
    github: GitHubSettings = Field(default_factory=GitHubSettings)
    google: GoogleSettings = Field(default_factory=GoogleSettings)
    search: SearchSettings = Field(default_factory=SearchSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    whisper: WhisperSettings = Field(default_factory=WhisperSettings)
    
    def ensure_directories(self) -> None:
        """Crea los directorios necesarios si no existen."""
        self.storage.chroma_persist_dir.mkdir(parents=True, exist_ok=True)
        self.storage.sqlite_db_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Obtiene la configuración cacheada."""
    return Settings()


# Singleton para acceso directo
settings = get_settings()

