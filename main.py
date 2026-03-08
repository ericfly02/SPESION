#!/usr/bin/env python3
"""SPESION 3.0 - Punto de entrada principal.

Este es el script principal para ejecutar SPESION.
Soporta múltiples modos de ejecución:

1. Bot de Telegram (default):
   python main.py

2. CLI interactivo:
   python main.py --cli

3. Servidor API:
   python main.py --api

4. Heartbeat (proactive background runner):
   python main.py --heartbeat

5. Cognitive reflection cycle:
   python main.py --reflect

6. Model health status:
   python main.py --status
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
        Path("./workspace"),
        Path("./workspace/memory"),
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
        description="SPESION 3.0 - Asistente Personal Multi-Agente con capacidades AGI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python main.py              # Ejecutar bot de Telegram
  python main.py --cli        # Ejecutar CLI interactivo
  python main.py --api        # Ejecutar servidor FastAPI
  python main.py --heartbeat  # Ejecutar heartbeat proactivo
  python main.py --reflect    # Ejecutar ciclo de reflexión cognitiva
  python main.py --status     # Ver estado de modelos y sistemas
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
        "--api",
        action="store_true",
        help="Ejecutar servidor FastAPI (puerto 8100)",
    )
    parser.add_argument(
        "--heartbeat",
        action="store_true",
        help="Ejecutar heartbeat proactivo (tareas programadas autónomas)",
    )
    parser.add_argument(
        "--reflect",
        action="store_true",
        help="Ejecutar un ciclo completo de reflexión cognitiva",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Mostrar estado de modelos, memoria y sistemas",
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
    
    # ------------------------------------------------------------------
    # SPESION 3.0: New execution modes
    # ------------------------------------------------------------------

    # Status: Show model health, memory stats, system state
    if args.status:
        print("\n" + "=" * 60)
        print("  SPESION 3.0 — System Status")
        print("=" * 60)

        # Model Router status
        try:
            from src.core.model_router import get_model_router
            router = get_model_router()
            health = router.get_health_status()
            print("\n🤖 Model Router:")
            for provider, status in health.get("providers", {}).items():
                icon = "✅" if status.get("healthy") else "❌"
                print(f"  {icon} {provider}: {status}")
        except Exception as e:
            print(f"\n🤖 Model Router: ⚠️  Not initialized ({e})")

        # Memory Bank stats
        try:
            from src.memory.evolving_memory import MemoryBank
            bank = MemoryBank()
            stats = bank.stats()
            print(f"\n🧠 Memory Bank:")
            print(f"  Total memories: {stats.get('total', 0)}")
            print(f"  By type: {stats.get('by_type', {})}")
            print(f"  Avg confidence: {stats.get('avg_confidence', 0):.2f}")
            print(f"  Links: {stats.get('total_links', 0)}")
        except Exception as e:
            print(f"\n🧠 Memory Bank: ⚠️  Not initialized ({e})")

        # Workspace files
        try:
            from src.core.workspace_loader import WorkspaceLoader
            loader = WorkspaceLoader()
            ctx = loader.load()
            available = [k for k, v in ctx.items() if v and k != "combined"]
            print(f"\n📁 Workspace Files: {', '.join(available)}")
        except Exception as e:
            print(f"\n📁 Workspace: ⚠️  Not loaded ({e})")

        print()
        return

    # Heartbeat: Run proactive background tasks
    if args.heartbeat:
        logger.info("Starting SPESION 3.0 Heartbeat Runner...")
        print("\n💓 Starting Heartbeat Runner (Ctrl+C to stop)...")
        try:
            from src.heartbeat.runner import HeartbeatRunner
            runner = HeartbeatRunner()
            asyncio.run(runner.start())
        except KeyboardInterrupt:
            print("\n💓 Heartbeat stopped.")
        except Exception as e:
            logger.error(f"Heartbeat error: {e}", exc_info=True)
        return

    # Reflect: Run one full cognitive cycle
    if args.reflect:
        logger.info("Running SPESION 3.0 Cognitive Reflection Cycle...")
        print("\n🧠 Running full cognitive reflection cycle...")
        try:
            from src.cognitive.reflection import CognitiveLoop
            loop = CognitiveLoop()
            result = asyncio.run(loop.run_full_cycle())
            print(f"\n✅ Reflection complete:")
            print(f"  Patterns detected: {result.get('patterns', 0)}")
            print(f"  Ideas generated: {result.get('ideas', 0)}")
            print(f"  Memories curated: {result.get('curated', False)}")
        except Exception as e:
            logger.error(f"Reflection error: {e}", exc_info=True)
            print(f"❌ Error: {e}")
        return

    # API server mode
    if args.api:
        logger.info("Starting SPESION 3.0 API Server...")
        try:
            import uvicorn
            from src.core.config import settings
            uvicorn.run(
                "src.interfaces.server:app",
                host=settings.api.host,
                port=settings.api.port,
                reload=False,
            )
        except ImportError:
            logger.error("uvicorn not installed. Run: pip install uvicorn")
        except Exception as e:
            logger.error(f"API server error: {e}", exc_info=True)
        return

    # ------------------------------------------------------------------
    # Default modes (Telegram / CLI)
    # ------------------------------------------------------------------

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
    logger.info("  SPESION 3.0 - Sistema Multi-Agente Personal")
    logger.info("=" * 60)
    
    if args.cli:
        run_cli()
    elif args.cli_async:
        asyncio.run(run_cli_async())
    else:
        run_telegram_bot()


if __name__ == "__main__":
    main()

