#!/usr/bin/env python3
"""SPESION - Punto de entrada principal.

Este es el script principal para ejecutar SPESION.
Soporta múltiples modos de ejecución:

1. Bot de Telegram (default):
   python main.py

2. CLI interactivo:
   python main.py --cli

3. Servidor API (futuro):
   python main.py --api
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Configurar path
sys.path.insert(0, str(Path(__file__).parent))


def setup_logging(level: str = "INFO") -> None:
    """Configura el sistema de logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("./data/spesion.log", mode="a"),
        ],
    )
    
    # Reducir logs de librerías externas
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)


def ensure_directories() -> None:
    """Crea los directorios necesarios."""
    dirs = [
        Path("./data"),
        Path("./data/chroma"),
        Path("./data/temp"),
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)


def run_telegram_bot() -> None:
    """Ejecuta el bot de Telegram."""
    from src.interfaces.telegram_bot import SpesionBot
    
    logger = logging.getLogger(__name__)
    logger.info("Iniciando SPESION en modo Telegram Bot...")
    
    bot = SpesionBot()
    bot.run()


def run_cli() -> None:
    """Ejecuta la interfaz de línea de comandos interactiva."""
    from src.core.graph import get_assistant
    
    logger = logging.getLogger(__name__)
    logger.info("Iniciando SPESION en modo CLI...")
    
    print("\n" + "=" * 60)
    print("  SPESION - Asistente Personal")
    print("  Escribe 'exit' o 'quit' para salir")
    print("=" * 60 + "\n")
    
    assistant = get_assistant()
    
    while True:
        try:
            user_input = input("Tú: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ("exit", "quit", "q"):
                print("\n👋 ¡Hasta luego!")
                break
            
            print("SPESION: ", end="", flush=True)
            response = assistant.chat(user_input)
            print(response)
            print()
            
        except KeyboardInterrupt:
            print("\n\n👋 ¡Hasta luego!")
            break
        except Exception as e:
            logger.error(f"Error: {e}")
            print(f"Error: {e}")


async def run_cli_async() -> None:
    """Versión asíncrona del CLI."""
    from src.core.graph import get_assistant
    
    logger = logging.getLogger(__name__)
    logger.info("Iniciando SPESION en modo CLI async...")
    
    print("\n" + "=" * 60)
    print("  SPESION - Asistente Personal (Async)")
    print("  Escribe 'exit' o 'quit' para salir")
    print("=" * 60 + "\n")
    
    assistant = get_assistant()
    
    while True:
        try:
            user_input = await asyncio.get_event_loop().run_in_executor(
                None, lambda: input("Tú: ").strip()
            )
            
            if not user_input:
                continue
            
            if user_input.lower() in ("exit", "quit", "q"):
                print("\n👋 ¡Hasta luego!")
                break
            
            print("SPESION: ", end="", flush=True)
            response = await assistant.achat(user_input)
            print(response)
            print()
            
        except KeyboardInterrupt:
            print("\n\n👋 ¡Hasta luego!")
            break
        except Exception as e:
            logger.error(f"Error: {e}")
            print(f"Error: {e}")


def check_ollama() -> bool:
    """Verifica si Ollama está disponible."""
    try:
        import httpx
        from src.core.config import settings
        
        response = httpx.get(
            f"{settings.llm.ollama_base_url}/api/tags",
            timeout=5.0,
        )
        return response.status_code == 200
    except Exception:
        return False


def pull_ollama_models() -> None:
    """Descarga los modelos de Ollama necesarios."""
    import subprocess
    from src.core.config import settings
    
    logger = logging.getLogger(__name__)
    
    models = [settings.llm.ollama_model_light, settings.llm.ollama_model_heavy]
    
    for model in models:
        logger.info(f"Descargando modelo Ollama: {model}")
        try:
            subprocess.run(
                ["ollama", "pull", model],
                check=True,
                capture_output=True,
            )
            logger.info(f"Modelo {model} descargado")
        except subprocess.CalledProcessError as e:
            logger.warning(f"Error descargando {model}: {e}")
        except FileNotFoundError:
            logger.warning("Ollama CLI no encontrado")
            break


def main() -> None:
    """Función principal."""
    parser = argparse.ArgumentParser(
        description="SPESION - Asistente Personal Multi-Agente",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python main.py              # Ejecutar bot de Telegram
  python main.py --cli        # Ejecutar CLI interactivo
  python main.py --setup      # Configurar entorno inicial
        """,
    )
    
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Ejecutar en modo CLI interactivo",
    )
    parser.add_argument(
        "--cli-async",
        action="store_true",
        help="Ejecutar CLI en modo asíncrono",
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Configurar entorno inicial (descargar modelos, etc.)",
    )
    parser.add_argument(
        "--setup-notion",
        action="store_true",
        help="Re-inicializar estructura de Notion (CUIDADO: Sobreescribe IDs en .env)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Nivel de logging (default: INFO)",
    )
    
    args = parser.parse_args()
    
    # Setup
    ensure_directories()
    setup_logging(args.log_level)
    
    logger = logging.getLogger(__name__)
    
    # Modo setup
    if args.setup:
        logger.info("Ejecutando setup inicial...")
        
        # Verificar Ollama
        if check_ollama():
            logger.info("Ollama disponible, descargando modelos...")
            pull_ollama_models()
        else:
            logger.warning(
                "Ollama no disponible. Instala Ollama desde https://ollama.ai"
            )
        
        # Verificar configuración
        try:
            from src.core.config import settings
            logger.info(f"Configuración cargada. Cloud provider: {settings.llm.cloud_provider}")
        except Exception as e:
            logger.error(f"Error cargando configuración: {e}")
            logger.info("Copia .env.example a .env y configura las variables")
        
        logger.info("Setup completado")
        return

    # Modo setup Notion
    if args.setup_notion:
        try:
            from src.core.config import settings
            from src.services.notion_setup import NotionSetupService
            
            if not settings.notion.api_key:
                logger.error("NOTION_API_KEY no encontrada en .env")
                sys.exit(1)
                
            logger.info("Iniciando configuración de Notion...")
            logger.warning("⚠️  Esto creará nuevas bases de datos y sobreescribirá el .env")
            
            service = NotionSetupService(settings.notion.api_key.get_secret_value())
            ids = service.initialize_workspace(overwrite_env=True)
            
            logger.info("✅ Setup de Notion completado exitosamente.")
            logger.info(f"Nuevos IDs guardados en .env: {list(ids.keys())}")
            
        except Exception as e:
            logger.error(f"Error durante el setup de Notion: {e}")
            sys.exit(1)
        return
    
    # Verificar token de Telegram si no es CLI
    if not args.cli and not args.cli_async:
        try:
            from src.core.config import settings
            if not settings.telegram.bot_token:
                logger.error("TELEGRAM_BOT_TOKEN no configurado")
                logger.info("Usa --cli para modo interactivo sin Telegram")
                sys.exit(1)
        except Exception as e:
            logger.error(f"Error cargando configuración: {e}")
            sys.exit(1)
    
    # Ejecutar modo seleccionado
    logger.info("=" * 60)
    logger.info("  SPESION - Sistema Multi-Agente Personal")
    logger.info("=" * 60)
    
    if args.cli:
        run_cli()
    elif args.cli_async:
        asyncio.run(run_cli_async())
    else:
        run_telegram_bot()


if __name__ == "__main__":
    main()

