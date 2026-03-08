#!/usr/bin/env bash
# =============================================================================
# SPESION 2.0 — Start / Restart
# =============================================================================
# Usage:  chmod +x scripts/start.sh && ./scripts/start.sh
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

echo "══════════════════════════════════════════════════════════"
echo "  SPESION 2.0 — Starting"
echo "══════════════════════════════════════════════════════════"

# Check .env exists
if [ ! -f .env ]; then
    echo "❌ .env file not found! Copy .env.example to .env first."
    exit 1
fi

# Check API key is set
if grep -q "SPESION_API_KEY=change-me" .env; then
    echo "❌ SPESION_API_KEY is still the default value!"
    echo "   Generate one: python3 -c \"import secrets; print(secrets.token_urlsafe(32))\""
    exit 1
fi

# Build and start
echo "[1/3] Building containers..."
docker compose -f docker/docker-compose.prod.yml build

echo "[2/3] Starting services..."
docker compose -f docker/docker-compose.prod.yml up -d

echo "[3/3] Waiting for health check..."
sleep 10

# Health check
if curl -sf http://localhost:8100/api/v1/health > /dev/null 2>&1; then
    echo ""
    echo "✅ SPESION 2.0 is running!"
    echo ""
    curl -s http://localhost:8100/api/v1/health | python3 -m json.tool
else
    echo ""
    echo "⚠️  API not responding yet. Check logs:"
    echo "   docker compose -f docker/docker-compose.prod.yml logs -f spesion"
fi

echo ""
echo "══════════════════════════════════════════════════════════"
echo "  Useful commands:"
echo "  • Logs:    docker compose -f docker/docker-compose.prod.yml logs -f"
echo "  • Stop:    docker compose -f docker/docker-compose.prod.yml down"
echo "  • Restart: docker compose -f docker/docker-compose.prod.yml restart"
echo "  • Health:  curl http://localhost:8100/api/v1/health"
echo "══════════════════════════════════════════════════════════"
