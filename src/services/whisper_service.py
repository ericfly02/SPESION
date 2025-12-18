"""Whisper Service - Transcripción de voz usando faster-whisper local."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class WhisperService:
    """Servicio de transcripción de voz usando faster-whisper.
    
    Optimizado para funcionar en CPU con el hardware del usuario
    (Intel i5-8259U, 16GB RAM).
    """
    
    def __init__(
        self,
        model_size: str | None = None,
        device: str | None = None,
        compute_type: str | None = None,
        language: str | None = None,
    ) -> None:
        """Inicializa el servicio de Whisper.
        
        Args:
            model_size: Tamaño del modelo (tiny, base, small, medium, large-v3)
            device: Dispositivo (cpu, cuda, auto)
            compute_type: Tipo de computación (int8, float16, float32)
            language: Idioma por defecto
        """
        from src.core.config import settings
        
        self.model_size = model_size or settings.whisper.model_size
        self.device = device or settings.whisper.device
        self.compute_type = compute_type or settings.whisper.compute_type
        self.language = language or settings.whisper.language
        
        self._model: Any = None
        
        logger.info(
            f"WhisperService configurado: model={self.model_size}, "
            f"device={self.device}, compute_type={self.compute_type}"
        )
    
    @property
    def model(self) -> Any:
        """Modelo de Whisper (lazy loading)."""
        if self._model is None:
            self._load_model()
        return self._model
    
    def _load_model(self) -> None:
        """Carga el modelo de Whisper."""
        try:
            from faster_whisper import WhisperModel
            
            logger.info(f"Cargando modelo Whisper {self.model_size}...")
            
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
            
            logger.info("Modelo Whisper cargado exitosamente")
            
        except ImportError:
            logger.error(
                "faster-whisper no instalado. "
                "Instalar con: pip install faster-whisper"
            )
            raise
        except Exception as e:
            logger.error(f"Error cargando modelo Whisper: {e}")
            raise
    
    def transcribe(
        self,
        audio_path: str | Path,
        language: str | None = None,
        task: str = "transcribe",
    ) -> dict[str, Any]:
        """Transcribe un archivo de audio.
        
        Args:
            audio_path: Ruta al archivo de audio
            language: Idioma del audio (None para auto-detectar)
            task: "transcribe" o "translate" (a inglés)
            
        Returns:
            Diccionario con texto, idioma detectado y segmentos
        """
        audio_path = Path(audio_path)
        
        if not audio_path.exists():
            raise FileNotFoundError(f"Archivo de audio no encontrado: {audio_path}")
        
        logger.info(f"Transcribiendo: {audio_path}")
        
        language = language or self.language
        
        segments, info = self.model.transcribe(
            str(audio_path),
            language=language,
            task=task,
            beam_size=5,
            vad_filter=True,  # Filtrar silencio
            vad_parameters=dict(
                min_silence_duration_ms=500,
            ),
        )
        
        # Procesar segmentos
        all_segments = []
        full_text_parts = []
        
        for segment in segments:
            all_segments.append({
                "start": segment.start,
                "end": segment.end,
                "text": segment.text.strip(),
            })
            full_text_parts.append(segment.text.strip())
        
        full_text = " ".join(full_text_parts)
        
        result = {
            "text": full_text,
            "language": info.language,
            "language_probability": info.language_probability,
            "duration": info.duration,
            "segments": all_segments,
        }
        
        logger.info(
            f"Transcripción completada: {len(full_text)} chars, "
            f"idioma={info.language} ({info.language_probability:.2%})"
        )
        
        return result
    
    def transcribe_bytes(
        self,
        audio_bytes: bytes,
        file_extension: str = ".ogg",
        language: str | None = None,
    ) -> dict[str, Any]:
        """Transcribe audio desde bytes (útil para Telegram).
        
        Args:
            audio_bytes: Bytes del archivo de audio
            file_extension: Extensión del archivo
            language: Idioma del audio
            
        Returns:
            Diccionario con transcripción
        """
        # Crear archivo temporal
        with tempfile.NamedTemporaryFile(
            suffix=file_extension,
            delete=False,
        ) as tmp_file:
            tmp_file.write(audio_bytes)
            tmp_path = Path(tmp_file.name)
        
        try:
            result = self.transcribe(tmp_path, language=language)
        finally:
            # Limpiar archivo temporal
            tmp_path.unlink(missing_ok=True)
        
        return result
    
    async def transcribe_async(
        self,
        audio_path: str | Path,
        language: str | None = None,
    ) -> dict[str, Any]:
        """Versión asíncrona de transcribe.
        
        Ejecuta la transcripción en un thread pool para no bloquear
        el event loop.
        
        Args:
            audio_path: Ruta al archivo de audio
            language: Idioma del audio
            
        Returns:
            Diccionario con transcripción
        """
        import asyncio
        
        loop = asyncio.get_event_loop()
        
        result = await loop.run_in_executor(
            None,
            lambda: self.transcribe(audio_path, language),
        )
        
        return result
    
    async def transcribe_bytes_async(
        self,
        audio_bytes: bytes,
        file_extension: str = ".ogg",
        language: str | None = None,
    ) -> dict[str, Any]:
        """Versión asíncrona de transcribe_bytes.
        
        Args:
            audio_bytes: Bytes del archivo de audio
            file_extension: Extensión del archivo
            language: Idioma del audio
            
        Returns:
            Diccionario con transcripción
        """
        import asyncio
        
        loop = asyncio.get_event_loop()
        
        result = await loop.run_in_executor(
            None,
            lambda: self.transcribe_bytes(audio_bytes, file_extension, language),
        )
        
        return result
    
    def get_supported_languages(self) -> list[str]:
        """Retorna lista de idiomas soportados."""
        # Idiomas principales soportados por Whisper
        return [
            "en", "es", "fr", "de", "it", "pt", "nl", "pl", "ru",
            "zh", "ja", "ko", "ar", "hi", "tr", "vi", "th", "id",
            "ca", "eu", "gl",  # Catalán, Euskera, Gallego
        ]
    
    def is_available(self) -> bool:
        """Verifica si el servicio está disponible."""
        try:
            _ = self.model
            return True
        except Exception:
            return False


# Singleton
_whisper_service: WhisperService | None = None


def get_whisper_service() -> WhisperService:
    """Obtiene la instancia singleton del WhisperService."""
    global _whisper_service
    if _whisper_service is None:
        _whisper_service = WhisperService()
    return _whisper_service

