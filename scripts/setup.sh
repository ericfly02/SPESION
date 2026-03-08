#!/usr/bin/env bash
# =============================================================================
# SPESION 2.0 — Server Setup Script
# =============================================================================
# Run on a fresh Ubuntu 22.04+ server or WSL2 instance.
# Usage:  chmod +x scripts/setup.sh && sudo ./scripts/setup.sh
# =============================================================================

set -euo pipefail

echo "══════════════════════════════════════════════════════════"
echo "  SPESION 2.0 — Server Setup"
echo "══════════════════════════════════════════════════════════"

# ─── 1. System packages ─────────────────────────────────────────────────────
echo "[1/7] Installing system packages..."
apt-get update -qq
apt-get install -y -qq \
    docker.io docker-compose-plugin \
    curl git ufw fail2ban \
    tesseract-ocr tesseract-ocr-spa \
    python3 python3-pip python3-venv

# ─── 2. Docker permissions ──────────────────────────────────────────────────
echo "[2/7] Configuring Docker..."
systemctl enable --now docker
usermod -aG docker "${SUDO_USER:-$(whoami)}" 2>/dev/null || true

# ─── 3. Firewall ────────────────────────────────────────────────────────────
echo "[3/7] Configuring firewall..."
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 8100/tcp comment "SPESION API"
# ufw allow 80/tcp comment "HTTP (Traefik)"
# ufw allow 443/tcp comment "HTTPS (Traefik)"
ufw --force enable

# ─── 4. Fail2ban ─────────────────────────────────────────────────────────────
echo "[4/7] Configuring Fail2ban..."
systemctl enable --now fail2ban

# ─── 5. Create directories ──────────────────────────────────────────────────
echo "[5/7] Creating data directories..."
SPESION_DIR="${SPESION_DIR:-/opt/spesion}"
mkdir -p "$SPESION_DIR"/{data/chroma,data/temp,data/backups,data/uploads}

# ─── 6. Pull Ollama models ──────────────────────────────────────────────────
echo "[6/7] Pulling Ollama models (this may take a while)..."
if command -v docker &> /dev/null; then
    docker pull ollama/ollama:latest
    # Start Ollama temporarily to pull models
    docker run -d --name ollama-setup -v ollama-data:/root/.ollama ollama/ollama:latest
    sleep 5
    docker exec ollama-setup ollama pull llama3.2:3b
    docker exec ollama-setup ollama pull qwen2.5:7b
    docker stop ollama-setup && docker rm ollama-setup
    echo "  ✅ Models pulled: llama3.2:3b, qwen2.5:7b"
else
    echo "  ⚠️  Docker not available, skipping model pull"
fi

# ─── 7. Generate API key ────────────────────────────────────────────────────
echo "[7/7] Generating API key..."
API_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
echo ""
echo "══════════════════════════════════════════════════════════"
echo "  ✅ Setup complete!"
echo "══════════════════════════════════════════════════════════"
echo ""
echo "  Generated API key: $API_KEY"
echo ""
echo "  Next steps:"
echo "  1. Copy .env.example to .env and fill in your values"
echo "  2. Set SPESION_API_KEY=$API_KEY in .env"
echo "  3. Run: docker compose -f docker/docker-compose.prod.yml up -d --build"
echo "  4. Test: curl -s http://localhost:8100/api/v1/health"
echo ""
echo "  ⚠️  Log out and back in for Docker group changes."
echo "══════════════════════════════════════════════════════════"
