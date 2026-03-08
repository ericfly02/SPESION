# SPESION vs OpenClaw — Strategic Analysis & Hardened Deployment Plan

**Date**: February 20, 2026  
**Author**: Senior AI Systems Architect (Consultant)  
**Client**: Eric Gonzalez Duro  

---

## Table of Contents

1. [Deep Repo Analysis — SPESION](#1-deep-repo-analysis--spesion)
2. [Deep Repo Analysis — OpenClaw](#2-deep-repo-analysis--openclaw)
3. [Strategic Recommendation](#3-strategic-recommendation)
4. [Cost-Efficiency Breakdown](#4-cost-efficiency-breakdown)
5. [Security Audit & Hardening Plan](#5-security-audit--hardening-plan)
6. [Second Brain on Discord](#6-second-brain-on-discord)
7. [Self-Hosted Local Server Setup](#7-self-hosted-local-server-setup)
8. [Action Plan & Continuation Prompts](#8-action-plan--continuation-prompts)

---

## 1. Deep Repo Analysis — SPESION

### Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                    SPESION ARCHITECTURE                          │
│                                                                  │
│  ┌──────────┐    ┌────────────┐    ┌─────────────────────────┐  │
│  │ Telegram  │───▶│  Guard     │───▶│  Supervisor (Router)    │  │
│  │ Bot       │    │ (Sentinel) │    │  - Keyword matching     │  │
│  │           │    │ PII Filter │    │  - LLM-based routing    │  │
│  └──────────┘    └────────────┘    └──────────┬──────────────┘  │
│                                                │                 │
│  ┌─────────────────────────────────────────────▼──────────────┐  │
│  │              THE OCTAGON (8 Agents)                         │  │
│  │                                                             │  │
│  │  Scholar   Coach    Tycoon   Companion                     │  │
│  │  (cloud)   (local)  (cloud)  (local)                       │  │
│  │                                                             │  │
│  │  TechLead  Connector Executive Sentinel                    │  │
│  │  (cloud)   (cloud)   (local)   (local)                     │  │
│  └────────────────────────┬────────────────────────────────────┘  │
│                           │                                       │
│  ┌────────────────────────▼────────────────────────────────────┐  │
│  │  SERVICES                                                    │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │  │
│  │  │ ChromaDB │ │ Ollama   │ │ Notion   │ │ Whisper      │   │  │
│  │  │ (RAG)    │ │ (Local)  │ │ (KB)     │ │ (Voice)      │   │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────┘   │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │  │
│  │  │ OpenAI   │ │ Anthropic│ │ IBKR     │ │ Garmin/      │   │  │
│  │  │ (Cloud)  │ │ (Cloud)  │ │ (Finance)│ │ Strava       │   │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────┘   │  │
│  └──────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### Strengths

| # | Strength | Evidence |
|---|----------|----------|
| 1 | **Well-designed agent taxonomy** | 8 agents with clear non-overlapping domains (scholar, coach, tycoon, companion, techlead, connector, executive, sentinel) |
| 2 | **Privacy-by-design** | Local LLM routing for sensitive agents (companion, coach, sentinel); PII regex detection in Sentinel |
| 3 | **Rich prompt engineering** | 700+ lines of carefully crafted system prompts with user context, behavioral rules, and output examples |
| 4 | **Hybrid LLM factory** | Clean abstraction via `TaskType` enum → automatic local/cloud routing |
| 5 | **Practical tooling** | IBKR+Bitget portfolio sync, Garmin/Strava integration, Google Calendar, ArXiv papers — these are real, usable integrations |
| 6 | **LangGraph architecture** | Proper graph-based orchestration with guard → supervisor → agent → tools → consolidate flow |
| 7 | **Pydantic settings** | Type-safe configuration with `SecretStr` for API keys |
| 8 | **Notion as second brain** | 9+ Notion databases (tasks, knowledge, CRM, finance, goals, pills, books, trainings, transactions) |

### Weaknesses (Brutal Honesty)

| # | Issue | Severity | Detail |
|---|-------|----------|--------|
| 1 | **In-memory conversation history** | 🔴 CRITICAL | `SpesionAssistant._history` is a plain `dict`. Server restart = all context lost. No persistence layer. |
| 2 | **Hardcoded user profile in prompts** | 🔴 CRITICAL | Eric's age, breakup history, financial details, and NIE patterns are baked into `prompts.py` — a file committed to git. This is a privacy disaster if the repo ever goes public. |
| 3 | **No authentication beyond Telegram whitelist** | 🔴 CRITICAL | `allowed_user_ids` is the only auth gate. No rate limiting, no session tokens, no API auth. |
| 4 | **Duplicate RAG/vector systems** | 🟡 MEDIUM | Both `VectorStore` (ChromaDB wrapper) and `RAGService` (LangChain Chroma) exist. Two separate ChromaDB clients hitting the same directory — potential corruption. |
| 5 | **No session persistence** | 🔴 CRITICAL | `_session_counter` is an in-memory integer. No database, no state recovery. |
| 6 | **Supervisor routing is fragile** | 🟡 MEDIUM | Keyword-first routing means "I have a bug with my training plan" → `techlead` (keyword "bug"), not `coach`. LLM fallback helps but is slow. |
| 7 | **No multi-channel support** | 🟡 MEDIUM | Telegram-only. No Discord, WhatsApp, CLI, or API endpoints. |
| 8 | **Blocking sync graph execution** | 🟡 MEDIUM | `graph.invoke()` is synchronous even in `achat()` — `ainvoke()` exists but the underlying agents use sync LLM calls. |
| 9 | **No tests** | 🔴 CRITICAL | Zero test files. No unit tests, no integration tests, no CI/CD. |
| 10 | **Docker config incomplete** | 🟡 MEDIUM | No `CMD` in Dockerfile. No reverse proxy config. No TLS. Port 11434 exposed to all interfaces. |
| 11 | **No rate limiting** | 🟡 MEDIUM | No protection against LLM cost explosion from rapid message spam. |
| 12 | **Singleton anti-pattern everywhere** | 🟢 LOW | Global singletons (`_assistant`, `_rag_service`, `settings`) make testing and multi-tenancy impossible. |
| 13 | **No compaction/context window management** | 🔴 CRITICAL | Messages accumulate without limit. Last 10 messages + RAG context + system prompt can easily overflow context windows, especially for Ollama models with 4-8K contexts. |
| 14 | **Smart Wake is half-built** | 🟢 LOW | `smart_wake.py` exists but integration is unclear. |

### Redundancies Found

1. **`notion_manager.py` vs `notion_mcp.py`** — Two Notion abstraction layers doing overlapping things. `notion_mcp.py` is 1365 lines and is the one actually used; `notion_manager.py` is largely dead code.
2. **`VectorStore` vs `RAGService`** — Both wrap ChromaDB with different APIs. `RAGService` is used by `BaseAgent._build_messages()`, `VectorStore` by `MemoryService`. They create separate ChromaDB client instances.
3. **`finance_tool.py` vs `finance_tools.py`** — Two finance tool files.
4. **`_normalize_database_id()`** — Duplicated identically in `notion_mcp.py` and `investments_sync.py`.

---

## 2. Deep Repo Analysis — OpenClaw

### Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                     OPENCLAW ARCHITECTURE                             │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │  CHANNELS (Multi-channel inbox)                                   │ │
│  │  WhatsApp │ Telegram │ Discord │ Slack │ Signal │ iMessage │ ... │ │
│  └────────────────────────────┬─────────────────────────────────────┘ │
│                               │                                       │
│  ┌────────────────────────────▼─────────────────────────────────────┐ │
│  │  GATEWAY (WebSocket Daemon)                                       │ │
│  │  - Sessions, Presence, Config, Cron, Webhooks                     │ │
│  │  - Multi-agent routing (bindings)                                 │ │
│  │  - Per-agent sandbox + tool policies                              │ │
│  │  - Context window management + compaction                         │ │
│  └────────────────────────────┬─────────────────────────────────────┘ │
│                               │                                       │
│  ┌────────────────────────────▼─────────────────────────────────────┐ │
│  │  AGENTS (Isolated workspaces)                                     │ │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐                            │ │
│  │  │ Agent A  │ │ Agent B │ │ Agent C │  ... (N agents)            │ │
│  │  │ SOUL.md  │ │ SOUL.md │ │ SOUL.md │                            │ │
│  │  │ USER.md  │ │ USER.md │ │ USER.md │                            │ │
│  │  │ MEMORY.md│ │ MEMORY.md│ │ MEMORY.md│                           │ │
│  │  │ skills/  │ │ skills/ │ │ skills/ │                            │ │
│  │  └─────────┘ └─────────┘ └─────────┘                            │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │  TOOLS                                                            │ │
│  │  read/write/edit │ exec/process │ web_search/fetch │ browser     │ │
│  │  canvas │ cron │ message │ sessions_* │ memory_search │ nodes    │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │  INFRASTRUCTURE                                                   │ │
│  │  Pi Agent Runtime │ Hooks │ Skills (ClawHub) │ Formal Security   │ │
│  └──────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

### OpenClaw Strengths (Relevant to SPESION)

| # | Strength | Why It Matters |
|---|----------|----------------|
| 1 | **Multi-channel out of box** | Discord, Telegram, WhatsApp, Slack, Signal — all wired. One Gateway, many channels. |
| 2 | **Multi-agent routing with isolation** | Each agent gets its own workspace, session store, auth profile, sandbox policy. SPESION's shared state is primitive by comparison. |
| 3 | **Memory as Markdown files** | `SOUL.md`, `USER.md`, `MEMORY.md`, `memory/YYYY-MM-DD.md` — human-readable, git-backable, editable. No vector DB required for core memory. |
| 4 | **Formal security models (TLA+)** | Machine-checked security properties. OpenClaw has a published threat model atlas. SPESION has regex PII patterns. |
| 5 | **Context window management** | Auto-compaction, pre-compaction memory flush, token budgeting. SPESION has none. |
| 6 | **Skills/Hooks ecosystem** | Extensible plugin system. ClawHub for community skills. |
| 7 | **Sandboxing per agent** | Docker sandboxes with per-agent tool allow/deny policies. |
| 8 | **Voice Wake + Talk Mode** | Always-on speech with ElevenLabs TTS. |
| 9 | **Sub-agents** | Spawn background work from a main agent. |
| 10 | **Production-grade ops** | `openclaw doctor`, `openclaw status`, log streaming, health checks. |

### OpenClaw Weaknesses (for SPESION's use case)

| # | Weakness | Impact |
|---|----------|--------|
| 1 | **TypeScript, not Python** | Eric's stack is Python. All SPESION tools (IBKR, Garmin, ccxt, yfinance) are Python libraries. |
| 2 | **No built-in domain agents** | OpenClaw agents are generic "brains" with personas. No Coach, Tycoon, Scholar equivalents with real tool integrations. |
| 3 | **No Notion integration** | No built-in Notion support. Would need custom skill development. |
| 4 | **No finance/health tooling** | No IBKR, no Bitget, no Garmin, no Strava, no ArXiv. All of SPESION's valuable tool integrations would need to be rebuilt. |
| 5 | **Memory is file-based only** | No vector search by default (optional `qmd` plugin). Semantic retrieval is weaker than ChromaDB. |
| 6 | **Heavier infrastructure** | Node.js runtime + Gateway daemon + multiple channel processes. More RAM, more complexity. |
| 7 | **Rapid breaking changes** | Active open-source project with fast iteration. API stability is not guaranteed. |

---

## 3. Strategic Recommendation

### Verdict: **Path C — Hybrid** (with caveats)

Use **OpenClaw as the Gateway/channel layer** and wrap **SPESION's agents/tools as OpenClaw skills or exec-based tools**.

#### Why NOT Path A (Enhance SPESION)

SPESION has fundamental infrastructure gaps that would take months to fix properly:
- Session persistence
- Multi-channel support
- Context window management
- Security hardening
- Test infrastructure

You'd be rebuilding 60% of what OpenClaw already provides.

#### Why NOT Path B (Full Migration)

All of SPESION's **unique value** is in its Python tool integrations:
- IBKR + Bitget portfolio sync → Notion
- Garmin + Strava health tracking
- ArXiv paper curation
- 700+ lines of hyper-personalized prompts

Rebuilding this in TypeScript/OpenClaw skills would take 3-6 months and lose the Python library ecosystem.

#### Why Path C (Hybrid)

```
┌─────────────────────────────────────────────────────────────────┐
│                    HYBRID ARCHITECTURE                           │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐   │
│  │  OPENCLAW GATEWAY (TypeScript)                             │   │
│  │  - Discord / Telegram / WhatsApp channels                  │   │
│  │  - Multi-agent routing (1 bot per persona)                 │   │
│  │  - Session management + compaction                         │   │
│  │  - Memory (SOUL.md + MEMORY.md per agent)                  │   │
│  │  - Security (sandbox, auth, TLS)                           │   │
│  └──────────────────────┬────────────────────────────────────┘   │
│                         │ exec / HTTP                            │
│  ┌──────────────────────▼────────────────────────────────────┐   │
│  │  SPESION ENGINE (Python - FastAPI)                         │   │
│  │  ┌─────────────┐ ┌──────────────┐ ┌───────────────────┐   │   │
│  │  │ Agent Tools  │ │ LLM Factory  │ │ Vector Store      │   │   │
│  │  │ - ArXiv      │ │ - Ollama     │ │ - ChromaDB        │   │   │
│  │  │ - Garmin     │ │ - OpenAI     │ │ - RAG Service     │   │   │
│  │  │ - IBKR       │ │ - Anthropic  │ │                   │   │   │
│  │  │ - Strava     │ │              │ │                   │   │   │
│  │  │ - Notion     │ │              │ │                   │   │   │
│  │  │ - yfinance   │ │              │ │                   │   │   │
│  │  └─────────────┘ └──────────────┘ └───────────────────┘   │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  INFRASTRUCTURE                                             │   │
│  │  Ollama │ ChromaDB │ Traefik │ Docker Compose              │   │
│  └────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

**How it works:**

1. OpenClaw Gateway handles all channel I/O (Discord, Telegram, WhatsApp)
2. Each SPESION agent becomes an OpenClaw agent with its own `SOUL.md` (persona) + workspace
3. OpenClaw routes messages to the right agent via `bindings`
4. Each OpenClaw agent uses `exec` tool to call SPESION's Python tools via a FastAPI microservice
5. SPESION's Python tooling (IBKR, Garmin, ArXiv, Notion, etc.) runs as API endpoints
6. Ollama stays as the local LLM backend for both systems

**Key advantages:**
- Keep all Python tool integrations untouched
- Get Discord/multi-channel for free
- Get session persistence, compaction, and security from OpenClaw
- Keep custom prompts in `SOUL.md` per agent (no more hardcoded prompts)
- Personal data lives in workspace files, not in source code

---

## 4. Cost-Efficiency Breakdown

### Monthly Cost Estimates

#### Path A: Enhanced SPESION (Python only)

| Component | Specification | Monthly Cost |
|-----------|--------------|--------------|
| **Server** | Hetzner CAX21 (4 ARM cores, 8GB RAM) | €8.49 |
| **Ollama models** | llama3.2:3b + llama3.1:8b | €0 (local) |
| **OpenAI API** | GPT-4o, ~50K tokens/day avg | ~€45 |
| **Anthropic API** | Claude 3.5 Sonnet (backup) | ~€15 |
| **ChromaDB** | Local, ~50K vectors | €0 |
| **Notion API** | Free tier (watch block limits) | €0 |
| **Telegram Bot** | Free | €0 |
| **Domain + DNS** | Optional | ~€1 |
| **Total** | | **~€70/month** |

#### Path B: Full OpenClaw Migration

| Component | Specification | Monthly Cost |
|-----------|--------------|--------------|
| **Server** | Hetzner CAX31 (8 ARM cores, 16GB RAM) — Node.js + heavier | €15.49 |
| **Ollama models** | Same | €0 |
| **OpenAI API** | Higher token use (context rebuilding, compaction) ~80K/day | ~€72 |
| **Anthropic API** | Backup | ~€15 |
| **Rebuild effort** | 3-6 months of dev time (opportunity cost) | SIGNIFICANT |
| **Total (infra only)** | | **~€103/month** |

#### Path C: Hybrid (Recommended)

| Component | Specification | Monthly Cost |
|-----------|--------------|--------------|
| **Server** | Hetzner CAX31 (8 ARM cores, 16GB RAM) | €15.49 |
| **Ollama models** | llama3.2:3b + qwen2.5:7b (better tool calling) | €0 |
| **OpenAI API** | ~40K tokens/day (OpenClaw is more token-efficient with compaction) | ~€36 |
| **Anthropic API** | Backup / Scholar deep dives | ~€10 |
| **ChromaDB** | Local | €0 |
| **Notion API** | Free tier | €0 |
| **Discord bots** | Free (8 bot accounts) | €0 |
| **Telegram bot** | Free (legacy, OpenClaw handles) | €0 |
| **Domain + Cloudflare** | spesion.ai or similar | ~€1 |
| **Tailscale** | Free tier (remote access) | €0 |
| **Total** | | **~€63/month** |

### Why Path C Is Cheapest Long-term

- OpenClaw's **compaction** reduces token waste (SPESION sends full history every time)
- OpenClaw's **session persistence** means no re-summarizing context
- Local Ollama handles more tasks (OpenClaw's model routing is smarter)
- You stop paying for "wasted" tokens from supervisor re-routing failures

### Hardware Requirements (Self-hosted)

| Spec | Minimum | Recommended |
|------|---------|-------------|
| **CPU** | 4 cores (ARM or x86) | 8 cores |
| **RAM** | 8GB | 16GB (Ollama needs ~5GB for 8B model) |
| **Storage** | 50GB SSD | 100GB NVMe |
| **GPU** | None required | Optional: old NVIDIA for faster Ollama |
| **Network** | 100Mbps, static IP or Tailscale | 1Gbps |
| **OS** | Ubuntu 22.04 LTS / Debian 12 | Ubuntu 24.04 LTS |

---

## 5. Security Audit & Hardening Plan

### Attack Surface Map

```
┌─────────────────────────────────────────────────────────────┐
│                  ATTACK SURFACE MAP                          │
│                                                              │
│  🔴 CRITICAL                                                 │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ 1. API keys in .env file (no encryption at rest)        │ │
│  │ 2. Hardcoded personal data in prompts.py (git-tracked)  │ │
│  │ 3. No auth on Ollama port 11434 (exposed in compose)    │ │
│  │ 4. Docker socket mounted read-only (still dangerous)    │ │
│  │ 5. No TLS anywhere — all traffic is plaintext           │ │
│  │ 6. No input validation on tool arguments                │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                              │
│  🟡 HIGH                                                     │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ 7. Prompt injection via user messages → tool execution  │ │
│  │ 8. Memory poisoning via ChromaDB (no input sanitization)│ │
│  │ 9. No rate limiting on Telegram messages                │ │
│  │ 10. Notion API key has full workspace access            │ │
│  │ 11. Garmin plaintext password in env                    │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                              │
│  🟢 MEDIUM                                                   │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ 12. No log rotation (spesion.log grows indefinitely)    │ │
│  │ 13. ffmpeg/tesseract installed but no sandboxing        │ │
│  │ 14. No CORS/CSP if API mode is ever added               │ │
│  │ 15. ChromaDB telemetry disabled but no network isolation│ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Hardening Checklist

#### Immediate (Do Today)

- [ ] **Move personal data out of `prompts.py`** → Store in `USER.md` or encrypted `.env` fields, load at runtime
- [ ] **Add `.env` to `.gitignore`** (verify it's not committed)
- [ ] **Remove `ports: "11434:11434"` from docker-compose.yml** — Ollama should only be accessible within the Docker network
- [ ] **Remove Docker socket mount** — Use Docker SDK with limited permissions or remove sandbox feature
- [ ] **Add rate limiting** — Max 30 messages/minute per user in Telegram bot
- [ ] **Add input length validation** — Max 4096 chars per message, reject longer inputs

#### Short-term (This Week)

- [ ] **Encrypt secrets at rest** — Use `age` or `sops` for `.env` encryption
- [ ] **Add TLS** — Traefik or Nginx reverse proxy with Let's Encrypt
- [ ] **Implement session persistence** — SQLite or Redis for conversation state
- [ ] **Add prompt injection guards**:
  ```python
  # In BaseAgent._build_messages():
  INJECTION_PATTERNS = [
      r"ignore (all )?previous instructions",
      r"you are now",
      r"system:\s",
      r"<\|im_start\|>",
      r"\[INST\]",
  ]
  ```
- [ ] **Network isolation** — Internal Docker network, no ports exposed to host except Traefik 443
- [ ] **Add WAF rules** — Block suspicious patterns in incoming messages

#### Medium-term (This Month)

- [ ] **Implement tool sandboxing** — Each tool call validates arguments against a schema
- [ ] **Add audit logging** — Log every LLM call, tool execution, and data access to SQLite
- [ ] **Memory integrity checks** — Hash ChromaDB entries, detect tampering
- [ ] **Implement RBAC** — User roles (admin, user, readonly) even for single-user
- [ ] **Set up automated backups** — ChromaDB + SQLite + workspace files to encrypted offsite
- [ ] **Container security scanning** — Trivy or Grype in CI

### Prompt Injection Defense (Critical)

SPESION currently has **zero** prompt injection protection. The `BaseAgent._build_messages()` method blindly passes user input + RAG context to LLMs. An attacker (or even a poisoned RAG document) could:

1. Override system prompts
2. Exfiltrate data via tool calls
3. Delete Notion pages
4. Send messages as the bot

**Defense layers needed:**

```
Layer 1: Input sanitization (regex strip known injection patterns)
Layer 2: Output validation (verify tool calls match allowed schemas)
Layer 3: Tool allowlists per agent (Scholar can't call delete_task)
Layer 4: Human-in-the-loop for destructive actions (Notion deletes, calendar changes)
Layer 5: Canary tokens in system prompts to detect leakage
```

---

## 6. Second Brain on Discord

### Architecture: One Bot Per Agent Persona

```
Discord Server: "SPESION HQ"
│
├── #general          ← Main bot (Supervisor)
├── #scholar          ← Scholar bot (papers, news, deep dives)
├── #coach            ← Coach bot (training, health, Garmin)
├── #tycoon           ← Tycoon bot (portfolio, markets, DCA)
├── #companion        ← Companion bot (journaling, emotions) [PRIVATE CHANNEL]
├── #techlead         ← TechLead bot (code review, architecture)
├── #connector        ← Connector bot (networking, CRM)
├── #executive        ← Executive bot (calendar, tasks, priorities)
├── #sentinel         ← Sentinel bot (system status, security)
│
├── #daily-briefing   ← Automated: Scholar posts morning briefing
├── #training-log     ← Automated: Coach posts workout summaries
├── #portfolio-alerts ← Automated: Tycoon posts allocation drift alerts
│
└── 🔒 Private Threads for sensitive conversations
```

### OpenClaw Configuration for Discord Multi-Agent

```json5
// ~/.openclaw/openclaw.json
{
  agents: {
    list: [
      { id: "scholar",   workspace: "~/.openclaw/workspace-scholar" },
      { id: "coach",     workspace: "~/.openclaw/workspace-coach" },
      { id: "tycoon",    workspace: "~/.openclaw/workspace-tycoon" },
      { id: "companion", workspace: "~/.openclaw/workspace-companion" },
      { id: "techlead",  workspace: "~/.openclaw/workspace-techlead" },
      { id: "connector", workspace: "~/.openclaw/workspace-connector" },
      { id: "executive", workspace: "~/.openclaw/workspace-executive" },
      { id: "sentinel",  workspace: "~/.openclaw/workspace-sentinel" },
    ],
  },

  bindings: [
    // Each Discord bot → its agent
    { agentId: "scholar",   match: { channel: "discord", accountId: "scholar" } },
    { agentId: "coach",     match: { channel: "discord", accountId: "coach" } },
    { agentId: "tycoon",    match: { channel: "discord", accountId: "tycoon" } },
    { agentId: "companion", match: { channel: "discord", accountId: "companion" } },
    { agentId: "techlead",  match: { channel: "discord", accountId: "techlead" } },
    { agentId: "connector", match: { channel: "discord", accountId: "connector" } },
    { agentId: "executive", match: { channel: "discord", accountId: "executive" } },
    { agentId: "sentinel",  match: { channel: "discord", accountId: "sentinel" } },
    // Keep Telegram → main supervisor for backward compat
    { agentId: "scholar", match: { channel: "telegram", accountId: "default" } },
  ],

  channels: {
    discord: {
      groupPolicy: "allowlist",
      accounts: {
        scholar: {
          token: "DISCORD_BOT_TOKEN_SCHOLAR",
          guilds: {
            "YOUR_SERVER_ID": {
              channels: {
                "SCHOLAR_CHANNEL_ID": { allow: true, requireMention: false },
                "DAILY_BRIEFING_CHANNEL_ID": { allow: true, requireMention: false },
              },
            },
          },
        },
        // ... repeat for each agent
      },
    },
    telegram: {
      accounts: {
        default: { token: "YOUR_TELEGRAM_BOT_TOKEN" },
      },
    },
  },

  // Per-agent model overrides
  agents: {
    defaults: {
      model: "ollama/llama3.2:3b",  // Default to local
    },
    list: [
      {
        id: "scholar",
        model: "openai/gpt-4o",     // Scholar needs cloud for quality
        workspace: "~/.openclaw/workspace-scholar",
      },
      {
        id: "companion",
        model: "ollama/llama3.2:3b", // Companion stays local (privacy)
        workspace: "~/.openclaw/workspace-companion",
      },
      // ... etc
    ],
  },
}
```

### SOUL.md Example (Scholar Agent)

```markdown
# SOUL.md — Scholar (SPESION Agent)

## Identity
- Name: Scholar
- Role: Research analyst and knowledge curator for Eric
- Emoji: 📚
- Tone: Intellectual, precise, no fluff. Dense and actionable.

## Boundaries
- Never fabricate paper citations or DOIs
- Always use tools to search ArXiv before claiming "no papers found"
- Write all briefings to memory/YYYY-MM-DD.md
- Create Knowledge Pills in Notion via the SPESION API

## Expertise
- AI/ML (cs.AI, cs.LG)
- Neuroscience (q-bio.NC)
- Quantitative Finance (q-fin.GN)
- Economics (econ.GN)

## Output Style
- Longform, 10+ minute reads for daily briefings
- Use headers, emojis (sparingly), and links
- Always connect insights to Eric's projects (Civita, Creda, WhoHub)
```

### SPESION Python API (FastAPI Bridge)

Each OpenClaw agent calls SPESION tools via `exec`:

```bash
# OpenClaw agent calls this via exec tool:
curl -s http://localhost:8100/api/tools/scholar/get_recent_papers \
  -H "Authorization: Bearer $SPESION_API_KEY" \
  -d '{"categories": ["cs.AI", "cs.LG", "q-bio.NC"]}'
```

---

## 7. Self-Hosted Local Server Setup

### Docker Compose (Production)

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  # ===== REVERSE PROXY =====
  traefik:
    image: traefik:v3.0
    container_name: spesion-traefik
    restart: unless-stopped
    command:
      - "--api.dashboard=true"
      - "--providers.docker=true"
      - "--providers.docker.exposedbydefault=false"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.websecure.address=:443"
      - "--certificatesresolvers.letsencrypt.acme.tlschallenge=true"
      - "--certificatesresolvers.letsencrypt.acme.email=eric@example.com"
      - "--certificatesresolvers.letsencrypt.acme.storage=/certs/acme.json"
      - "--entrypoints.web.http.redirections.entrypoint.to=websecure"
      - "--accesslog=true"
      - "--accesslog.filepath=/var/log/traefik/access.log"
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - traefik-certs:/certs
      - traefik-logs:/var/log/traefik
    networks:
      - spesion-network
    security_opt:
      - no-new-privileges:true

  # ===== SPESION PYTHON API =====
  spesion-api:
    build:
      context: .
      dockerfile: docker/Dockerfile.api
    container_name: spesion-api
    restart: unless-stopped
    environment:
      - SPESION_API_KEY=${SPESION_API_KEY}
      - OLLAMA_BASE_URL=http://ollama:11434
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - NOTION_API_KEY=${NOTION_API_KEY}
      - GARMIN_EMAIL=${GARMIN_EMAIL}
      - GARMIN_PASSWORD=${GARMIN_PASSWORD}
      - STRAVA_CLIENT_ID=${STRAVA_CLIENT_ID}
      - STRAVA_CLIENT_SECRET=${STRAVA_CLIENT_SECRET}
      - STRAVA_REFRESH_TOKEN=${STRAVA_REFRESH_TOKEN}
      - GITHUB_TOKEN=${GITHUB_TOKEN}
      - IBKR_FLEX_TOKEN=${IBKR_FLEX_TOKEN}
      - IBKR_FLEX_QUERY_ID=${IBKR_FLEX_QUERY_ID}
      - BITGET_API_KEY=${BITGET_API_KEY}
      - BITGET_API_SECRET=${BITGET_API_SECRET}
      - BITGET_PASSPHRASE=${BITGET_PASSPHRASE}
      - CHROMA_PERSIST_DIR=/data/chroma
    volumes:
      - spesion-data:/data
    networks:
      - spesion-internal
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.spesion-api.rule=Host(`api.spesion.local`)"
      - "traefik.http.routers.spesion-api.tls=true"
      - "traefik.http.services.spesion-api.loadbalancer.server.port=8100"
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '2'

  # ===== OPENCLAW GATEWAY =====
  openclaw:
    image: node:20-slim
    container_name: spesion-openclaw
    restart: unless-stopped
    working_dir: /app
    command: ["npx", "openclaw", "gateway", "start", "--foreground"]
    environment:
      - OPENCLAW_STATE_DIR=/openclaw-state
      - OPENCLAW_CONFIG_PATH=/openclaw-state/openclaw.json
    volumes:
      - openclaw-state:/openclaw-state
      - openclaw-workspaces:/openclaw-workspaces
    networks:
      - spesion-network
      - spesion-internal
    depends_on:
      - spesion-api
      - ollama

  # ===== OLLAMA =====
  ollama:
    image: ollama/ollama:latest
    container_name: spesion-ollama
    restart: unless-stopped
    volumes:
      - ollama-data:/root/.ollama
    environment:
      - OLLAMA_HOST=0.0.0.0
    # NO ports exposed to host!
    networks:
      - spesion-internal
    deploy:
      resources:
        limits:
          memory: 6G
          cpus: '4'

  # ===== CHROMADB =====
  chromadb:
    image: chromadb/chroma:latest
    container_name: spesion-chromadb
    restart: unless-stopped
    volumes:
      - chroma-data:/chroma/chroma
    environment:
      - IS_PERSISTENT=TRUE
      - ANONYMIZED_TELEMETRY=FALSE
    networks:
      - spesion-internal
    # NO ports exposed to host!

volumes:
  traefik-certs:
  traefik-logs:
  spesion-data:
  openclaw-state:
  openclaw-workspaces:
  ollama-data:
  chroma-data:

networks:
  spesion-network:
    driver: bridge
  spesion-internal:
    driver: bridge
    internal: true  # No external access!
```

### Network Security Rules

```bash
# UFW firewall rules for the host
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Only allow SSH (key-only) and HTTPS
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 443/tcp   # HTTPS (Traefik)
sudo ufw allow 80/tcp    # HTTP (redirect to HTTPS)

# If using Tailscale for remote access:
sudo ufw allow in on tailscale0

sudo ufw enable
```

### Server Hardening Script

```bash
#!/bin/bash
# server-harden.sh — Run on fresh Ubuntu 24.04

set -euo pipefail

echo "=== SPESION Server Hardening ==="

# 1. System updates
apt-get update && apt-get upgrade -y
apt-get install -y ufw fail2ban unattended-upgrades

# 2. Create non-root user
useradd -m -s /bin/bash -G docker spesion
echo "spesion ALL=(ALL) NOPASSWD: /usr/bin/docker, /usr/bin/docker-compose" >> /etc/sudoers.d/spesion

# 3. SSH hardening
sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/#PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
sed -i 's/#MaxAuthTries 6/MaxAuthTries 3/' /etc/ssh/sshd_config
systemctl restart sshd

# 4. fail2ban
cat > /etc/fail2ban/jail.local << 'EOF'
[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
bantime = 3600
EOF
systemctl enable fail2ban && systemctl start fail2ban

# 5. Firewall
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 443/tcp
ufw allow 80/tcp
ufw --force enable

# 6. Docker security
cat > /etc/docker/daemon.json << 'EOF'
{
  "no-new-privileges": true,
  "live-restore": true,
  "userland-proxy": false,
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF
systemctl restart docker

# 7. Auto-updates
dpkg-reconfigure -plow unattended-upgrades

echo "=== Hardening complete ==="
```

### Backup Strategy

```bash
#!/bin/bash
# backup.sh — Daily cron backup

BACKUP_DIR="/backups/spesion/$(date +%Y-%m-%d)"
mkdir -p "$BACKUP_DIR"

# 1. ChromaDB
docker exec spesion-chromadb tar czf /tmp/chroma-backup.tar.gz /chroma/chroma
docker cp spesion-chromadb:/tmp/chroma-backup.tar.gz "$BACKUP_DIR/"

# 2. OpenClaw workspaces + state
tar czf "$BACKUP_DIR/openclaw-workspaces.tar.gz" \
  /var/lib/docker/volumes/spesion_openclaw-workspaces/_data/

# 3. SPESION data (SQLite, logs)
tar czf "$BACKUP_DIR/spesion-data.tar.gz" \
  /var/lib/docker/volumes/spesion_spesion-data/_data/

# 4. Encrypt
age -R ~/.ssh/id_ed25519.pub -o "$BACKUP_DIR.tar.gz.age" \
  <(tar czf - "$BACKUP_DIR")

# 5. Upload to B2/S3 (optional)
# rclone copy "$BACKUP_DIR.tar.gz.age" b2:spesion-backups/

# 6. Cleanup old backups (keep 30 days)
find /backups/spesion -maxdepth 1 -mtime +30 -type d -exec rm -rf {} +

echo "Backup complete: $BACKUP_DIR"
```

---

## 8. Action Plan & Continuation Prompts

### Numbered Action Plan

| # | Task | Priority | Effort | Dependency |
|---|------|----------|--------|------------|
| 1 | **Move personal data out of `prompts.py`** into `USER.md` files | 🔴 P0 | 2h | None |
| 2 | **Fix critical security issues** (remove exposed ports, add rate limiting) | 🔴 P0 | 4h | None |
| 3 | **Build FastAPI bridge** for SPESION tools | 🔴 P0 | 1 day | None |
| 4 | **Install OpenClaw** on target server | 🟡 P1 | 2h | Server |
| 5 | **Create 8 Discord bots** via Discord Developer Portal | 🟡 P1 | 1h | None |
| 6 | **Write SOUL.md** for each agent (migrate from `prompts.py`) | 🟡 P1 | 4h | Step 1 |
| 7 | **Configure OpenClaw multi-agent routing** | 🟡 P1 | 2h | Steps 4,5 |
| 8 | **Set up Docker Compose production stack** | 🟡 P1 | 4h | Steps 3,4 |
| 9 | **Deploy Traefik + TLS** | 🟡 P1 | 2h | Step 8 |
| 10 | **Add session persistence** (SQLite) to SPESION API | 🟢 P2 | 4h | Step 3 |
| 11 | **Implement automated backups** | 🟢 P2 | 2h | Step 8 |
| 12 | **Add prompt injection defenses** | 🟢 P2 | 4h | Step 3 |
| 13 | **Write integration tests** | 🟢 P2 | 1 day | Step 3 |
| 14 | **Set up Tailscale** for remote access | 🟢 P2 | 1h | Step 8 |
| 15 | **Configure cron jobs** (daily briefing, portfolio alerts) | 🟢 P2 | 2h | Steps 7,3 |

### Ready-to-Use AI Continuation Prompts

---

**Prompt 1: FastAPI Bridge**

> Build a FastAPI microservice that wraps all SPESION Python tools (from `src/tools/`) as REST API endpoints. Requirements: (1) Each tool becomes a POST endpoint at `/api/tools/{agent}/{tool_name}`. (2) Add bearer token auth via `SPESION_API_KEY` env var. (3) Add Pydantic request/response models for each tool. (4) Add rate limiting (30 req/min per IP). (5) Add health check at `/health`. (6) Add OpenAPI docs at `/docs`. (7) Include a Dockerfile. The existing tools are LangChain `@tool` decorated functions — extract their logic into pure functions and wrap in FastAPI routes.

---

**Prompt 2: SOUL.md Migration**

> I'm migrating from hardcoded system prompts in `prompts.py` to OpenClaw workspace files. Take each agent's prompt from `AGENT_PROMPTS` dict in `src/core/prompts.py` and convert it into a `SOUL.md` file following OpenClaw conventions. For each agent (scholar, coach, tycoon, companion, techlead, connector, executive, sentinel): (1) Create `~/.openclaw/workspace-{agent}/SOUL.md` with identity, tone, boundaries. (2) Create `USER.md` with Eric's profile (extracted from `USER_PROFILE` in prompts.py but sanitized — no NIE patterns, no financial details). (3) Create `AGENTS.md` with operating instructions. (4) Create `TOOLS.md` listing available SPESION API endpoints for that agent.

---

**Prompt 3: Security Hardening Sprint**

> I need to harden my SPESION + OpenClaw self-hosted setup. The current issues are: (1) API keys in plaintext `.env`, (2) no TLS, (3) Ollama port exposed, (4) no rate limiting, (5) no prompt injection defense, (6) Docker socket mounted. For each issue, provide: the exact fix (code/config), a test to verify it works, and a rollback plan. Use sops+age for secret encryption, Traefik for TLS, and implement a middleware-based rate limiter in the FastAPI bridge.

---

**Prompt 4: Discord Multi-Bot Setup**

> Set up 8 Discord bots for my SPESION second-brain system. For each bot (scholar, coach, tycoon, companion, techlead, connector, executive, sentinel): (1) Provide the Discord Developer Portal steps to create the bot. (2) List the required permissions and intents. (3) Generate the OpenClaw `openclaw.json` config snippet with bindings. (4) Explain channel-to-bot mapping. (5) Set up automated posting: Scholar posts daily briefing to #daily-briefing at 07:00 via OpenClaw cron. Coach posts training summary after each workout. Tycoon posts portfolio alerts when allocation drifts >5%.

---

**Prompt 5: Session Persistence & Context Window**

> My SPESION system loses all conversation history on restart because `SpesionAssistant._history` is an in-memory dict. Fix this by: (1) Adding SQLite-based session persistence with tables for conversations, messages, and agent state. (2) Implementing context window management — detect when messages + system prompt exceed the model's context window and auto-summarize older messages. (3) Adding a `/sessions` API endpoint to list/retrieve past conversations. (4) Integrating with OpenClaw's session model so sessions survive across Gateway restarts.

---

**Prompt 6: Automated Deployment Pipeline**

> Create a complete CI/CD pipeline for my SPESION + OpenClaw hybrid stack. The setup: Docker Compose on a Hetzner CAX31, GitHub Actions for CI, auto-deploy on push to main. Include: (1) GitHub Actions workflow: lint, type-check, test, build Docker images, push to GitHub Container Registry. (2) Deploy script: SSH to server, pull new images, docker compose up -d --build, health check, rollback on failure. (3) Monitoring: Uptime Kuma for health checks, Grafana + Prometheus for metrics (optional). (4) Alerting: Notify via Discord webhook if any service goes down.

---

**Prompt 7: Local LLM Optimization**

> I'm running Ollama locally for privacy-sensitive agents (companion, coach, sentinel) on a Hetzner CAX31 (8 ARM cores, 16GB RAM). Optimize my setup: (1) Compare llama3.2:3b vs qwen2.5:7b vs phi-3-mini for tool-calling accuracy and Spanish/English bilingual quality. (2) Benchmark response times and RAM usage for each. (3) Configure Ollama model preloading so the primary model stays warm. (4) Implement intelligent model routing: use the 3B model for simple routing/classification and the 7B model for actual agent responses. (5) Test if quantized models (Q4_K_M vs Q5_K_M) meaningfully degrade quality for emotional support (Companion) and health analysis (Coach).

---

**Prompt 8: Integration Testing Suite**

> Write a comprehensive test suite for the SPESION + OpenClaw hybrid system. Cover: (1) Unit tests for each SPESION tool (mock external APIs). (2) Integration tests for the FastAPI bridge (test each endpoint with realistic payloads). (3) End-to-end tests: send a Discord message → verify OpenClaw routes to correct agent → verify SPESION API is called → verify response is sent back. (4) Security tests: attempt prompt injection via each channel, verify PII detection works, test rate limiting. (5) Chaos tests: kill Ollama mid-request, verify fallback to cloud. Kill SPESION API, verify OpenClaw gracefully degrades. Use pytest, pytest-asyncio, and httpx for the test framework.

---

## Summary Matrix

| Dimension | SPESION (Current) | OpenClaw (Standalone) | **Hybrid (Recommended)** |
|-----------|--------------------|-----------------------|--------------------------|
| **Channels** | Telegram only | 15+ channels | 15+ channels ✅ |
| **Agent isolation** | Shared state | Full workspace isolation | Full isolation ✅ |
| **Memory** | ChromaDB (fragile) | Markdown + vector | Both ✅ |
| **Session persistence** | ❌ None | ✅ Full | ✅ Full |
| **Context management** | ❌ None | ✅ Compaction | ✅ Compaction |
| **Security** | Basic PII regex | Formal TLA+ models | Strong ✅ |
| **Custom tools** | ✅ Rich Python tools | ❌ Would need rebuild | ✅ Kept via API |
| **Personal prompts** | ✅ Deep customization | Generic agents | ✅ SOUL.md per agent |
| **Monthly cost** | ~€70 | ~€103 | **~€63** ✅ |
| **Migration effort** | N/A | 3-6 months | **2-3 weeks** ✅ |
| **Discord ready** | ❌ | ✅ | ✅ |
| **Self-hostable** | Partial | ✅ | ✅ |

---

*This document is a living reference. Update it as implementation progresses.*
