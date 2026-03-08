# SPESION 2.0 — Setup & Deployment Guide

> **Architecture**: FastAPI (brain) + Discord Bot + Telegram Bot + Ollama (local LLM)  
> **Server**: Intel i5-8259U • 16 GB RAM • x64  
> **Stack**: Python 3.11 • LangGraph • ChromaDB • SQLite • Docker

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Pre-requisites](#2-pre-requisites)
3. [Quick Start (Local Dev)](#3-quick-start-local-dev)
4. [Discord Bot Setup](#4-discord-bot-setup)
5. [Production Deployment (Docker)](#5-production-deployment-docker)
6. [Server Hardening](#6-server-hardening)
7. [API Usage](#7-api-usage)
8. [Maintenance & Backups](#8-maintenance--backups)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│                    SPESION 2.0 Server                     │
│                                                          │
│  ┌──────────────────────────────────────────────────┐    │
│  │           FastAPI Server (:8100)                  │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │    │
│  │  │ /chat    │  │ /tools   │  │ /health      │   │    │
│  │  └────┬─────┘  └──────────┘  └──────────────┘   │    │
│  │       │                                          │    │
│  │  ┌────▼────────────────────────────────────┐     │    │
│  │  │  LangGraph Engine (The Octagon)         │     │    │
│  │  │  guard → supervisor → agent → tools     │     │    │
│  │  │  8 agents: scholar, coach, tycoon, ...  │     │    │
│  │  └────┬────────────────────────────────────┘     │    │
│  │       │                                          │    │
│  │  ┌────▼─────┐  ┌───────────┐  ┌────────────┐    │    │
│  │  │ SQLite   │  │ ChromaDB  │  │ Notion API │    │    │
│  │  │ Sessions │  │ RAG/Memory│  │ Tasks/CRM  │    │    │
│  │  └──────────┘  └───────────┘  └────────────┘    │    │
│  └──────────────────────────────────────────────────┘    │
│                                                          │
│  ┌────────────┐  ┌─────────────┐  ┌──────────────┐      │
│  │ Discord Bot│  │ Telegram Bot│  │ Ollama       │      │
│  │ (async)    │  │ (async)     │  │ llama3.2:3b  │      │
│  │ channel→   │  │ /commands   │  │ qwen2.5:7b   │      │
│  │ agent      │  │ voice/photo │  │ :11434       │      │
│  └────────────┘  └─────────────┘  └──────────────┘      │
└──────────────────────────────────────────────────────────┘
```

### What Changed from v1 → v2

| Feature | v1 | v2 |
|---------|----|----|
| Entry point | `main.py` (Telegram-only) | `uvicorn src.api.server:app` (API + all bots) |
| History | In-memory dict (lost on restart) | SQLite persistence |
| Channels | Telegram only | Telegram + Discord + REST API |
| Security | Basic Sentinel PII regex | + Injection guard + rate limiter + API auth |
| User profile | Hardcoded in `prompts.py` | Loaded from `data/user_profile.md` |
| Routing | Supervisor only | + `agent_hint` for forced channel→agent routing |
| Docker | Dev-only compose | Production compose with internal networking |

---

## 2. Pre-requisites

### On your server (Ubuntu 22.04+ or WSL2 on Windows)

```bash
# Docker + Docker Compose
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Python 3.11+ (for local dev only)
sudo apt install python3.11 python3.11-venv

# Ollama (if running natively, not in Docker)
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2:3b
ollama pull qwen2.5:7b
```

### On Windows with Docker Desktop

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/)
2. Enable WSL2 integration in Docker Desktop settings
3. Install Ollama from [ollama.com](https://ollama.com)
4. Pull models: `ollama pull llama3.2:3b && ollama pull qwen2.5:7b`

---

## 3. Quick Start (Local Dev)

```bash
# 1. Clone and enter the project
cd /path/to/SPESION

# 2. Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env — at minimum set:
#   SPESION_API_KEY=<generate with: python -c "import secrets; print(secrets.token_urlsafe(32))">
#   TELEGRAM_BOT_TOKEN=<your token>  (optional)
#   OPENAI_API_KEY=<your key>        (for cloud agents)

# 5. Start Ollama (if not running)
ollama serve &

# 6. Run the API server
uvicorn src.api.server:app --host 0.0.0.0 --port 8100 --reload

# 7. Test
curl http://localhost:8100/api/v1/health
curl -X POST http://localhost:8100/api/v1/chat \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello SPESION", "user_id": "eric"}'
```

### Running the old Telegram-only mode (backward compatible)

```bash
python main.py  # Still works, uses the same LangGraph engine
```

---

## 4. Discord Bot Setup

### Step 1: Create a Discord Application

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **New Application** → name it "SPESION"
3. Go to **Bot** tab → click **Add Bot**
4. Copy the **Token** → paste into `.env` as `DISCORD_BOT_TOKEN`
5. Under **Privileged Gateway Intents**, enable:
   - ✅ Message Content Intent
   - ✅ Server Members Intent

### Step 2: Invite the Bot

1. Go to **OAuth2 → URL Generator**
2. Select scopes: `bot`, `applications.commands`
3. Select permissions: `Send Messages`, `Embed Links`, `Read Message History`, `Use Slash Commands`
4. Copy the generated URL → open in browser → invite to your server

### Step 3: Create Channels

Create these channels in your Discord server (the bot routes by channel name):

| Channel | Agent | Purpose |
|---------|-------|---------|
| `#scholar` | Scholar | Papers, research, news |
| `#coach` | Coach | Fitness, sleep, HRV |
| `#tycoon` | Tycoon | Portfolio, investments |
| `#companion` | Companion | Journal, emotions |
| `#techlead` | TechLead | Code, architecture |
| `#connector` | Connector | Networking, CRM |
| `#executive` | Executive | Calendar, tasks |
| `#sentinel` | Sentinel | Security, system status |
| `#general` | Supervisor | Auto-routes (mention @SPESION) |

### Step 4: Restrict Access

Add your Discord user ID to `.env`:

```env
DISCORD_ALLOWED_USER_IDS=123456789012345678
```

Get your ID: Discord settings → Advanced → Enable Developer Mode → Right-click your name → Copy User ID.

---

## 5. Production Deployment (Docker)

### Build and Launch

```bash
# 1. Configure
cp .env.example .env
nano .env  # Fill in all values

# 2. Build & start
docker compose -f docker/docker-compose.prod.yml up -d --build

# 3. Pull Ollama models (first time only)
docker exec spesion-ollama ollama pull llama3.2:3b
docker exec spesion-ollama ollama pull qwen2.5:7b

# 4. Verify
docker compose -f docker/docker-compose.prod.yml ps
curl http://localhost:8100/api/v1/health
```

### Resource Usage on i5-8259U / 16GB

| Service | RAM | CPU |
|---------|-----|-----|
| Ollama (llama3.2:3b idle) | ~200MB | 0% |
| Ollama (qwen2.5:7b inference) | ~5GB | 100% (burst) |
| SPESION app | ~400MB | <5% |
| ChromaDB (embedded) | ~100MB | <1% |
| **Total (idle)** | **~700MB** | **<5%** |
| **Total (peak inference)** | **~6GB** | **100%** |

You have plenty of headroom with 16GB.

### Logs

```bash
# All services
docker compose -f docker/docker-compose.prod.yml logs -f

# Just SPESION
docker compose -f docker/docker-compose.prod.yml logs -f spesion

# Just Ollama
docker compose -f docker/docker-compose.prod.yml logs -f ollama
```

---

## 6. Server Hardening

### Firewall (UFW)

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 8100/tcp  # API (remove if behind Traefik)
sudo ufw enable
```

### Fail2ban

```bash
sudo apt install fail2ban
sudo systemctl enable --now fail2ban
```

### HTTPS with Traefik (optional, needs a domain)

Uncomment the Traefik section in `docker/docker-compose.prod.yml` and set:

```env
ACME_EMAIL=you@example.com
```

### VPN Access (Tailscale — recommended)

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
# Now access SPESION at http://<tailscale-ip>:8100 from anywhere
```

---

## 7. API Usage

All endpoints require `Authorization: Bearer <SPESION_API_KEY>`.

### Chat

```bash
curl -X POST http://localhost:8100/api/v1/chat \
  -H "Authorization: Bearer $SPESION_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "¿Cómo va mi portfolio?",
    "user_id": "eric",
    "agent_hint": "tycoon"
  }'
```

Response:
```json
{
  "response": "Tu portfolio tiene...",
  "agent": "tycoon",
  "session_id": "abc-123-..."
}
```

### List Tools

```bash
curl http://localhost:8100/api/v1/tools \
  -H "Authorization: Bearer $SPESION_API_KEY"
```

### Invoke a Tool Directly

```bash
curl -X POST http://localhost:8100/api/v1/tools/get_recent_papers \
  -H "Authorization: Bearer $SPESION_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"args": {"days": 7, "max_results": 5, "categories": ["cs.AI"]}}'
```

### Health Check (no auth required)

```bash
curl http://localhost:8100/api/v1/health
```

---

## 8. Maintenance & Backups

### Automated Backups

```bash
chmod +x scripts/backup.sh

# Add to crontab (daily at 3 AM)
(crontab -l 2>/dev/null; echo "0 3 * * * /opt/spesion/scripts/backup.sh") | crontab -
```

This backs up:
- `sessions.db` (conversation history)
- `chroma/` (RAG memory)
- `user_profile.md` (personal config)
- `.env` (credentials, chmod 600)

Backups older than 14 days are auto-pruned.

### Update SPESION

```bash
cd /path/to/SPESION
git pull
docker compose -f docker/docker-compose.prod.yml up -d --build
```

### Update Ollama Models

```bash
docker exec spesion-ollama ollama pull llama3.2:3b
docker exec spesion-ollama ollama pull qwen2.5:7b
```

---

## 9. Troubleshooting

### "SPESION_API_KEY is not set"

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
# Copy output to .env as SPESION_API_KEY=...
```

### Ollama not connecting

```bash
# Check if Ollama is running
docker exec spesion-ollama ollama list

# If empty, pull models
docker exec spesion-ollama ollama pull llama3.2:3b
```

### Discord bot not responding

1. Check `DISCORD_BOT_TOKEN` is set in `.env`
2. Check Message Content Intent is enabled in Discord Developer Portal
3. Check `DISCORD_ALLOWED_USER_IDS` includes your ID
4. Check logs: `docker compose -f docker/docker-compose.prod.yml logs spesion | grep -i discord`

### Telegram bot not responding

1. Check `TELEGRAM_BOT_TOKEN` is set in `.env`
2. Check `TELEGRAM_ALLOWED_USER_IDS` includes your Telegram ID
3. Check you talked to the bot first (`/start`)

### Out of memory

Your i5-8259U has 16GB. If running qwen2.5:7b + Chrome + other apps:

```bash
# Switch to lighter model in .env
OLLAMA_MODEL_HEAVY=llama3.2:3b
```

### Reset conversation history

```bash
# Delete the sessions database
rm data/sessions.db
# Restart
docker compose -f docker/docker-compose.prod.yml restart spesion
```

---

## Quick Reference

| Command | Description |
|---------|-------------|
| `./scripts/start.sh` | Build & start everything |
| `./scripts/backup.sh` | Backup data + credentials |
| `docker compose -f docker/docker-compose.prod.yml logs -f` | Watch logs |
| `docker compose -f docker/docker-compose.prod.yml down` | Stop everything |
| `docker compose -f docker/docker-compose.prod.yml restart` | Restart |
| `curl localhost:8100/api/v1/health` | Health check |
| `python main.py` | Legacy Telegram-only mode |
