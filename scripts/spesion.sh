#!/usr/bin/env bash
# =============================================================================
# SPESION 3.0 — Quick Management Commands
# =============================================================================
# Usage: ./scripts/spesion.sh [command]
#
# Commands:
#   start      — Start all services
#   stop       — Stop all services
#   restart    — Restart all services
#   status     — Show container and system status
#   logs       — Follow live logs
#   health     — Quick health check
#   shell      — Open a shell inside SPESION container
#   models     — List Ollama models
#   backup     — Backup data directory
#   update     — Pull latest code, rebuild, restart
#   reflect    — Trigger cognitive reflection
#   tools      — List all registered tools
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# Detect compose files
if [ -f docker/docker-compose.prod.yml ]; then
    COMPOSE_FILES="-f docker/docker-compose.yml -f docker/docker-compose.prod.yml"
else
    COMPOSE_FILES="-f docker/docker-compose.yml"
fi

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

case "${1:-help}" in

    start)
        echo -e "${GREEN}🚀 Starting SPESION...${NC}"
        docker compose $COMPOSE_FILES up -d
        sleep 5
        echo -e "${GREEN}✅ Services started${NC}"
        docker compose $COMPOSE_FILES ps
        ;;

    stop)
        echo -e "${RED}⏹️  Stopping SPESION...${NC}"
        docker compose $COMPOSE_FILES down
        echo -e "${GREEN}✅ All services stopped${NC}"
        ;;

    restart)
        echo -e "${CYAN}🔄 Restarting SPESION...${NC}"
        docker compose $COMPOSE_FILES restart
        echo -e "${GREEN}✅ Restarted${NC}"
        ;;

    status)
        echo -e "${BOLD}📊 Container Status:${NC}"
        docker compose $COMPOSE_FILES ps
        echo ""
        echo -e "${BOLD}🧠 System Status:${NC}"
        docker exec -it spesion python main.py --status 2>/dev/null || echo "  Container not running"
        ;;

    logs)
        echo -e "${CYAN}📋 Following SPESION logs (Ctrl+C to stop)...${NC}"
        docker logs -f spesion --tail 100
        ;;

    health)
        echo -e "${BOLD}❤️ Health Check:${NC}"
        if curl -sf http://localhost:8100/health 2>/dev/null | python3 -m json.tool; then
            echo -e "${GREEN}✅ SPESION is healthy${NC}"
        else
            echo -e "${RED}❌ SPESION is not responding${NC}"
            echo "  Check logs: docker logs spesion --tail 50"
        fi
        ;;

    shell)
        echo -e "${CYAN}🐚 Opening shell in SPESION container...${NC}"
        docker exec -it spesion /bin/bash
        ;;

    models)
        echo -e "${BOLD}🤖 Ollama Models:${NC}"
        docker exec spesion-ollama ollama list
        ;;

    pull-model)
        MODEL="${2:-}"
        if [ -z "$MODEL" ]; then
            echo "Usage: $0 pull-model <model-name>"
            echo "Example: $0 pull-model mistral:7b"
            exit 1
        fi
        echo -e "${CYAN}📥 Pulling model: $MODEL${NC}"
        docker exec spesion-ollama ollama pull "$MODEL"
        ;;

    backup)
        BACKUP_DIR="$PROJECT_DIR/backups"
        mkdir -p "$BACKUP_DIR"
        TIMESTAMP=$(date +%Y%m%d_%H%M%S)
        BACKUP_FILE="$BACKUP_DIR/spesion_backup_$TIMESTAMP.tar.gz"
        
        echo -e "${CYAN}💾 Backing up data...${NC}"
        
        # Copy data from Docker volume
        docker cp spesion:/app/data /tmp/spesion_data_backup 2>/dev/null || true
        
        tar -czf "$BACKUP_FILE" \
            -C /tmp spesion_data_backup \
            -C "$PROJECT_DIR" .env workspace/ 2>/dev/null
        
        rm -rf /tmp/spesion_data_backup
        
        SIZE=$(du -sh "$BACKUP_FILE" | awk '{print $1}')
        echo -e "${GREEN}✅ Backup created: $BACKUP_FILE ($SIZE)${NC}"
        ;;

    update)
        echo -e "${CYAN}🔄 Updating SPESION...${NC}"
        
        # Backup first
        $0 backup
        
        # Pull latest
        git pull origin main 2>/dev/null || echo "  Not a git repo, skipping pull"
        
        # Rebuild and restart
        echo "  Rebuilding containers..."
        docker compose $COMPOSE_FILES build
        docker compose $COMPOSE_FILES up -d
        
        echo -e "${GREEN}✅ Updated and restarted${NC}"
        ;;

    reflect)
        echo -e "${CYAN}🧠 Triggering cognitive reflection...${NC}"
        docker exec -it spesion python main.py --reflect
        ;;

    tools)
        echo -e "${BOLD}🔧 Custom Tools:${NC}"
        docker exec -it spesion python -c "
from src.tools.tool_factory import get_tool_factory
factory = get_tool_factory()
stats = factory.registry.stats()
tools = factory.registry.list_tools(enabled_only=False)
print(f'Total: {stats[\"total_tools\"]} tools, {stats[\"total_uses\"]} uses')
for t in tools:
    status = '✅' if t.enabled else '⏸️'
    print(f'  {status} {t.name} v{t.version} — {t.description[:60]}')
" 2>/dev/null || echo "  No custom tools registered yet"
        ;;

    help|*)
        echo -e "${BOLD}SPESION 3.0 — Management Commands${NC}"
        echo ""
        echo "Usage: $0 <command>"
        echo ""
        echo "Commands:"
        echo "  start       Start all services"
        echo "  stop        Stop all services"
        echo "  restart     Restart all services"
        echo "  status      Show container and system status"
        echo "  logs        Follow live logs"
        echo "  health      Quick health check"
        echo "  shell       Open a shell inside SPESION container"
        echo "  models      List Ollama models"
        echo "  pull-model  Pull a new Ollama model"
        echo "  backup      Backup data + config"
        echo "  update      Pull latest code + rebuild + restart"
        echo "  reflect     Trigger cognitive reflection"
        echo "  tools       List custom tools"
        echo ""
        ;;
esac
