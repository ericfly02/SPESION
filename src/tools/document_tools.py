"""Document Tools - extracción y normalización de contenido de documentos.

Objetivo:
- Permitir que SPESION pueda "leer" documentos subidos por Telegram (PDF, txt, md, csv)
  y pasar un texto limpio al LLM para análisis y memoria.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


def _safe_read_text(path: Path, max_chars: int) -> str:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if len(text) > max_chars:
        return text[:max_chars] + "\n\n[TRUNCATED]"
    return text


def _extract_pdf_text(path: Path, max_chars: int) -> str:
    # Prefer pypdf (ligero). Si no está instalado, pedimos instalación.
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "PDF support not available. Install 'pypdf' to enable PDF parsing."
        ) from e

    reader = PdfReader(str(path))
    out = []
    total = 0
    for page in reader.pages:
        page_text = page.extract_text() or ""
        if not page_text.strip():
            continue
        out.append(page_text)
        total += len(page_text)
        if total >= max_chars:
            break
    text = "\n\n".join(out).strip()
    if not text:
        return ""
    if len(text) > max_chars:
        return text[:max_chars] + "\n\n[TRUNCATED]"
    return text


@tool
def extract_text_from_document(file_path: str, max_chars: int = 30000) -> dict[str, Any]:
    """Extrae texto de un documento local (PDF/txt/md/csv).

    Args:
        file_path: Ruta absoluta o relativa dentro del workspace.
        max_chars: Límite de caracteres devueltos para evitar prompts enormes.

    Returns:
        Dict con:
        - ok: bool
        - type: extensión detectada
        - text: contenido extraído (posiblemente truncado)
        - error: str (si ok=false)
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return {"ok": False, "error": f"File not found: {file_path}", "type": None, "text": ""}

        ext = path.suffix.lower().lstrip(".")

        if ext in {"txt", "md"}:
            return {"ok": True, "type": ext, "text": _safe_read_text(path, max_chars)}

        if ext == "csv":
            # CSV como texto (primeros max_chars)
            return {"ok": True, "type": ext, "text": _safe_read_text(path, max_chars)}

        if ext == "pdf":
            text = _extract_pdf_text(path, max_chars=max_chars)
            if not text:
                return {
                    "ok": False,
                    "type": ext,
                    "text": "",
                    "error": "No text extracted from PDF (maybe scanned image). Consider OCR.",
                }
            return {"ok": True, "type": ext, "text": text}

        return {"ok": False, "type": ext, "text": "", "error": f"Unsupported file type: {ext}"}

    except Exception as e:
        logger.error(f"Error extracting document text: {e}")
        return {"ok": False, "type": None, "text": "", "error": str(e)}


def create_document_tools() -> list:
    return [extract_text_from_document]


