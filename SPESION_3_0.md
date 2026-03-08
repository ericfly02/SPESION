# SPESION 3.0 — Complete Reference

> **Your personal AGI operating system.** SPESION runs 24/7, learns from every interaction, manages your finances, health, calendar, knowledge, and code — all from Telegram or Discord.

---

## Table of Contents

1. [What's New in 3.0](#whats-new-in-30)
2. [Architecture Overview](#architecture-overview)
3. [Agent Roster & Model Routing](#agent-roster--model-routing)
4. [How Agents Learn (SkillStore)](#how-agents-learn-skillstore)
5. [Memory Subsystems](#memory-subsystems)
6. [Environment Variables Reference](#environment-variables-reference)
7. [Telegram Setup](#telegram-setup)
8. [Discord Setup](#discord-setup)
9. [Google Calendar Setup](#google-calendar-setup)
10. [Garmin Setup](#garmin-setup)
11. [IBKR (Interactive Brokers) Setup](#ibkr-interactive-brokers-setup)
12. [Notion Setup](#notion-setup)
13. [First-Run Checklist](#first-run-checklist)
14. [CLI Commands](#cli-commands)
15. [Windows 11 PowerShell Start Guide](#windows-11-powershell-start-guide)
16. [Docker Deployment](#docker-deployment)
17. [Upgrading from 2.0](#upgrading-from-20)

---

## What's New in 3.0

| Feature | 2.0 | 3.0 |
|---------|-----|-----|
| Models | Single (GPT-4o) | **11 models, auto-routed by task complexity** |
| Agent learning | ❌ | ✅ **SkillStore — agents remember how to do tasks** |
| Memory | Single vector store | **3-tier: Episodic + Semantic + Skills (SQLite + Chroma)** |
| Cognitive loop | ❌ | ✅ **Nightly reflection, pattern detection, idea generation** |
| Heartbeat | ❌ | ✅ **Cron-like scheduler: daily digest, weekly review** |
| Context compaction | ❌ | ✅ **Auto-compresses long conversations (6000 token budget)** |
| Workspace bootstrap | ❌ | ✅ **SOUL.md, IDENTITY.md, AGENTS.md — SPESION knows itself** |
| Google Calendar | Basic | **JSON token (Windows-safe) + 7 tools (view/create/edit/delete)** |
| Garmin | Basic | **Auto-reconnect + weekly summary + HRV tracking** |
| IBKR | Sync only | **Connection check + open positions tool** |
| Notion | Basic CRUD | **18 tools + connection health check + 7 database types** |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     INTERFACES LAYER                        │
│   Telegram Bot  ◄──────────────────────►  Discord Bot       │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                   SPESION CORE (LangGraph)                   │
│                                                              │
│   ┌─────────────┐    ┌──────────────┐   ┌───────────────┐  │
│   │  Supervisor  │    │ ModelRouter  │   │ WorkspaceLdr  │  │
│   │ (llama3.2:3b)│    │  (11 models) │   │  (SOUL.md etc)│  │
│   └──────┬──────┘    └──────────────┘   └───────────────┘  │
│          │                                                    │
│   ┌──────▼──────────────────────────────────────────────┐   │
│   │              AGENT LAYER (8 agents)                  │   │
│   │  companion │ executive │ scholar │ tycoon │ coach    │   │
│   │  techlead  │ sentinel  │ connector                   │   │
│   └──────┬──────────────────────────────────────────────┘   │
│          │                                                    │
│   ┌──────▼──────────────────────────────────────────────┐   │
│   │                  MEMORY LAYER                        │   │
│   │   EvolvingMemory (SQLite) │ VectorStore (Chroma)    │   │
│   │   SkillStore (SQLite WAL) │ CognitiveLoop           │   │
│   └──────┬──────────────────────────────────────────────┘   │
│          │                                                    │
│   ┌──────▼──────────────────────────────────────────────┐   │
│   │               TOOLS / INTEGRATIONS                  │   │
│   │  Google Calendar │ Garmin │ IBKR │ Notion          │   │
│   │  GitHub │ Search │ Finance │ Code Sandbox │ Arxiv   │   │
│   └─────────────────────────────────────────────────────┘   │
│                                                              │
│   HeartbeatRunner ──► daily_digest, weekly_review, reflect  │
└─────────────────────────────────────────────────────────────┘
```

---

## Agent Roster & Model Routing

SPESION uses a **ModelRouter** that selects the best model per task based on complexity, privacy, and cost weights.

### Agent Table

| Agent | Role | Default Model | Fallback | Privacy |
|-------|------|---------------|----------|---------|
| **companion** | Daily assistant, emotional support | `llama3.2:3b` (local) | — | 🔒 Local only |
| **supervisor** | Routes tasks to correct agent | `llama3.2:3b` (local) | — | 🔒 Local only |
| **sentinel** | Security & monitoring alerts | `llama3.2:3b` (local) | — | 🔒 Local only |
| **coach** | Health, fitness, Garmin coaching | `llama3.2:3b` (local) | — | 🔒 Local only |
| **connector** | Contacts, CRM, relationships | `qwen2.5:7b` (local) | `gpt-4o-mini` | ⚖️ Moderate |
| **executive** | Calendar, tasks, Notion management | `qwen2.5:7b` (local) | `gpt-4o-mini` | ⚖️ Moderate |
| **scholar** | Research, papers, deep analysis | `gpt-4o` | `claude-sonnet-4` | ☁️ Cloud |
| **tycoon** | Finance, IBKR, portfolio, crypto | `gpt-4o` | `claude-sonnet-4` | ☁️ Cloud |
| **techlead** | Code, GitHub, architecture | `gpt-4o` | `claude-sonnet-4` | ☁️ Cloud |

### How the ModelRouter Works

```
User message → Supervisor (llama3.2:3b) → picks agent
                                              │
                                        ModelRouter
                                              │
                              ┌───────────────┼───────────────┐
                         complexity?     privacy?         cost limit?
                              │               │                │
                           SIMPLE         LOCAL ONLY        CHEAP
                        qwen2.5:7b      llama3.2:3b       gpt-4o-mini
                              │
                          COMPLEX
                           gpt-4o
                              │
                         REASONING
                           o3-mini
```

The router also tracks **model health** — if a provider returns 429 or 503, the router backs off and auto-switches to the fallback for 5 minutes.

---

## How Agents Learn (SkillStore)

SPESION 3.0 agents accumulate **reusable task patterns** over time using the `SkillStore`.

### The Skill Lifecycle

```
1. USER asks something → agent answers successfully
         │
         ▼
2. LLM extracts a "Skill" pattern from the interaction:
   {
     "name": "Add Google Calendar Event",
     "trigger_keywords": ["calendar", "schedule", "appointment"],
     "steps": "1. Parse date/time...\n2. Call create_calendar_event...",
     "outcome_hint": "Returns confirmation with event ID"
   }
         │
         ▼
3. Skill saved to data/skill_store.db (SQLite WAL)
   with confidence = 0.55
         │
         ▼
4. NEXT TIME user asks something similar:
   SkillStore.recall(agent="executive", query="add meeting tomorrow") 
   → Jaccard similarity: query_words ∩ trigger_keywords
   → Returns top-3 skills as context before LLM call
         │
         ▼
5. Agent sees: "## 🛠️ LEARNED SKILLS" block in system prompt
   → Uses the steps as a guide
         │
         ▼
6. Success → mark_success() → confidence += 0.05
   Failure → mark_failure() → confidence -= 0.08
         │
         ▼
7. Low-confidence skills (< 0.1 after 3+ uses) auto-pruned nightly
```

### Skill Database Location

```
data/skill_store.db    ← SQLite, WAL mode, auto-created
```

You can inspect skills:
```bash
sqlite3 data/skill_store.db "SELECT agent, name, confidence, use_count FROM skills ORDER BY confidence DESC"
```

---

## Memory Subsystems

SPESION has three independent memory layers:

### 1. Episodic Memory (`data/memory_bank.db`)
- Every conversation is saved with timestamp, agent, user_id
- Daily logs summarized each night by `CognitiveLoop`
- Recall: semantic search over recent logs

### 2. Semantic Memory (`data/chroma_db/`)
- ChromaDB vector store (persistent)
- Documents, knowledge pills, important facts
- Used by `scholar` and `techlead` for RAG
- Added via `create_knowledge_pill` Notion tool or directly via API

### 3. Skill Memory (`data/skill_store.db`)
- SQLite WAL — concurrent reads during inference
- Stores task patterns (how to do things)
- See "How Agents Learn" above

### 4. Workspace Identity (`workspace/`)
- `SOUL.md` — SPESION's values and personality core
- `IDENTITY.md` — WHO it is (your personal AI OS)
- `AGENTS.md` — what each agent does
- `BOOTSTRAP.md` — startup checklist run at launch
- `HEARTBEAT.md` — what tasks to run on schedule
- `MEMORY.md` — what to remember across sessions
- These files are loaded by `WorkspaceLoader` and injected into every agent's system prompt

---

## Environment Variables Reference

Copy `.env.example` → `.env` and fill in all values.

### Core

```env
# LLM Providers — add whichever you use
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Ollama (local models — must be running)
OLLAMA_BASE_URL=http://localhost:11434   # default

# Model overrides (optional, ModelRouter picks automatically)
DEFAULT_MODEL=gpt-4o-mini
LOCAL_MODEL=llama3.2:3b
HEAVY_LOCAL_MODEL=qwen2.5:7b
```

### Telegram

```env
TELEGRAM_BOT_TOKEN=1234567890:AAE...
TELEGRAM_ALLOWED_USER_IDS=123456789,987654321   # comma-separated Telegram user IDs
```

### Discord

```env
DISCORD_BOT_TOKEN=OTk...
DISCORD_GUILD_ID=1234567890123456789
# Channel → Agent mapping (optional — defaults to companion for all)
DISCORD_CHANNEL_COMPANION=general
DISCORD_CHANNEL_TYCOON=finance
DISCORD_CHANNEL_SCHOLAR=research
DISCORD_CHANNEL_TECHLEAD=code
DISCORD_CHANNEL_COACH=health
```

### Google Calendar

```env
# Path to your OAuth credentials JSON (downloaded from Google Cloud Console)
GOOGLE_CREDENTIALS_PATH=./data/google_calendar_credentials.json

# Token is auto-generated on first run at:
# ./data/google_token.json  (JSON format, Windows-safe)
```

### Garmin

```env
GARMIN_USERNAME=you@email.com
GARMIN_PASSWORD=yourpassword
# MFA: if your account has 2FA, Garmin Connect will prompt at first login.
# SPESION detects MFA and gives you a clear error message with instructions.
```

### IBKR (Interactive Brokers)

```env
IBKR_FLEX_TOKEN=123456789012345678   # 18-digit token from IBKR Account Management
IBKR_FLEX_QUERY_ID=1234567           # 7-digit query ID from Flex Query setup
```

### Notion

```env
NOTION_API_KEY=secret_...

# Database IDs — get these from each database's URL in Notion
# URL format: https://notion.so/{WORKSPACE}/{DATABASE_ID}?v=...
NOTION_TASKS_DATABASE_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
NOTION_JOURNAL_DATABASE_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
NOTION_CRM_DATABASE_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
NOTION_BOOKS_DATABASE_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
NOTION_TRAININGS_DATABASE_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
NOTION_FINANCE_DATABASE_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
NOTION_TRANSACTIONS_DATABASE_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### App Settings

```env
# Server
API_HOST=0.0.0.0
API_PORT=8100
LOG_LEVEL=INFO

# Memory
MEMORY_RETENTION_DAYS=90
SKILL_STORE_PATH=./data/skill_store.db
VECTOR_STORE_PATH=./data/chroma_db

# Heartbeat
HEARTBEAT_ENABLED=true
HEARTBEAT_DAILY_HOUR=7      # 7 AM daily digest
HEARTBEAT_WEEKLY_WEEKDAY=0  # 0=Monday weekly review

# Cognitive Loop
COGNITIVE_LOOP_ENABLED=true
COGNITIVE_LOOP_HOUR=23      # 11 PM nightly reflection
```

---

## Telegram Setup

### Step 1: Create your bot

1. Open Telegram, search for `@BotFather`
2. Send `/newbot`
3. Choose a name: `SPESION`
4. Choose a username: `spesion_yourname_bot`
5. Copy the **token** → `TELEGRAM_BOT_TOKEN` in `.env`

### Step 2: Get your user ID

1. Search for `@userinfobot` in Telegram
2. Send `/start`
3. Copy your **id** number → `TELEGRAM_ALLOWED_USER_IDS` in `.env`

### Step 3: Configure commands (optional but recommended)

Send to BotFather:
```
/setcommands
```
Then paste:
```
start - Start SPESION
status - System status
help - Show available agents
clear - Clear conversation memory
reflect - Trigger nightly reflection now
```

### Step 4: Set bot description

```
/setdescription
Your personal AGI OS — finance, health, calendar, research, code.
```

### Usage

- Just send a message. SPESION's supervisor routes it to the right agent.
- Mention agents explicitly: `@tycoon what's my portfolio doing?`
- Send voice messages — Whisper transcribes them automatically (if configured)
- Send images — vision models analyse them

---

## Discord Setup

### Step 1: Create the Application

1. Go to https://discord.com/developers/applications
2. Click **New Application** → name it `SPESION`
3. Go to **Bot** tab → click **Add Bot**
4. Under **Token**, click **Reset Token** → copy it → `DISCORD_BOT_TOKEN` in `.env`
5. Enable **Privileged Gateway Intents**:
   - ✅ Server Members Intent
   - ✅ Message Content Intent

### Step 2: Invite to your server

1. Go to **OAuth2 → URL Generator**
2. Scopes: `bot`, `applications.commands`
3. Bot Permissions: `Send Messages`, `Read Message History`, `Use Slash Commands`, `Embed Links`, `Attach Files`
4. Copy the generated URL → open in browser → select your server

### Step 3: Get your server (guild) ID

1. Enable Developer Mode in Discord: Settings → Advanced → Developer Mode ✅
2. Right-click your server name → **Copy ID** → `DISCORD_GUILD_ID` in `.env`

### Step 4: Map channels to agents (optional)

By default every channel uses `companion`. Set channel names in `.env`:

```env
DISCORD_CHANNEL_TYCOON=finance        # #finance → tycoon agent
DISCORD_CHANNEL_SCHOLAR=research      # #research → scholar agent
DISCORD_CHANNEL_TECHLEAD=engineering  # #engineering → techlead agent
DISCORD_CHANNEL_COACH=health          # #health → coach agent
DISCORD_CHANNEL_EXECUTIVE=planning    # #planning → executive agent
```

### Usage

- Message in any channel — SPESION responds
- `/status` — system health
- `/reflect` — trigger cognitive loop now
- `/clear` — reset memory for this user

---

## Google Calendar Setup

### Step 1: Create OAuth Credentials

1. Go to https://console.cloud.google.com
2. Create a new project (or use existing)
3. Enable **Google Calendar API**: APIs & Services → Library → search "Google Calendar API" → Enable
4. Go to **APIs & Services → Credentials**
5. Click **Create Credentials → OAuth client ID**
6. Application type: **Desktop app**
7. Name: `SPESION`
8. Click **Download JSON**
9. Save the file to `data/google_calendar_credentials.json`

### Step 2: Configure OAuth consent screen

1. APIs & Services → OAuth consent screen
2. User type: **External** (for personal use)
3. Add your email as a test user
4. Scopes: add `https://www.googleapis.com/auth/calendar`

### Step 3: First run authentication

Run SPESION once in CLI mode:
```bash
python main.py --cli
```
Ask it: `"what's on my calendar today?"`

A browser window will open → log in with Google → grant permission.

The token is saved to `data/google_token.json` (JSON format, works on Windows and Mac).

> **Token migration**: If you had a `.pickle` token from SPESION 2.0, it is automatically migrated to `.json` on first run.

### Available Calendar Tools

| Tool | What it does |
|------|-------------|
| `get_calendar_events` | List events in a date range |
| `get_today_agenda` | Today's full schedule |
| `get_week_agenda` | Monday–Sunday view with heavy day detection |
| `create_calendar_event` | Create new event with title/time/location |
| `update_calendar_event` | Edit existing event |
| `delete_calendar_event` | Remove event by ID |
| `find_free_slots` | Find open blocks in your week |

---

## Garmin Setup

### Step 1: Credentials

Add to `.env`:
```env
GARMIN_USERNAME=your.email@example.com
GARMIN_PASSWORD=yourgarminpassword
```

### Step 2: MFA / Two-Factor Authentication

If your Garmin account has **2FA enabled**:

1. SPESION will detect this on first connection and return:
   ```
   Garmin requires MFA/2FA. Please:
   1. Temporarily disable 2FA on connect.garmin.com
   2. Restart SPESION to connect
   3. Re-enable 2FA afterwards
   ```
2. Go to https://connect.garmin.com → Settings → Security → disable 2FA
3. Restart SPESION — it will connect and cache the session
4. Re-enable 2FA

> **Note**: Sessions auto-refresh. SPESION uses `_garmin_call()` which auto-reconnects if the session expires (401/session errors).

### Available Garmin Tools

| Tool | What it does |
|------|-------------|
| `get_garmin_stats` | Steps, calories, HR for a specific date |
| `get_garmin_activities` | Recent activities (runs, rides, etc.) |
| `get_training_status` | Training load, readiness score |
| `get_garmin_weekly_summary` | 7-day summary with HRV, sleep, steps totals |
| `check_garmin_connection` | Health check — verify credentials work |

**Example questions:**
- *"How did I sleep this week?"*
- *"What's my training load?"*
- *"Summarize my fitness this week"*
- *"Check if Garmin is connected"*

---

## IBKR (Interactive Brokers) Setup

SPESION uses **Flex Web Service** — a read-only API that exports your account data. No trading API required.

### Step 1: Enable Flex Web Service

1. Log in to https://www.interactivebrokers.com/sso/Login
2. Go to **Account Management → Reports → Flex Queries**
3. In the top-right, click **Flex Web Service** (or search it)
4. Generate a **Flex Token** (18-digit number) → `IBKR_FLEX_TOKEN`

### Step 2: Create a Flex Query

1. Still in **Reports → Flex Queries → Activity Flex Query**
2. Click **+** to create new query
3. Configure:
   - **Date Range**: Last 365 Days
   - **Sections**: Trades, Open Positions, Portfolio, Cash Balances
   - **Format**: XML
4. Save and note the **Query ID** (7-digit number) → `IBKR_FLEX_QUERY_ID`

### Step 3: Add to .env

```env
IBKR_FLEX_TOKEN=123456789012345678
IBKR_FLEX_QUERY_ID=1234567
```

### Step 4: Test connection

In Telegram/Discord:
```
Check IBKR connection
```

The `tycoon` agent will run `check_ibkr_connection` and confirm or show the error.

### Available IBKR Tools

| Tool | What it does |
|------|-------------|
| `sync_investments_to_notion` | Full sync of trades/portfolio → Notion databases |
| `check_ibkr_connection` | Validates token + query ID with a live API call |

---

## Notion Setup

### Step 1: Create an Integration

1. Go to https://www.notion.so/my-integrations
2. Click **+ New integration**
3. Name: `SPESION`
4. Associated workspace: select yours
5. Capabilities: ✅ Read content, ✅ Update content, ✅ Insert content
6. Click **Submit** → copy the **Internal Integration Token** → `NOTION_API_KEY`

### Step 2: Share databases with SPESION

For **each database** you want SPESION to access:
1. Open the database in Notion
2. Click `...` (top-right) → **Connections** → find `SPESION` → **Connect**

### Step 3: Get Database IDs

From any database URL:
```
https://www.notion.so/workspace/XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX?v=...
                               ↑ This 32-char hex string is the database ID
```

Add each to `.env` (with or without dashes — SPESION normalizes automatically):
```env
NOTION_TASKS_DATABASE_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### Step 4: Auto-setup (optional)

Ask SPESION to create all databases for you:
```
"Set up my Notion workspace with all SPESION databases"
```

The `executive` agent will run `setup_notion_workspace` which creates:
- 📋 Tasks database
- 📓 Journal database  
- 👥 CRM / Contacts database
- 📚 Books database
- 🏋️ Training Log database
- 💰 Finance Portfolio database
- 🔄 Transactions database

### Available Notion Tools (18 total)

| Category | Tools |
|----------|-------|
| **Health** | `check_notion_connection` |
| **Tasks** | `get_tasks`, `create_task`, `update_task_status` |
| **Journal** | `create_journal_entry`, `create_knowledge_pill` |
| **CRM** | `search_contacts`, `add_contact` |
| **Books** | `add_book` |
| **Training** | `log_training_session`, `get_training_for_date` |
| **Finance** | `add_portfolio_holding`, `get_portfolio_holdings` |
| **Setup** | `setup_notion_workspace`, `setup_books_database`, `setup_trainings_database`, `setup_transactions_database` |

---

## First-Run Checklist

```
□ 1. Copy .env.example → .env, fill in ALL required values

□ 2. Install dependencies:
      pip install -r requirements.txt

□ 3. Pull local models (if using Ollama):
      ollama pull llama3.2:3b
      ollama pull qwen2.5:7b

□ 4. Google Calendar first-auth:
      python main.py --cli
      → Ask: "what's on my calendar today?"
      → Browser opens → authorize → token saved

□ 5. Verify all connections:
      Ask SPESION: "run a full system status check"
      It will call: check_garmin_connection, check_notion_connection,
                    check_ibkr_connection, get_today_agenda

□ 6. Initialize workspace identity files (auto-created on first run):
      workspace/SOUL.md
      workspace/IDENTITY.md
      workspace/AGENTS.md

□ 7. Start the API server:
      python main.py --api

□ 8. (Optional) Start Telegram bot:
      python main.py --telegram

□ 9. (Optional) Start Discord bot:
      python main.py --discord

□ 10. Verify heartbeat is scheduled:
       python main.py --status
```

---

## CLI Commands

```bash
# Interactive CLI — direct conversation
python main.py --cli

# API server (FastAPI on port 8100)
python main.py --api

# Telegram bot
python main.py --telegram

# Discord bot
python main.py --discord

# Heartbeat mode — runs scheduler (daily/weekly tasks)
python main.py --heartbeat

# Trigger nightly cognitive reflection now
python main.py --reflect

# System status (all subsystems)
python main.py --status

# Combine modes (API + heartbeat + telegram)
python main.py --api --heartbeat --telegram
```

### API Endpoints (port 8100)

```
POST /chat           → Send message, get response
GET  /status         → System health
GET  /agents         → List agents + models
GET  /memory/skills  → All learned skills
POST /memory/compact → Force conversation compaction
GET  /heartbeat      → Scheduled tasks status
```

---

## Windows 11 PowerShell Start Guide

### One-time setup

```powershell
# Clone / copy project
cd C:\SPESION

# Create virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Install Ollama (if using local models)
# Download from: https://ollama.com/download/windows
ollama pull llama3.2:3b
ollama pull qwen2.5:7b

# Copy and edit .env
Copy-Item .env.example .env
notepad .env
```

### Daily start (save as `start_spesion.ps1`)

```powershell
# Start Ollama in background (if not running)
Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden

# Activate venv
.venv\Scripts\Activate.ps1

# Start SPESION (API + heartbeat + telegram)
python main.py --api --heartbeat --telegram
```

### Run as Windows Service (optional)

Use `NSSM` (Non-Sucking Service Manager):
```powershell
# Download NSSM: https://nssm.cc/download
nssm install SPESION "C:\SPESION\.venv\Scripts\python.exe" "C:\SPESION\main.py --api --heartbeat --telegram"
nssm set SPESION AppDirectory "C:\SPESION"
nssm start SPESION
```

Check status:
```powershell
nssm status SPESION
```

---

## Docker Deployment

```bash
# Build + start all services
docker compose -f docker/docker-compose.yml up -d

# View logs
docker compose -f docker/docker-compose.yml logs -f spesion

# Stop
docker compose -f docker/docker-compose.yml down
```

The `docker-compose.yml` starts:
- `spesion` — main application (API + heartbeat)
- `ollama` — local model server (GPU if available)
- `chroma` — vector database

---

## Upgrading from 2.0

1. **Pull latest code** (or copy files)
2. **Run migrations** (auto-happens on startup):
   - `data/memory_bank.db` — auto-created if missing
   - `data/skill_store.db` — auto-created if missing
   - `data/google_token.json` — migrated from `.pickle` automatically
3. **New `.env` variables to add**:
   ```env
   HEARTBEAT_ENABLED=true
   COGNITIVE_LOOP_ENABLED=true
   SKILL_STORE_PATH=./data/skill_store.db
   ```
4. **New workspace files** — created automatically on first run in `workspace/`
5. **Notion**: new databases (Transactions, Finance Portfolio) — run `setup_notion_workspace` to create them

---

## Feature Comparison: SPESION 3.0 vs OpenClaw

| Capability | OpenClaw | SPESION 3.0 |
|-----------|---------|-------------|
| Multi-agent | ✅ | ✅ |
| Multi-model routing | ✅ | ✅ (11 models, privacy-aware) |
| Agent self-learning | ✅ | ✅ (SkillStore, Jaccard+LLM) |
| Persistent memory | ✅ | ✅ (3-tier: episodic+semantic+skills) |
| Nightly reflection | ✅ | ✅ (CognitiveLoop) |
| Heartbeat scheduler | ✅ | ✅ (HeartbeatRunner) |
| Code sandbox | ✅ | ✅ (Docker sandbox) |
| Web search | ✅ | ✅ (Tavily/DuckDuckGo) |
| Finance integration | ❌ | ✅ (IBKR + Bitget + Notion sync) |
| Health integration | ❌ | ✅ (Garmin — full stats + HRV) |
| Calendar management | ❌ | ✅ (Google Calendar — 7 tools) |
| Knowledge base (Notion) | ❌ | ✅ (18 tools, 7 database types) |
| Workspace identity | ✅ | ✅ (SOUL.md + 5 workspace files) |
| Context compaction | ✅ | ✅ (6000 token budget, LLM summary) |
| Local privacy mode | Partial | ✅ (3 agents fully local) |
| Research (Arxiv) | ✅ | ✅ |
| Telegram interface | ❌ | ✅ |
| Discord interface | ✅ | ✅ |
| Docker deployment | ✅ | ✅ |

---

## Troubleshooting

### "Ollama not responding"
```bash
ollama serve          # Mac/Linux
# Windows: open Ollama from system tray
ollama list           # verify models are downloaded
```

### "Google Calendar: invalid_grant"
The token expired or was revoked. Delete it and re-authenticate:
```bash
rm data/google_token.json
python main.py --cli   # triggers re-auth on next calendar request
```

### "Garmin requires MFA"
See [Garmin Setup → MFA section](#step-2-mfa--two-factor-authentication)

### "IBKR: Missing .env variables"
Make sure both `IBKR_FLEX_TOKEN` and `IBKR_FLEX_QUERY_ID` are set. The token is 18 digits, query ID is 7 digits.

### "Notion: Could not find database"
1. Check the database ID in `.env` matches the URL
2. Make sure you connected the SPESION integration to that database (click `...` → Connections → SPESION)
3. Run: `check_notion_connection` to see which databases are configured

### "Skills not being learned"
Skills only save after **successful non-tool-call responses**. Make sure:
1. `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` is set (skill extraction uses LLM)
2. Check `data/skill_store.db` exists after a few conversations
3. Run: `sqlite3 data/skill_store.db "SELECT count(*) FROM skills"`

---

*SPESION 3.0 — Built for autonomy. Designed to grow.*
