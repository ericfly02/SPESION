"""Telegram Bot - Interfaz principal de SPESION via Telegram."""

from __future__ import annotations

import logging
import json
import re
from datetime import datetime, time
from pathlib import Path
from typing import TYPE_CHECKING

from telegram import Update
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

if TYPE_CHECKING:
    from src.core.graph import SpesionAssistant

logger = logging.getLogger(__name__)

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore


class SpesionBot:
    """Bot de Telegram para SPESION.
    
    Comandos disponibles:
    - /start: Iniciar conversación
    - /resumen: Resumen diario de papers/noticias
    - /entreno: Plan de entrenamiento
    - /finance: Estado del portfolio
    - /audit: Code review (TechLead)
    - /journal: Iniciar journaling
    - /agenda: Tareas y calendario
    - /status: Estado del sistema
    - /help: Mostrar ayuda
    """
    
    def __init__(self) -> None:
        """Inicializa el bot."""
        from src.core.config import settings
        
        self.token = settings.telegram.bot_token.get_secret_value()
        self.allowed_users = settings.telegram.allowed_user_ids
        
        self._assistant: SpesionAssistant | None = None
        self._whisper_service = None
        self._app: Application | None = None
    
    @property
    def assistant(self) -> SpesionAssistant:
        """Obtiene el asistente (lazy loading)."""
        if self._assistant is None:
            from src.core.graph import get_assistant
            self._assistant = get_assistant()
        return self._assistant
    
    @property
    def whisper(self):
        """Obtiene el servicio de Whisper (lazy loading)."""
        if self._whisper_service is None:
            from src.services.whisper_service import get_whisper_service
            self._whisper_service = get_whisper_service()
        return self._whisper_service
    
    def _check_user_allowed(self, user_id: int) -> bool:
        """Verifica si el usuario está permitido."""
        if not self.allowed_users:
            return True  # Sin restricciones si la lista está vacía
        return user_id in self.allowed_users
    
    async def _send_typing(self, update: Update) -> None:
        """Envía indicador de 'escribiendo...'."""
        if update.effective_chat:
            await update.effective_chat.send_chat_action("typing")

    async def _reply_safe(self, update: Update, text: str) -> None:
        """Envía un mensaje intentando Markdown primero, y cayendo a texto plano si falla.
        
        Esto evita crashes por 'Can't parse entities' cuando el LLM genera Markdown inválido.
        """
        if not text:
            return

        try:
            # Intentar con Markdown primero para formato bonito
            await update.message.reply_text(text, parse_mode="Markdown")
        except TelegramError as e:
            logger.warning(f"Error enviando Markdown: {e}. Reintentando como texto plano.")
            try:
                # Fallback a texto plano
                await update.message.reply_text(text, parse_mode=None)
            except Exception as e2:
                logger.error(f"Error crítico enviando mensaje: {e2}")
                await update.message.reply_text("Error enviando la respuesta.")

    # =========================================================================
    # HANDLERS DE COMANDOS
    # =========================================================================
    
    async def start_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handler para /start."""
        if not self._check_user_allowed(update.effective_user.id):
            await update.message.reply_text("No tienes acceso a este bot.")
            return
        
        welcome_message = """👋 ¡Hola Eric! Soy **SPESION**, tu asistente personal.

Puedo ayudarte con:

📚 **/resumen** - Papers de ArXiv y noticias tech
🏃 **/entreno** - Tu plan de entrenamiento del día
💰 **/finance** - Estado de tu portfolio
💭 **/journal** - Iniciar journaling nocturno
📅 **/agenda** - Calendario y tareas
🔧 **/audit** - Code review de un repo
🛡️ **/status** - Estado del sistema
❓ **/help** - Ver todos los comandos

