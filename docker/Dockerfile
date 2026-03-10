# SPESION - Dockerfile Principal
# Imagen base de Python 3.11
FROM python:3.11-slim

# Variables de entorno
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/app/.playwright

# Crear usuario no-root
RUN useradd --create-home --shell /bin/bash spesion

# Instalar dependencias del sistema
# Includes Playwright system deps (libnss3, libatk, etc.) and Tesseract OCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    ffmpeg \
    tesseract-ocr \
    tesseract-ocr-spa \
    tesseract-ocr-eng \
    # Playwright / Chromium deps
    libnss3 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxkbcommon0 \
    libgbm1 \
    libasound2 \
    libxshmfence1 \
    libatspi2.0-0 \
    libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*

# Crear directorio de trabajo
WORKDIR /app

# Copiar requirements primero (para cache de Docker)
COPY requirements.txt .

# Instalar dependencias de Python (incluye autonomous engine)
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir twilio playwright

# Instalar Chromium para Playwright (como root antes de cambiar usuario)
RUN playwright install chromium

# Copiar código fuente
COPY . .

# Crear directorios de datos y logs
RUN mkdir -p \
    /app/data/chroma \
    /app/data/temp \
    /app/data/screenshots \
    /app/logs \
    && chown -R spesion:spesion /app

# Cambiar a usuario no-root
USER spesion

# API server port
EXPOSE 8100

# Health check against the FastAPI /health endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8100/health || exit 1

# Default: unified API server; Telegram/Discord/Heartbeat are launched from
# src.api.server lifespan when related env vars are present.
CMD ["python", "-m", "uvicorn", "src.api.server:app", "--host", "0.0.0.0", "--port", "8100", "--workers", "1"]

