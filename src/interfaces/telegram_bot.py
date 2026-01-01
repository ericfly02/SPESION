"""Telegram Bot - Interfaz principal de SPESION via Telegram."""

from __future__ import annotations

import logging
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
        
        # Handler de errores
        app.add_error_handler(self.handle_error)
        
        self._app = app
        return app
    
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
