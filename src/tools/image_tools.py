"""Image Tools - extracción de texto (OCR) e interpretación básica de screenshots.

Enfoque:
- OCR local con Tesseract (via pytesseract) para mantener privacidad.
- Devuelve texto plano para que los agentes (Companion/Connector) puedan aconsejar respuestas.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
def extract_text_from_image(file_path: str, lang: str = "spa+eng") -> dict[str, Any]:
    """Extrae texto de una imagen (screenshot) usando OCR local.

    Args:
        file_path: Ruta local de la imagen (png/jpg/jpeg/webp).
        lang: Idiomas de OCR (por defecto español+inglés). Requiere paquetes de idioma en Tesseract.

    Returns:
        Dict con:
        - ok: bool
        - text: str
        - error: str (si ok=false)
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return {"ok": False, "text": "", "error": f"File not found: {file_path}"}

        try:
            from PIL import Image  # type: ignore
        except Exception as e:
            return {
                "ok": False,
                "text": "",
                "error": "Pillow not installed. Install 'pillow' to enable image OCR.",
            }

        try:
            import pytesseract  # type: ignore
        except Exception:
            return {
                "ok": False,
                "text": "",
                "error": "pytesseract not installed. Install 'pytesseract' (and system tesseract-ocr).",
            }

        img = Image.open(path)
        # Convertir a RGB para evitar issues con paletas/alpha
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")

        text = pytesseract.image_to_string(img, lang=lang) or ""
        text = text.strip()
        if not text:
            return {"ok": False, "text": "", "error": "No text detected in image (OCR empty)."}
        return {"ok": True, "text": text}

    except Exception as e:
        logger.error(f"Error extracting image text: {e}")
        return {"ok": False, "text": "", "error": str(e)}


def create_image_tools() -> list:
    return [extract_text_from_image]