O simplemente escríbeme lo que necesites."""
        
        await self._reply_safe(update, welcome_message)
    
    async def help_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handler para /help."""
        help_text = """📖 **Comandos de SPESION**

**Investigación (Scholar)**
• /resumen - Resumen diario de papers y noticias

**Salud (Coach)**
• /entreno - Plan de entrenamiento adaptado a tu recuperación
• "¿Cómo está mi HRV?" - Métricas de Garmin

**Finanzas (Tycoon)**
• /finance - Estado y asignación del portfolio
• "¿Cómo va mi portfolio?" - Resumen rápido

**Bienestar (Companion)**
• /journal - Iniciar entrada de diario
• Cualquier reflexión emocional

**Ingeniería (TechLead)**
• /audit `owner/repo` - Code review de un repositorio
• "Revisa este código..." - Análisis de código

**Productividad (Executive)**
• /agenda - Calendario y tareas del día
• "¿Qué tengo hoy?" - Resumen rápido

**Sistema (Sentinel)**
• /status - Estado de todos los servicios

**Tips:**
🎤 Puedes enviarme notas de voz
🔒 Tus datos sensibles se procesan localmente"""
        
        await self._reply_safe(update, help_text)
    
    async def resumen_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handler para /resumen - Investigación diaria."""
        if not self._check_user_allowed(update.effective_user.id):
            return
        
        await self._send_typing(update)
        
        response = await self.assistant.achat(
            message="Dame un resumen de los papers más relevantes de IA y noticias tech de hoy",
            user_id=str(update.effective_user.id),
            telegram_chat_id=update.effective_chat.id,
        )
        
        await self._reply_safe(update, response)
    
    async def entreno_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handler para /entreno - Plan de entrenamiento."""
        if not self._check_user_allowed(update.effective_user.id):
            return
        
        await self._send_typing(update)
        
        response = await self.assistant.achat(
            message="Dame mi plan de entrenamiento para hoy basado en mi estado de recuperación",
            user_id=str(update.effective_user.id),
            telegram_chat_id=update.effective_chat.id,
        )
        
        await self._reply_safe(update, response)
    
    async def finance_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handler para /finance - Estado del portfolio."""
        if not self._check_user_allowed(update.effective_user.id):
            return
        
        await self._send_typing(update)
        
        response = await self.assistant.achat(
            message="¿Cómo está mi portfolio? Dame el estado actual y sugerencias de rebalanceo si las hay",
            user_id=str(update.effective_user.id),
            telegram_chat_id=update.effective_chat.id,
        )
        
        await self._reply_safe(update, response)
    
    async def journal_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handler para /journal - Journaling nocturno."""
        if not self._check_user_allowed(update.effective_user.id):
            return
        
        await self._send_typing(update)
        
        response = await self.assistant.achat(
            message="Quiero hacer mi journal de hoy. Guíame por el proceso.",
            user_id=str(update.effective_user.id),
            telegram_chat_id=update.effective_chat.id,
        )
        
        await self._reply_safe(update, response)
    
    async def agenda_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handler para /agenda - Calendario y tareas."""
        if not self._check_user_allowed(update.effective_user.id):
            return
        
        await self._send_typing(update)
        
        response = await self.assistant.achat(
            message="¿Qué tengo en la agenda hoy? Dame un resumen de eventos y tareas prioritarias",
            user_id=str(update.effective_user.id),
            telegram_chat_id=update.effective_chat.id,
        )
        
        await self._reply_safe(update, response)
    
    async def audit_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handler para /audit - Code review."""
        if not self._check_user_allowed(update.effective_user.id):
            return
        
        # Verificar si hay argumentos (nombre del repo)
        if context.args:
            repo_name = context.args[0]
            message = f"Haz un code review del repositorio {repo_name}. Enfócate en issues críticos."
        else:
            await update.message.reply_text(
                "Uso: `/audit owner/repo`\n\n"
                "Ejemplo: `/audit ericgonzalez/civita`",
                parse_mode="Markdown",
            )
            return
        
        await self._send_typing(update)
        
        response = await self.assistant.achat(
            message=message,
            user_id=str(update.effective_user.id),
            telegram_chat_id=update.effective_chat.id,
        )
        
        await self._reply_safe(update, response)
    
    async def status_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handler para /status - Estado del sistema."""
        if not self._check_user_allowed(update.effective_user.id):
            return
        
        await self._send_typing(update)
        
        response = await self.assistant.achat(
            message="Dame el estado completo del sistema SPESION",
            user_id=str(update.effective_user.id),
            telegram_chat_id=update.effective_chat.id,
        )
        
        await self._reply_safe(update, response)
    
    # =========================================================================
    # HANDLERS DE MENSAJES
    # =========================================================================
    
    async def handle_text_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handler para mensajes de texto."""
        if not self._check_user_allowed(update.effective_user.id):
            return
        
        await self._send_typing(update)
        
        response = await self.assistant.achat(
            message=update.message.text,
            user_id=str(update.effective_user.id),
            telegram_chat_id=update.effective_chat.id,
        )
        
        # Dividir mensaje si es muy largo (límite de Telegram: 4096 chars)
        if len(response) > 4000:
            chunks = [response[i:i+4000] for i in range(0, len(response), 4000)]
            for chunk in chunks:
                await self._reply_safe(update, chunk)
        else:
            await self._reply_safe(update, response)
    
    async def handle_voice_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handler para notas de voz."""
        if not self._check_user_allowed(update.effective_user.id):
            return
        
        await self._send_typing(update)
        
        try:
            # Descargar audio
            voice = update.message.voice
            file = await context.bot.get_file(voice.file_id)
            
            # Crear directorio temporal
            temp_dir = Path("./data/temp")
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            audio_path = temp_dir / f"{voice.file_id}.ogg"
            await file.download_to_drive(audio_path)
            
            # Transcribir
            await update.message.reply_text("🎤 Transcribiendo audio...")
            
            transcription = await self.whisper.transcribe_async(audio_path)
            text = transcription.get("text", "")
            
            # Limpiar archivo temporal
            audio_path.unlink(missing_ok=True)
            
            if not text:
                await update.message.reply_text(
                    "No pude transcribir el audio. ¿Puedes intentar de nuevo?"
                )
                return
            
            # Mostrar transcripción
            await self._reply_safe(update, f"📝 Transcripción: _{text}_")
            
            # Procesar con el asistente
            await self._send_typing(update)
            
            response = await self.assistant.achat(
                message=text,
                user_id=str(update.effective_user.id),
                telegram_chat_id=update.effective_chat.id,
                is_voice=True,
            )
            
            await self._reply_safe(update, response)
            
        except Exception as e:
            logger.error(f"Error procesando nota de voz: {e}")
            await update.message.reply_text(
                f"Error procesando el audio: {str(e)}"
            )

    async def handle_photo_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handler para fotos (screenshots). Extrae texto via OCR y da feedback."""
        if not self._check_user_allowed(update.effective_user.id):
            return

        await self._send_typing(update)

        try:
            if not update.message.photo:
                return

            # Descargar la foto de mayor resolución
            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)

            temp_dir = Path("./data/uploads")
            temp_dir.mkdir(parents=True, exist_ok=True)

            file_path = temp_dir / f"{photo.file_id}.jpg"
            await file.download_to_drive(file_path)

            await update.message.reply_text("🖼️ Screenshot recibido. Leyendo texto...")

            extracted_text = ""
            extraction_error = None
            try:
                from src.tools.image_tools import extract_text_from_image

                result = extract_text_from_image.invoke(
                    {"file_path": str(file_path.absolute()), "lang": "spa+eng"}
                )
                if isinstance(result, dict) and result.get("ok"):
                    extracted_text = str(result.get("text") or "")
                else:
                    extraction_error = (
                        result.get("error") if isinstance(result, dict) else "Unknown OCR error"
                    )
            except Exception as e_ocr:
                extraction_error = str(e_ocr)

            caption = update.message.caption or ""
            hint = (
                "El usuario ha subido un screenshot de un chat.\n"
                "Tarea: ayudarle a responder (a una chica/amigo), con psicología práctica.\n"
                "- No inventes mensajes que no ves.\n"
                "- Primero resume el contexto del chat.\n"
                "- Luego propone 2-3 respuestas: (1) directa, (2) juguetona, (3) madura/empática.\n"
                "- Pregunta UNA aclaración si falta una pieza crítica (por ejemplo, objetivo del usuario).\n"
            )

            if extraction_error:
                payload = (
                    f"{hint}\n"
                    f"Nota del usuario: {caption}\n"
                    f"ERROR OCR: {extraction_error}\n"
                    "Pide al usuario que re-subiera el screenshot con más zoom o mejor calidad.\n"
                )
            else:
                payload = (
                    f"{hint}\n"
                    f"Nota del usuario: {caption}\n\n"
                    "=== TEXTO OCR (puede contener errores) ===\n"
                    f"{extracted_text}\n"
                    "=== FIN ===\n"
                )

            response = await self.assistant.achat(
                message=payload,
                user_id=str(update.effective_user.id),
                telegram_chat_id=update.effective_chat.id,
            )

            await self._reply_safe(update, response)

        except Exception as e:
            logger.error(f"Error procesando foto: {e}")
            await update.message.reply_text(f"Error procesando la imagen: {e}")
    
    async def handle_document_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handler para documentos (CSV, PDF, etc)."""
        if not self._check_user_allowed(update.effective_user.id):
            return
        
        await self._send_typing(update)
        
        try:
            document = update.message.document
            file = await context.bot.get_file(document.file_id)
            
            # Crear directorio temporal
            temp_dir = Path("./data/uploads")
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            file_path = temp_dir / document.file_name
            await file.download_to_drive(file_path)
            
            await update.message.reply_text(f"📂 Archivo recibido: {document.file_name}. Procesando...")

            # 1) Extraer texto del documento (para que el LLM tenga algo real que analizar)
            extracted_text = ""
            extraction_error = None
            try:
                from src.tools.document_tools import extract_text_from_document

                result = extract_text_from_document.invoke(
                    {"file_path": str(file_path.absolute()), "max_chars": 30000}
                )
                if isinstance(result, dict) and result.get("ok"):
                    extracted_text = str(result.get("text") or "")
                else:
                    extraction_error = (
                        result.get("error") if isinstance(result, dict) else "Unknown extraction error"
                    )
            except Exception as e_extract:
                extraction_error = str(e_extract)

            # 2) Construir mensaje enriquecido al asistente
            user_caption = update.message.caption or ""
            hint = (
                "El usuario ha subido un documento. Analízalo con cuidado, SIN inventar datos.\n"
                "- Si es un informe de salud/running (VO2, umbrales, lactato, etc.): "
                "extrae métricas clave y GUARDA los hechos con `save_important_memory` (category='health').\n"
                "- Si es de finanzas: detecta si es CSV o texto de reporte y propone importación.\n"
                "- Responde con un resumen claro + los datos que has guardado.\n"
            )

            if extraction_error:
                doc_payload = (
                    f"{hint}\n"
                    f"Archivo: {file_path.absolute()}\n"
                    f"Nombre: {document.file_name}\n"
                    f"Nota del usuario: {user_caption}\n"
                    f"ERROR extrayendo texto: {extraction_error}\n"
                    "Si el PDF es escaneado (imagen), necesitaremos OCR (lo añadiremos si lo confirmas).\n"
                )
            else:
                doc_payload = (
                    f"{hint}\n"
                    f"Archivo: {file_path.absolute()}\n"
                    f"Nombre: {document.file_name}\n"
                    f"Nota del usuario: {user_caption}\n\n"
                    "=== TEXTO EXTRAÍDO (puede estar truncado) ===\n"
                    f"{extracted_text}\n"
                    "=== FIN ===\n"
                )

            response = await self.assistant.achat(
                message=doc_payload,
                user_id=str(update.effective_user.id),
                telegram_chat_id=update.effective_chat.id,
            )

            await self._reply_safe(update, response)
            
        except Exception as e:
            logger.error(f"Error procesando documento: {e}")
            await update.message.reply_text(f"Error procesando el archivo: {e}")

    async def handle_error(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handler de errores."""
        logger.error(f"Error en Telegram Bot: {context.error}")
        
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "😅 Hubo un error procesando tu mensaje. ¿Puedes intentar de nuevo?"
            )
    
    # =========================================================================
    # MÉTODOS DE EJECUCIÓN
    # =========================================================================
    
    def build_application(self) -> Application:
        """Construye la aplicación de Telegram."""
        app = Application.builder().token(self.token).build()
        
        # Registrar handlers de comandos
        app.add_handler(CommandHandler("start", self.start_command))
        app.add_handler(CommandHandler("help", self.help_command))
        app.add_handler(CommandHandler("resumen", self.resumen_command))
        app.add_handler(CommandHandler("entreno", self.entreno_command))
        app.add_handler(CommandHandler("finance", self.finance_command))
        app.add_handler(CommandHandler("journal", self.journal_command))
        app.add_handler(CommandHandler("agenda", self.agenda_command))
        app.add_handler(CommandHandler("audit", self.audit_command))
        app.add_handler(CommandHandler("status", self.status_command))
        
        # Registrar handlers de mensajes
        app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self.handle_text_message,
        ))
        app.add_handler(MessageHandler(
            filters.VOICE,
            self.handle_voice_message,
        ))
        app.add_handler(MessageHandler(
            filters.PHOTO,
            self.handle_photo_message,
        ))
        app.add_handler(MessageHandler(
            filters.Document.ALL,
            self.handle_document_message,
        ))
        
        # Handler de errores
        app.add_error_handler(self.handle_error)
        
        # JobQueue para tareas programadas (Scholar daily)
        if app.job_queue:
            tz = ZoneInfo("Europe/Madrid") if ZoneInfo else None

            app.job_queue.run_daily(
                self.send_scholar_daily_summary,
                time=time(hour=9, minute=0, tzinfo=tz),  # 09:00 local (Europe/Madrid)
                days=(0, 1, 2, 3, 4, 5, 6),
                name="scholar_daily",
                job_kwargs={
                    "misfire_grace_time": 120,
                    "coalesce": True,
                    "max_instances": 1,
                },
            )

            # Morning Brief (agenda + entreno + portfolio)
            app.job_queue.run_daily(
                self.send_morning_brief,
                time=time(hour=8, minute=30, tzinfo=tz),  # 08:30 local
                days=(0, 1, 2, 3, 4, 5, 6),
                name="morning_brief",
                job_kwargs={
                    "misfire_grace_time": 300,
                    "coalesce": True,
                    "max_instances": 1,
                },
            )
        
        self._app = app
        return app

    async def _send_long_message(self, chat_id: int, text: str, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Envía un mensaje largo dividiéndolo en fragmentos seguros."""
        max_length = 4000
        
        if len(text) <= max_length:
            try:
                await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
            except TelegramError:
                await context.bot.send_message(chat_id=chat_id, text=text)
            return

        # Split logic simple pero efectiva
        chunks = [text[i:i+max_length] for i in range(0, len(text), max_length)]
        for i, chunk in enumerate(chunks):
            try:
                await context.bot.send_message(chat_id=chat_id, text=chunk, parse_mode="Markdown")
            except TelegramError:
                # Si falla el markdown (probablemente cortamos un tag), enviar texto plano
                await context.bot.send_message(chat_id=chat_id, text=chunk)

    async def send_scholar_daily_summary(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Envía el resumen diario de Scholar."""
        # Si no hay usuarios en allowed_users, intentar obtenerlos de las variables de entorno
        target_chat_id = None
        
        if self.allowed_users:
            target_chat_id = self.allowed_users[0]
        else:
            logger.warning("No hay usuarios configurados en TELEGRAM_ALLOWED_USER_IDS para el resumen diario.")
            return

        logger.info(f"Ejecutando resumen diario de Scholar para {target_chat_id}")
        
        try:
            # 1) Preparar inputs (code-driven) para evitar alucinaciones y repetición
            from src.tools.arxiv_tool import get_recent_papers
            from src.tools.search_tool import search_news

            cache_path = Path("data/scholar_sent_arxiv_ids.json")
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            sent_ids: set[str] = set()
            try:
                if cache_path.exists():
                    payload = json.loads(cache_path.read_text(encoding="utf-8"))
                    sent_ids = set(payload.get("ids", []))
            except Exception:
                sent_ids = set()

            def _norm_arxiv_id(x: str) -> str:
                # Normaliza "2512.25075v1" -> "2512.25075"
                return re.sub(r"v\d+$", "", x.strip())

            papers = get_recent_papers.invoke({
                "days": 7,
                "max_results": 18,
                "categories": ["cs.AI", "cs.LG", "cs.CL", "q-bio.NC", "q-fin.GN", "econ.GN", "q-bio.QM"],
            })
            papers = [p for p in papers if isinstance(p, dict) and "error" not in p]
            # Dedupe: strip version suffix + cap fields to reduce prompt tokens
            cleaned_papers: list[dict] = []
            for p in papers:
                aid = p.get("arxiv_id")
                if not aid:
                    continue
                base_id = _norm_arxiv_id(str(aid))
                if base_id in sent_ids:
                    continue
                cleaned_papers.append({
                    "title": p.get("title", "")[:180],
                    "published": p.get("published", ""),
                    "arxiv_id": base_id,
                    "pdf_url": p.get("pdf_url", ""),
                    "category": p.get("category", ""),
                    "summary": str(p.get("summary", ""))[:220],
                })
            papers = cleaned_papers[:8]

            # Curación de noticias: evitar gadgets/laptops, priorizar economía/medicina/neuro/IA
            raw_news: list[dict] = []
            for q in [
                "AI policy regulation foundation models 2026",
                "neuroscience sleep cognition study 2026",
                "medicine longevity clinical trial 2026",
                "macroeconomics inflation central bank 2026",
                "markets economy recession indicators 2026",
            ]:
                items = search_news.invoke({"query": q, "max_results": 5, "region": "es-es"})
                if isinstance(items, list):
                    raw_news.extend([x for x in items if isinstance(x, dict) and "error" not in x])

            bad_kw = {"laptop", "portátil", "smartphone", "iphone", "ipad", "android", "wearable", "auriculares", "headphones"}
            seen_urls: set[str] = set()
            news: list[dict] = []
            for n in raw_news:
                title = str(n.get("title", "")).lower()
                url = str(n.get("url", ""))
                if not url or url in seen_urls:
                    continue
                if any(k in title for k in bad_kw):
                    continue
                seen_urls.add(url)
                news.append({
                    "title": str(n.get("title", ""))[:200],
                    "url": url,
                    "source": n.get("source", ""),
                    "date": n.get("date", ""),
                    "snippet": str(n.get("snippet", ""))[:180],
                })
            news = news[:7]

            async def _generate_brief(short_mode: bool) -> str:
                return await self.assistant.achat(
                    message=(
                        "Genera mi 'Scholar Daily Briefing' Super Aesthetic.\n\n"
                        "REGLA: NO puedes añadir papers/noticias fuera de las listas. "
                        "Si faltan temas, dilo.\n\n"
                        f"PAPERS_JSON:\n{json.dumps(papers, ensure_ascii=False)}\n\n"
                        f"NEWS_JSON:\n{json.dumps(news, ensure_ascii=False)}\n\n"
                        "Requisitos: cubrir IA, neurociencia, medicina, economía/ciencia. "
                        "Omitir gadgets (laptops, móviles).\n"
                        + ("Modo: compacto (máx 6-7 min lectura)." if short_mode else "Modo: normal (máx 8-10 min lectura).")
                    ),
                    user_id=str(target_chat_id),
                    telegram_chat_id=target_chat_id,
                )

            # 2) Generar briefing; si OpenAI revienta por TPM/tokens, reintentar compacto
            try:
                response_text = await _generate_brief(short_mode=False)
            except Exception as e1:
                if "rate_limit_exceeded" in str(e1) or "Request too large" in str(e1) or "TPM" in str(e1):
                    response_text = await _generate_brief(short_mode=True)
                else:
                    raise

            # Persistir IDs para dedupe futuro
            try:
                new_ids = [_norm_arxiv_id(str(p.get("arxiv_id"))) for p in papers if p.get("arxiv_id")]
                merged = list((set(_norm_arxiv_id(x) for x in sent_ids) | set(new_ids)))
                merged = merged[-300:]  # mantener acotado
                cache_path.write_text(
                    json.dumps({"ids": merged, "updated_at": datetime.now().strftime("%Y-%m-%d")}, ensure_ascii=False),
                    encoding="utf-8",
                )
            except Exception:
                pass
            
            # 2. Guardar en Notion manualmente (Código-driven para fiabilidad)
            final_message = f"🎓 **Scholar Daily Briefing**\n\n{response_text}"
            
            try:
                from src.tools.notion_mcp import create_knowledge_pill
                from datetime import datetime
                
                today_str = datetime.now().strftime("%Y-%m-%d")
                title = f"Daily Briefing - {today_str}"
                
                # Invocar herramienta directamente
                save_result = create_knowledge_pill.invoke({
                    "title": title,
                    "content": response_text,
                    "categories": ["Daily Briefing", "Scholar"],
                    "tags": ["AI", "Tech", "Auto"]
                })
                
                if isinstance(save_result, dict) and save_result.get("created"):
                    url = save_result.get("url")
                    final_message += f"\n\n💾 **Guardado en Notion:** [Ver en SPESION HQ]({url})"
                elif isinstance(save_result, dict) and "error" in save_result:
                    logger.error(f"Error guardando en Notion: {save_result['error']}")
                    final_message += f"\n\n⚠️ *No se pudo guardar en Notion automáticamente.*"
                    
            except Exception as e_notion:
                logger.error(f"Excepción guardando en Notion: {e_notion}")
            
            # 3. Enviar a Telegram
            await self._send_long_message(target_chat_id, final_message, context)
            
        except Exception as e:
            logger.error(f"Error en resumen diario Scholar: {e}")
            await context.bot.send_message(
                chat_id=target_chat_id,
                text="Error generando el resumen diario."
            )

    async def send_morning_brief(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Envía el brief de la mañana (agenda + entreno + portfolio) sin alucinar."""
        target_chat_id = None
        if self.allowed_users:
            target_chat_id = self.allowed_users[0]
        else:
            logger.warning("No hay usuarios configurados en TELEGRAM_ALLOWED_USER_IDS para el morning brief.")
            return

        try:
            from src.tools.calendar_mcp import get_today_agenda
            from src.tools.notion_mcp import get_tasks, get_training_for_date, get_portfolio_holdings

            today_str = datetime.now().strftime("%Y-%m-%d")

            agenda = get_today_agenda.invoke({})
            tasks = get_tasks.invoke({"limit": 50})
            trainings = get_training_for_date.invoke({"date": today_str})
            holdings = get_portfolio_holdings.invoke({})

            # Filtrar tasks por due_date hoy
            due_today = []
            if isinstance(tasks, list):
                for t in tasks:
                    if isinstance(t, dict) and t.get("due_date") == today_str and (t.get("status") != "Done"):
                        due_today.append(t)

            # Portfolio stats simples
            total_amount = 0.0
            by_type: dict[str, float] = {}
            if isinstance(holdings, list):
                for h in holdings:
                    if not isinstance(h, dict) or "error" in h:
                        continue
                    amt = float(h.get("amount") or 0)
                    total_amount += amt
                    t = h.get("type") or "Unknown"
                    by_type[t] = by_type.get(t, 0.0) + amt

            def pct(x: float) -> str:
                return "—" if total_amount <= 0 else f"{(x/total_amount)*100:.0f}%"

            # Formato (Telegram Markdown)
            msg = f"""🌅 **Morning Brief** — {today_str}

### 📅 Agenda de hoy
"""
            if isinstance(agenda, dict) and agenda.get("error"):
                msg += f"- **Calendario**: {agenda['error']}\n"
            else:
                events = (agenda or {}).get("events", []) if isinstance(agenda, dict) else []
                if not events:
                    msg += "- No veo eventos hoy.\n"
                else:
                    for ev in events[:8]:
                        msg += f"- {ev.get('title','(sin título)')} ({ev.get('start','?')} → {ev.get('end','?')})\n"
                if isinstance(agenda, dict):
                    msg += f"\n- **Meetings (h)**: {agenda.get('meeting_hours','?')} | **Free (h)**: {agenda.get('free_hours','?')}\n"

            msg += "\n### ✅ Tasks (due hoy)\n"
            if due_today:
                for t in due_today[:8]:
                    pr = t.get("priority") or ""
                    proj = t.get("project") or ""
                    msg += f"- {t.get('title','(sin título)')} {f'[{proj}]' if proj else ''} {f'({pr})' if pr else ''}\n"
            else:
                msg += "- No veo tasks con due date hoy.\n"

            msg += "\n### 🏃 Entreno (hoy)\n"
            if isinstance(trainings, list) and trainings and not trainings[0].get("error"):
                tr = trainings[0]
                msg += (
                    f"- **{tr.get('type','')}** — {tr.get('distance_km','?')} km, "
                    f"{tr.get('time_min','?')} min, {tr.get('pace','?')} | HR {tr.get('hr','?')} | {tr.get('zone','')}\n"
                )
            else:
                # Si DB no está configurada, decirlo explícitamente
                err = trainings[0].get("error") if isinstance(trainings, list) and trainings else None
                msg += f"- {err or 'No hay entreno guardado para hoy.'}\n"

            msg += "\n### 💰 Portfolio (snapshot)\n"
            if total_amount <= 0:
                if isinstance(holdings, list) and holdings and isinstance(holdings[0], dict) and holdings[0].get("error"):
                    msg += f"- {holdings[0]['error']}\n"
                else:
                    msg += "- No hay holdings cargados.\n"
            else:
                msg += f"- **Total**: €{total_amount:,.0f}\n"
                for k, v in sorted(by_type.items(), key=lambda kv: kv[1], reverse=True):
                    msg += f"  - {k}: €{v:,.0f} ({pct(v)})\n"

            await self._send_long_message(target_chat_id, msg, context)
        except Exception as e:
            logger.error(f"Error en morning brief: {e}")
            await context.bot.send_message(chat_id=target_chat_id, text="Error generando el morning brief.")

    def run(self) -> None:
        """Ejecuta el bot en modo polling."""
        logger.info("Iniciando SPESION Telegram Bot...")
        
        app = self.build_application()
        
        logger.info("Bot iniciado. Escuchando mensajes...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    
    async def run_async(self) -> None:
        """Ejecuta el bot de forma asíncrona."""
        logger.info("Iniciando SPESION Telegram Bot (async)...")
        
        app = self.build_application()
        
        async with app:
            await app.start()
            logger.info("Bot iniciado. Escuchando mensajes...")
            await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
            
            # Mantener corriendo
            import asyncio
            while True:
                await asyncio.sleep(3600)


def run_bot() -> None:
    """Función de conveniencia para ejecutar el bot."""
    bot = SpesionBot()
    bot.run()
