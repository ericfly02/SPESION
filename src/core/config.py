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
        default="minimax-m2.1:cloud",
        description="Modelo más potente para tareas complejas locales",
    )    
    """
    ollama_model_heavy: str = Field(
        default="llama3.1:8b",
        description="Modelo más potente para tareas complejas locales",
    )
    """
    
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
    finance_database_id: str | None = Field(
        default=None,
        description="ID de la base de datos de Finance Portfolio",
    )
    goals_database_id: str | None = Field(
        default=None,
        description="ID de la base de datos de Goals 2026",
    )
    pills_database_id: str | None = Field(
        default=None,
        description="ID de la base de datos de Knowledge Pills",
    )
    books_database_id: str | None = Field(
        default=None,
        description="ID de la base de datos de Books / Reading List",
    )
    trainings_database_id: str | None = Field(
        default=None,
        description="ID de la base de datos de Trainings / Weekly Trainings",
    )
    transactions_database_id: str | None = Field(
        default=None,
        description="ID de la base de datos de Transactions (trades/movimientos)",
    )


class IBKRSettings(BaseSettings):
    """Configuración de Interactive Brokers (Flex Web Service)."""

    model_config = SettingsConfigDict(
        env_prefix="IBKR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Flex Web Service
    flex_token: SecretStr | None = Field(
        default=None,
        description="IBKR Flex Web Service token",
    )
    flex_query_id: str | None = Field(
        default=None,
        description="IBKR Flex Query ID (statement query id)",
    )


class BitgetSettings(BaseSettings):
    """Configuración de Bitget (via ccxt)."""

    model_config = SettingsConfigDict(
        env_prefix="BITGET_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_key: SecretStr | None = Field(default=None, description="Bitget API key")
    api_secret: SecretStr | None = Field(default=None, description="Bitget API secret")
    passphrase: SecretStr | None = Field(default=None, description="Bitget API passphrase")
    # spot | swap | futures (ccxt uses 'defaultType' in options)
    default_type: Literal["spot", "swap", "futures"] = Field(
        default="spot",
        description="Tipo por defecto para Bitget en ccxt",
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
        default=Path("data/google_calendar_credentials.json"),
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


class TwilioSettings(BaseSettings):
    """Configuración de Twilio para llamadas y SMS."""

    model_config = SettingsConfigDict(
        env_prefix="TWILIO_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    account_sid: SecretStr | None = Field(
        default=None,
        description="Twilio Account SID",
    )
    auth_token: SecretStr | None = Field(
        default=None,
        description="Twilio Auth Token",
    )
    phone_number: str | None = Field(
        default=None,
        description="Your Twilio phone number (+34...)",
    )
    callback_url: str | None = Field(
        default=None,
        description="Public URL for call status callbacks",
    )


class SMTPSettings(BaseSettings):
    """Configuración SMTP para envío de emails."""

    model_config = SettingsConfigDict(
        env_prefix="SMTP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = Field(default="smtp.gmail.com", description="SMTP server host")
    port: int = Field(default=587, description="SMTP server port")
    username: str | None = Field(default=None, description="SMTP username / email")
    password: SecretStr | None = Field(default=None, description="SMTP password (app password)")
    from_name: str = Field(default="SPESION", description="Sender display name")


class AutonomousSettings(BaseSettings):
    """SPESION 3.0: Autonomous execution engine configuration."""

    model_config = SettingsConfigDict(
        env_prefix="AUTONOMOUS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    enabled: bool = Field(
        default=True,
        description="Enable autonomous plan execution",
    )
    approval_timeout_seconds: int = Field(
        default=300,
        description="Seconds to wait for user approval on dangerous actions",
    )
    max_plan_steps: int = Field(
        default=15,
        description="Maximum steps in a single autonomous plan",
    )
    background_worker_enabled: bool = Field(
        default=True,
        description="Enable background task queue worker",
    )


class DiscordSettings(BaseSettings):
    """Configuración de Discord."""

    model_config = SettingsConfigDict(
        env_prefix="DISCORD_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bot_token: SecretStr | None = Field(
        default=None,
        description="Token del bot de Discord",
    )
    guild_id: str | None = Field(
        default=None,
        description="ID del servidor de Discord",
    )
    allowed_user_ids: list[int] = Field(
        default_factory=list,
        description="IDs de usuarios permitidos (vacío = todos)",
    )


class APISettings(BaseSettings):
    """Configuración del API FastAPI."""

    model_config = SettingsConfigDict(
        env_prefix="SPESION_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_key: SecretStr = Field(
        default="change-me",
        description="API key for the FastAPI server (Bearer token)",
    )
    host: str = Field(default="0.0.0.0", description="API host")
    port: int = Field(default=8100, description="API port")


class HeartbeatSettings(BaseSettings):
    """SPESION 3.0: Heartbeat runner configuration."""

    model_config = SettingsConfigDict(
        env_prefix="HEARTBEAT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    enabled: bool = Field(
        default=False,
        description="Enable heartbeat proactive runner",
    )
    check_interval_minutes: int = Field(
        default=30,
        description="Minutes between heartbeat checks",
    )
    active_hours_start: str = Field(
        default="07:00",
        description="Start of active hours (HH:MM)",
    )
    active_hours_end: str = Field(
        default="23:30",
        description="End of active hours (HH:MM)",
    )
    timezone: str = Field(
        default="Europe/Madrid",
        description="Timezone for active hours",
    )


class MemoryBankSettings(BaseSettings):
    """SPESION 3.0: Evolving memory system configuration."""

    model_config = SettingsConfigDict(
        env_prefix="MEMORY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bank_db_path: Path = Field(
        default=Path("./data/memory_bank.db"),
        description="Path to SQLite memory bank database",
    )
    daily_logs_dir: Path = Field(
        default=Path("./workspace/memory"),
        description="Directory for daily memory log files",
    )
    min_confidence_threshold: float = Field(
        default=0.3,
        description="Minimum confidence to keep memories during cleanup",
    )
    max_context_tokens: int = Field(
        default=6000,
        description="Max tokens before context compaction triggers",
    )

    @field_validator("bank_db_path", "daily_logs_dir", mode="before")
    @classmethod
    def ensure_mem_path(cls, v: str | Path) -> Path:
        return Path(v) if isinstance(v, str) else v


class WorkspaceSettings(BaseSettings):
    """SPESION 3.0: Workspace bootstrap configuration."""

    model_config = SettingsConfigDict(
        env_prefix="WORKSPACE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    directory: Path = Field(
        default=Path("./workspace"),
        description="Workspace directory containing SOUL.md, IDENTITY.md, etc.",
    )
    cache_ttl_seconds: int = Field(
        default=60,
        description="Seconds to cache workspace files in memory",
    )

    @field_validator("directory", mode="before")
    @classmethod
    def ensure_ws_path(cls, v: str | Path) -> Path:
        return Path(v) if isinstance(v, str) else v


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
    discord: DiscordSettings = Field(default_factory=DiscordSettings)
    api: APISettings = Field(default_factory=APISettings)
    notion: NotionSettings = Field(default_factory=NotionSettings)
    ibkr: IBKRSettings = Field(default_factory=IBKRSettings)
    bitget: BitgetSettings = Field(default_factory=BitgetSettings)
    garmin: GarminSettings = Field(default_factory=GarminSettings)
    strava: StravaSettings = Field(default_factory=StravaSettings)
    github: GitHubSettings = Field(default_factory=GitHubSettings)
    google: GoogleSettings = Field(default_factory=GoogleSettings)
    search: SearchSettings = Field(default_factory=SearchSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    whisper: WhisperSettings = Field(default_factory=WhisperSettings)
    
    # SPESION 3.0: New subsystem settings
    heartbeat: HeartbeatSettings = Field(default_factory=HeartbeatSettings)
    memory_bank: MemoryBankSettings = Field(default_factory=MemoryBankSettings)
    workspace: WorkspaceSettings = Field(default_factory=WorkspaceSettings)
    
    # SPESION 3.0: Autonomous execution
    twilio: TwilioSettings = Field(default_factory=TwilioSettings)
    smtp: SMTPSettings = Field(default_factory=SMTPSettings)
    autonomous: AutonomousSettings = Field(default_factory=AutonomousSettings)
    
    def ensure_directories(self) -> None:
        """Crea los directorios necesarios si no existen."""
        self.storage.chroma_persist_dir.mkdir(parents=True, exist_ok=True)
        self.storage.sqlite_db_path.parent.mkdir(parents=True, exist_ok=True)
        # SPESION 3.0: Ensure new directories exist
        self.memory_bank.bank_db_path.parent.mkdir(parents=True, exist_ok=True)
        self.memory_bank.daily_logs_dir.mkdir(parents=True, exist_ok=True)
        self.workspace.directory.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Obtiene la configuración cacheada."""
    return Settings()


# Singleton para acceso directo
settings = get_settings()

