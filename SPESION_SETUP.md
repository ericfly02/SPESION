# SPESION 3.0 — Complete Server Setup & Autonomous Agent Guide

> **SPESION is now an autonomous agent that can make phone calls, send emails, browse websites, fill forms, and execute multi-step plans in the real world — with human approval gates for safety.**

---

## Table of Contents

1. [What SPESION Can Do Now](#what-spesion-can-do-now)
2. [Architecture — How Autonomous Execution Works](#architecture--how-autonomous-execution-works)
3. [New Components Created](#new-components-created)
4. [Complete .env Reference](#complete-env-reference)
5. [Server Setup (Windows 11)](#server-setup-windows-11)
6. [Windows Server Security Configuration](#windows-server-security-configuration)
7. [Production Deployment with Docker](#production-deployment-with-docker)
8. [Twilio Setup (Phone Calls & SMS)](#twilio-setup-phone-calls--sms)
9. [Email Setup (SMTP / Gmail API)](#email-setup-smtp--gmail-api)
10. [Browser Automation Setup (Playwright)](#browser-automation-setup-playwright)
11. [Telegram Bot Configuration](#telegram-bot-configuration)
12. [Discord Bot Configuration](#discord-bot-configuration)
13. [Google Calendar Setup](#google-calendar-setup)
14. [Garmin Setup](#garmin-setup)
15. [IBKR Setup](#ibkr-setup)
16. [Notion Setup](#notion-setup)
17. [Running SPESION](#running-spesion)
18. [How the Approval System Works](#how-the-approval-system-works)
19. [Example Autonomous Scenarios](#example-autonomous-scenarios)
20. [Full Feature Comparison: SPESION vs OpenClaw](#full-feature-comparison-spesion-vs-openclaw)
21. [Troubleshooting](#troubleshooting)

---

## What SPESION Can Do Now

### Real-World Autonomous Actions

| Capability | How it works | Example |
|-----------|-------------|---------|
| 📞 **Phone calls** | Twilio Programmable Voice + TTS | "Call Endesa about wrong receipt #12345" |
| 📧 **Send emails** | SMTP or Gmail API | "Email my landlord about the broken boiler" |
| 📱 **Send SMS** | Twilio Messaging | "Text the plumber confirming Thursday at 10" |
| 🌐 **Browse websites** | Playwright (headless Chromium) | "Check my order status on Amazon" |
| 📝 **Fill web forms** | Playwright form automation | "Submit a complaint on Vodafone's website" |
| 📸 **Screenshot pages** | Full page capture | "Take a screenshot of my bank balance" |
| 🔍 **Search the web** | Google via Playwright | "Find Endesa's complaint phone number" |
| 🗂️ **Multi-step plans** | AutonomousPlanner + PlanExecutor | "Research, call, email about my gas bill" |
| ✅ **Human approval** | Telegram/Discord inline buttons | User confirms before any dangerous action |
| 🔄 **Background tasks** | SQLite-backed task queue | Long-running tasks run while you work |

### All Previous Capabilities

- 8-agent multi-model system (companion, executive, scholar, tycoon, coach, techlead, connector, sentinel)
- ModelRouter (11 models, privacy-aware routing, health tracking)
- Agent self-learning (SkillStore — agents remember how to do tasks)
- 3-tier memory (episodic + semantic + skills)
- Google Calendar (7 tools), Garmin (5 tools), IBKR (2 tools), Notion (18 tools)
- CognitiveLoop (nightly reflection), HeartbeatRunner (cron scheduler)
- Context compaction, workspace identity (SOUL.md), injection guard

---

## Architecture — How Autonomous Execution Works

```
User: "Llama a Endesa por la factura incorrecta del gas"
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│                    SUPERVISOR (llama3.2:3b)              │
│  Keywords: "llama a" → route to EXECUTIVE               │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│              EXECUTIVE AGENT (gpt-4o-mini)               │
│                                                          │
│  Sees tool: execute_autonomous_plan                      │
│  Calls: execute_autonomous_plan(                         │
│    goal="Call Endesa about wrong gas receipt"             │
│  )                                                       │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│             AUTONOMOUS PLANNER (gpt-4o)                  │
│                                                          │
│  Decomposes into steps:                                  │
│  ┌─────────────────────────────────────────────────┐    │
│  │ Step 1 (SAFE): Search web for Endesa complaints │    │
│  │   phone number                                   │    │
│  │ Step 2 (SAFE): Draft TTS script for the call    │    │
│  │ Step 3 (DANGEROUS): Make phone call to Endesa   │    │
│  │   ⚠️ approval_message: "SPESION va a llamar a   │    │
│  │   Endesa (+34 900 850 840) para reclamar..."    │    │
│  │ Step 4 (SAFE): Check call status and report     │    │
│  └─────────────────────────────────────────────────┘    │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│               PLAN EXECUTOR                              │
│                                                          │
│  Step 1: ✅ search_web_browser → found number            │
│  Step 2: ✅ reasoning → script drafted                   │
│  Step 3: 🔐 DANGEROUS → triggers approval gate          │
│     │                                                    │
│     ├──► Telegram: "🔐 SPESION necesita tu aprobación"  │
│     │    [✅ Aprobar] [❌ Rechazar]                       │
│     │                                                    │
│     ◄── User taps ✅ Aprobar                             │
│     │                                                    │
│     └──► make_phone_call("+34900850840", script)        │
│  Step 4: ✅ check_call_status → call completed           │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
         "Done. I called Endesa, here's the recording..."
```

### Safety Layers

| Category | Examples | Requires Approval? |
|----------|---------|-------------------|
| `safe` | Web search, check status, read calendar | ❌ No |
| `moderate` | Create Notion task, add calendar event | ❌ No |
| `dangerous` | Phone call, send email, fill web form | ✅ **YES** |
| `critical` | Make payment, sign contract | ✅ **YES** (never auto-approved) |

**If no approval callback is configured, dangerous actions are automatically rejected.** This is a fail-safe — SPESION never does something dangerous without your explicit consent.

---

## New Components Created

### Autonomous Engine (`src/autonomous/`)

| File | Purpose |
|------|---------|
| `planner.py` | LLM-based plan decomposition, `PlanStep`, `Plan`, `PlanExecutor`, retry logic, context passing |
| `task_queue.py` | SQLite-backed background task queue with async worker |
| `approval.py` | Human-in-the-loop approval gates, Telegram/Discord formatters, timeout handling |

### New Tools (`src/tools/`)

| File | Tools |
|------|-------|
| `phone_tool.py` | `make_phone_call`, `check_call_status`, `send_sms` |
| `email_tool.py` | `send_email`, `draft_email`, `check_email_config` |
| `browser_tool.py` | `browse_webpage`, `take_screenshot`, `browser_fill_form`, `browser_extract_data`, `search_web_browser` |
| `autonomous_tools.py` | `execute_autonomous_plan`, `check_task_status`, `list_background_tasks`, `get_pending_approvals`, `respond_approval` |

### Modified Files

| File | Changes |
|------|---------|
| `src/core/config.py` | Added `TwilioSettings`, `SMTPSettings`, `AutonomousSettings` |
| `src/core/state.py` | Added `active_plan_id`, `pending_approval_step` |
| `src/core/supervisor.py` | Added autonomous keywords routing ("llama a", "email", "queja", "factura", etc.) |
| `src/agents/executive.py` | Added autonomous_tools, email_tools, phone_tools, browser_tools |
| `src/agents/tycoon.py` | Added autonomous_tools, browser_tools |

---

## Complete .env Reference

### Core LLM

```env
# Ollama (local — must be running)
OLLAMA_BASE_URL=http://localhost:11434

# Cloud providers (at least one recommended)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

### Telegram

```env
TELEGRAM_BOT_TOKEN=1234567890:AAE...
TELEGRAM_ALLOWED_USER_IDS=123456789
```

### Discord

```env
DISCORD_BOT_TOKEN=OTk...
DISCORD_GUILD_ID=1234567890123456789
```

### Google Calendar

```env
GOOGLE_CREDENTIALS_PATH=./data/google_calendar_credentials.json
# Token auto-generated at ./data/google_token.json
```

### Garmin

```env
GARMIN_EMAIL=you@email.com
GARMIN_PASSWORD=yourpassword
```

### IBKR

```env
IBKR_FLEX_TOKEN=123456789012345678
IBKR_FLEX_QUERY_ID=1234567
```

### Notion

```env
NOTION_API_KEY=secret_...
NOTION_TASKS_DATABASE_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
NOTION_JOURNAL_DATABASE_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
NOTION_CRM_DATABASE_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
NOTION_BOOKS_DATABASE_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
NOTION_TRAININGS_DATABASE_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
NOTION_FINANCE_DATABASE_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
NOTION_TRANSACTIONS_DATABASE_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 📞 Twilio (Phone Calls & SMS) — NEW

```env
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+34...           # Your Twilio number (Spanish number recommended)
TWILIO_CALLBACK_URL=https://your-server.com/twilio/status  # Optional
```

### 📧 SMTP (Email) — NEW

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=you@gmail.com
SMTP_PASSWORD=xxxx-xxxx-xxxx-xxxx    # Gmail App Password (NOT your real password)
SMTP_FROM_NAME=Eric González
```

### 🤖 Autonomous Engine — NEW

```env
AUTONOMOUS_ENABLED=true
AUTONOMOUS_APPROVAL_TIMEOUT_SECONDS=300    # 5 minutes to approve
AUTONOMOUS_MAX_PLAN_STEPS=15
AUTONOMOUS_BACKGROUND_WORKER_ENABLED=true
```

### Search

```env
TAVILY_API_KEY=tvly-...              # Optional, falls back to DuckDuckGo
```

### Heartbeat & Memory

```env
HEARTBEAT_ENABLED=true
HEARTBEAT_CHECK_INTERVAL_MINUTES=30
HEARTBEAT_ACTIVE_HOURS_START=07:00
HEARTBEAT_ACTIVE_HOURS_END=23:30
HEARTBEAT_TIMEZONE=Europe/Madrid
```

### API Server

```env
SPESION_API_KEY=your-secure-api-key
SPESION_HOST=0.0.0.0
SPESION_PORT=8100
```

---

## Server Setup (Windows 11)

### Prerequisites

```powershell
# 1. Install Python 3.11+
winget install Python.Python.3.11

# 2. Install Ollama
winget install Ollama.Ollama

# 3. Clone/copy SPESION to your server
cd C:\SPESION

# 4. Create virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# 5. Install dependencies
pip install -r requirements.txt

# 6. Install additional dependencies for autonomous features
pip install twilio playwright
playwright install chromium

# 7. Pull local models
ollama pull llama3.2:3b
ollama pull qwen2.5:7b
```

### Configure

```powershell
# Copy and edit environment
Copy-Item .env.example .env
notepad .env
# Fill in ALL values from the .env reference above
```

### First Run

```powershell
# Start Ollama
Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden

# Activate venv
.venv\Scripts\Activate.ps1

# First-time Google Calendar auth
python main.py --cli
# Ask: "what's on my calendar today?" → browser opens → authorize

# Verify all connections
# Ask: "run full system status" → checks Garmin, Notion, IBKR, Calendar, Email, Twilio
```

### Daily Start Script (`start_spesion.ps1`)

```powershell
# Start Ollama
Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
Start-Sleep -Seconds 3

# Activate venv
cd C:\SPESION
.venv\Scripts\Activate.ps1

# Start SPESION with all features
python main.py --api --heartbeat --telegram
```

### Run as Windows Service (NSSM)

```powershell
nssm install SPESION "C:\SPESION\.venv\Scripts\python.exe" "C:\SPESION\main.py --api --heartbeat --telegram"
nssm set SPESION AppDirectory "C:\SPESION"
nssm set SPESION AppEnvironmentExtra "PATH=C:\SPESION\.venv\Scripts;%PATH%"
nssm start SPESION
```

---

## Windows Server Security Configuration

> ⚠️ SPESION contains your API keys, bank credentials (IBKR), Garmin password, Twilio tokens, and Gmail app password. These must be protected. A server with no hardening is a liability.

### 1. Run SPESION as a Dedicated Non-Admin User

Never run SPESION as your main admin account. Create a restricted service account:

```powershell
# Create local service account
net user spesion_svc StrongPassword123! /add
net localgroup Users spesion_svc /add

# Grant access ONLY to C:\SPESION
icacls C:\SPESION /grant spesion_svc:(OI)(CI)F /T
icacls C:\SPESION /deny Users:(OI)(CI)W /T   # block everyone else from writing

# Update NSSM to run under this account
nssm set SPESION ObjectName ".\spesion_svc" "StrongPassword123!"
```

### 2. Protect the .env File

The `.env` file contains ALL your secrets. Lock it down:

```powershell
# Remove all inherited permissions
icacls C:\SPESION\.env /inheritance:r

# Grant access only to the service account and your admin user
icacls C:\SPESION\.env /grant spesion_svc:(R)
icacls C:\SPESION\.env /grant YourAdminUser:(F)

# Verify — only 2 entries should appear
icacls C:\SPESION\.env
```

> **Never commit `.env` to Git.** Add it to `.gitignore` immediately:
> ```
> echo ".env" >> .gitignore
> ```

### 3. Protect Sensitive Data Folders

```powershell
# Restrict the data/ folder (contains OAuth tokens, SQLite DBs, screenshots)
icacls C:\SPESION\data /inheritance:r
icacls C:\SPESION\data /grant spesion_svc:(OI)(CI)F
icacls C:\SPESION\data /grant YourAdminUser:(OI)(CI)F

# The Google OAuth token is as powerful as your Google account
# It should NEVER be world-readable
icacls C:\SPESION\data\google_token.json /grant spesion_svc:(R)
icacls C:\SPESION\data\google_token.json /grant YourAdminUser:(F)
```

### 4. Windows Firewall Rules

SPESION's API runs on port 8100. Do not expose it directly to the internet.

```powershell
# Block port 8100 from ALL external access by default
New-NetFirewallRule -DisplayName "SPESION API - BLOCK External" `
    -Direction Inbound -Protocol TCP -LocalPort 8100 `
    -Action Block -Profile Any

# Allow ONLY from your local network (e.g. 192.168.1.0/24)
New-NetFirewallRule -DisplayName "SPESION API - Allow LAN" `
    -Direction Inbound -Protocol TCP -LocalPort 8100 `
    -RemoteAddress 192.168.1.0/24 -Action Allow

# Allow Ollama only from localhost (never expose it externally)
New-NetFirewallRule -DisplayName "Ollama - Localhost Only" `
    -Direction Inbound -Protocol TCP -LocalPort 11434 `
    -RemoteAddress 127.0.0.1 -Action Allow

New-NetFirewallRule -DisplayName "Ollama - BLOCK External" `
    -Direction Inbound -Protocol TCP -LocalPort 11434 `
    -Action Block

# Block all other unusual inbound traffic
Set-NetFirewallProfile -Profile Domain,Public,Private -DefaultInboundAction Block
```

### 5. Reverse Proxy with HTTPS (Required for Twilio Webhooks)

Twilio requires a public HTTPS URL to send call status callbacks. Use **Caddy** (simplest on Windows) as a reverse proxy with automatic SSL:

```powershell
# Install Caddy
winget install CaddyServer.Caddy
```

Create `C:\Caddy\Caddyfile`:

```
your-domain.duckdns.org {
    reverse_proxy localhost:8100

    # Only allow Twilio callback IPs to reach /twilio/*
    @twilio {
        path /twilio/*
        remote_ip 54.172.60.0/23 34.203.250.0/23 52.215.127.0/24
    }

    # Rate-limit the API
    route /api/* {
        rate_limit {
            zone spesion 10r/s
        }
        reverse_proxy localhost:8100
    }
}
```

Start Caddy:
```powershell
Start-Process caddy -ArgumentList "run --config C:\Caddy\Caddyfile" -WindowStyle Hidden
```

Update your `.env`:
```env
TWILIO_CALLBACK_URL=https://your-domain.duckdns.org/twilio/status
```

> **Free DDNS (Dynamic DNS):** If you don't have a static IP, use https://www.duckdns.org — free, supports HTTPS via Caddy automatically.

### 6. API Key Authentication

The SPESION API (port 8100) requires a bearer token. Generate a strong one:

```powershell
# Generate a strong random API key (PowerShell)
-join ((1..40) | ForEach { [char]((65..90) + (97..122) + (48..57) | Get-Random) })
```

Set it in `.env`:
```env
SPESION_API_KEY=your-40-char-random-key-here
```

All API calls must include:
```http
Authorization: Bearer your-40-char-random-key-here
```

### 7. Windows Defender Exclusions (Performance)

Defender can falsely flag Playwright's Chromium binary and slow SPESION down. Add exclusions:

```powershell
# Exclude SPESION directory from real-time scanning
Add-MpPreference -ExclusionPath "C:\SPESION"

# Exclude Playwright browser binaries specifically
$playwright_path = "$env:LOCALAPPDATA\ms-playwright"
Add-MpPreference -ExclusionPath $playwright_path

# Exclude Ollama models (large binary files, slow to scan)
$ollama_path = "$env:LOCALAPPDATA\Ollama"
Add-MpPreference -ExclusionPath $ollama_path
```

> ⚠️ Only add these exclusions after confirming the code is clean. Do not exclude the entire `C:\` drive.

### 8. Secrets Rotation Schedule

API keys and tokens should be rotated regularly. Set a reminder:

| Secret | Rotation Frequency | How to Rotate |
|--------|--------------------|---------------|
| `OPENAI_API_KEY` | Every 90 days | platform.openai.com → API Keys |
| `ANTHROPIC_API_KEY` | Every 90 days | console.anthropic.com → API Keys |
| `SPESION_API_KEY` | Every 60 days | Generate new random key |
| `TWILIO_AUTH_TOKEN` | Every 6 months | Twilio Console → Rotate Token |
| `SMTP_PASSWORD` (App Password) | Every 6 months | Google Account → App Passwords |
| `NOTION_API_KEY` | Every 6 months | Notion → Integrations → Regenerate |
| `GARMIN_PASSWORD` | After any breach | myaccount.garmin.com |
| Google OAuth token | Auto-refreshes | Automatic via refresh token |

### 9. Audit Logs

Enable Windows audit logging to detect unauthorized access:

```powershell
# Enable logon/logoff auditing
AuditPol /set /subcategory:"Logon" /success:enable /failure:enable
AuditPol /set /subcategory:"Logoff" /success:enable

# Enable file access auditing on the SPESION data folder
AuditPol /set /subcategory:"File System" /success:enable /failure:enable

# Enable process creation auditing (detects if Playwright is hijacked)
AuditPol /set /subcategory:"Process Creation" /success:enable
```

View logs:
```powershell
# Check recent failed logons
Get-EventLog -LogName Security -InstanceId 4625 -Newest 20

# Check SPESION process starts
Get-EventLog -LogName Security -InstanceId 4688 -Newest 20 | Where-Object {$_.Message -like "*python*"}
```

### 10. NSSM Service Hardening

```powershell
# Limit NSSM service restart attempts (prevent crash loops)
nssm set SPESION AppThrottle 5000         # min 5s between restarts
nssm set SPESION AppRestartDelay 10000    # 10s after crash before restart
nssm set SPESION AppExit Default Restart  # always restart on exit

# Log SPESION stdout/stderr to rotating files
nssm set SPESION AppStdout C:\SPESION\logs\stdout.log
nssm set SPESION AppStderr C:\SPESION\logs\stderr.log
nssm set SPESION AppRotateFiles 1
nssm set SPESION AppRotateBytes 10485760  # rotate at 10 MB
nssm set SPESION AppRotateOnline 1        # rotate without restart

# Create log directory
New-Item -ItemType Directory -Force -Path C:\SPESION\logs
icacls C:\SPESION\logs /grant spesion_svc:(OI)(CI)F
```

### 11. Remote Access — Use RDP with NLA (Not Exposed to Internet)

Do NOT expose RDP (port 3389) to the internet.

```powershell
# Ensure NLA is required for RDP (blocks unauthenticated scans)
Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp" `
    -Name UserAuthentication -Value 1

# Disable RDP from external IPs at the firewall (VPN only)
New-NetFirewallRule -DisplayName "Block RDP External" `
    -Direction Inbound -Protocol TCP -LocalPort 3389 `
    -RemoteAddress Internet -Action Block

# Allow RDP only from LAN
New-NetFirewallRule -DisplayName "Allow RDP LAN" `
    -Direction Inbound -Protocol TCP -LocalPort 3389 `
    -RemoteAddress 192.168.1.0/24 -Action Allow
```

For **remote access from outside your network**, use:
- **Tailscale** (recommended — zero-config VPN): https://tailscale.com/download/windows
  ```powershell
  winget install Tailscale.Tailscale
  # Login and your server becomes accessible via VPN IP only
  ```
- Or **WireGuard** if you prefer self-hosted VPN.

### Security Summary Checklist

```
□  1. SPESION runs as dedicated non-admin service account (spesion_svc)
□  2. .env file is readable ONLY by spesion_svc and your admin user
□  3. data/ folder is locked to spesion_svc only
□  4. Port 8100 is blocked from internet (LAN only or behind Caddy HTTPS)
□  5. Port 11434 (Ollama) is localhost only
□  6. RDP is blocked from internet — access via Tailscale VPN only
□  7. SPESION_API_KEY is a 40+ character random string
□  8. Windows Defender exclusions added for Playwright + Ollama
□  9. NSSM logs enabled with rotation at C:\SPESION\logs
□ 10. Audit logging enabled for logon events and process creation
□ 11. Caddy reverse proxy with HTTPS for Twilio webhooks
□ 12. .env added to .gitignore
□ 13. Secret rotation reminders set in calendar
```

---

## Twilio Setup (Phone Calls & SMS)

### Why Twilio?

Twilio lets SPESION make **real phone calls** and **send SMS**. When you say "call Endesa about my wrong receipt", SPESION:

1. Generates a TTS script (in Spanish)
2. Calls the number via Twilio
3. Plays the script with a natural voice (Amazon Polly Lucia)
4. Records the call for your review
5. Reports the result

### Step 1: Create a Twilio Account

1. Go to https://www.twilio.com/try-twilio
2. Sign up (free trial includes $15 credit — enough for ~100 calls)
3. Verify your phone number

### Step 2: Get a Phone Number

1. In the Twilio Console → **Phone Numbers → Buy a Number**
2. Search for a **Spain (+34)** number (recommended for calling Spanish companies)
   - If none available, get a US number and enable international calling
3. Buy the number (~$1/month)

### Step 3: Get Your Credentials

1. **Dashboard → Account SID** → `TWILIO_ACCOUNT_SID`
2. **Dashboard → Auth Token** → `TWILIO_AUTH_TOKEN`
3. **Phone number** (e.g. +34612345678) → `TWILIO_PHONE_NUMBER`

### Step 4: Configure in .env

```env
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_PHONE_NUMBER=+34612345678
```

### Step 5: Test

In Telegram:
```
"Call +34900850840 to complain about my wrong gas receipt from January"
```

SPESION will:
1. Generate a plan (search → draft script → call)
2. Ask for your approval via Telegram button
3. Make the call
4. Report the status and recording

### Pricing

| Action | Cost |
|--------|------|
| Outbound call (Spain) | ~$0.05/min |
| SMS (Spain) | ~$0.07/message |
| Phone number (Spain) | ~$1/month |

---

## Email Setup (SMTP / Gmail API)

### Option A: Gmail App Password (Simplest)

1. Go to https://myaccount.google.com/apppasswords
2. Generate an App Password for "Mail"
3. Copy the 16-character password

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your.email@gmail.com
SMTP_PASSWORD=xxxx-xxxx-xxxx-xxxx
SMTP_FROM_NAME=Eric González
```

### Option B: Gmail API (Uses same OAuth as Calendar)

No extra setup needed if you already authenticated Google Calendar.
Just ensure your OAuth consent screen includes the Gmail scope:
```
https://www.googleapis.com/auth/gmail.send
```

SPESION auto-detects available backends and uses the best one.

### Test

In Telegram:
```
"Send an email to soporte@endesa.es about my wrong gas receipt"
```

SPESION will:
1. Draft the email (professional tone, Spanish)
2. Show you the draft
3. Ask for approval
4. Send it

---

## Browser Automation Setup (Playwright)

### Install

```bash
pip install playwright
playwright install chromium
```

That's it. No API keys needed. Playwright runs a headless Chromium browser.

### What it can do

| Tool | Use case |
|------|---------|
| `browse_webpage` | Read any URL, extract text content |
| `take_screenshot` | Visual proof of web pages |
| `browser_fill_form` | Fill complaint forms, contact forms |
| `browser_extract_data` | Scrape prices, order status, tracking |
| `search_web_browser` | Google search via real browser |

### Example

```
"Go to Endesa's website and find their complaint form. Fill it with my details
 and my complaint about the wrong gas receipt from January."
```

---

## Telegram Bot Configuration

### Create the Bot

1. Open Telegram → search `@BotFather`
2. `/newbot` → name: `SPESION` → username: `spesion_your_bot`
3. Copy token → `TELEGRAM_BOT_TOKEN`

### Get Your User ID

1. Search `@userinfobot` → `/start`
2. Copy your ID → `TELEGRAM_ALLOWED_USER_IDS`

### Set Commands (Recommended)

Send to BotFather:
```
/setcommands
```
Paste:
```
start - Start SPESION
status - System status
approve - View pending approvals
tasks - List background tasks
clear - Clear conversation
reflect - Trigger nightly reflection
```

### Approval Integration

When SPESION needs approval for a dangerous action, you'll see:

```
🔐 SPESION necesita tu aprobación

Voy a llamar a Endesa (+34 900 850 840) para reclamar
la factura incorrecta del gas de enero 2026.

⚠️ Esta acción contacta a terceros.
Responde en los próximos 5 minutos.

[✅ Aprobar]  [❌ Rechazar]
```

Just tap the button. If you don't respond in 5 minutes, the action is auto-rejected.

---

## Discord Bot Configuration

### Create the Application

1. https://discord.com/developers/applications → New Application → `SPESION`
2. Bot → Add Bot → copy token → `DISCORD_BOT_TOKEN`
3. Enable: ✅ Server Members Intent, ✅ Message Content Intent

### Invite to Server

OAuth2 → URL Generator:
- Scopes: `bot`, `applications.commands`
- Permissions: Send Messages, Read Message History, Use Slash Commands, Embed Links, Attach Files

### Channel Mapping

```env
DISCORD_GUILD_ID=your_guild_id
DISCORD_CHANNEL_TYCOON=finance
DISCORD_CHANNEL_SCHOLAR=research
DISCORD_CHANNEL_TECHLEAD=engineering
DISCORD_CHANNEL_COACH=health
DISCORD_CHANNEL_EXECUTIVE=planning
```

---

## Google Calendar Setup

1. https://console.cloud.google.com → enable Google Calendar API
2. Create OAuth Desktop credentials → download JSON → `data/google_calendar_credentials.json`
3. Run `python main.py --cli` → ask about calendar → browser opens → authorize
4. Token saved to `data/google_token.json` (auto, survives reboots)

**7 tools**: get_calendar_events, get_today_agenda, get_week_agenda, create_calendar_event, update_calendar_event, delete_calendar_event, find_free_slots

---

## Garmin Setup

```env
GARMIN_EMAIL=your@email.com
GARMIN_PASSWORD=yourpassword
```

Auto-reconnect on session expiry. MFA detected and reported clearly.

**5 tools**: get_garmin_stats, get_garmin_activities, get_training_status, get_garmin_weekly_summary, check_garmin_connection

---

## IBKR Setup

1. IBKR Account Management → Reports → Flex Queries → Flex Web Service
2. Generate token (18 digits) → `IBKR_FLEX_TOKEN`
3. Create Activity Flex Query → note Query ID (7 digits) → `IBKR_FLEX_QUERY_ID`

**2 tools**: sync_investments_to_notion, check_ibkr_connection

---

## Notion Setup

1. https://www.notion.so/my-integrations → New Integration → `SPESION`
2. Copy Internal Integration Token → `NOTION_API_KEY`
3. Share each database with the integration
4. Copy database IDs from URLs → `.env`

Or ask SPESION: `"Set up my Notion workspace"` — auto-creates all 7 databases.

**18 tools** across Tasks, Journal, CRM, Books, Training, Finance, Setup.

---

## Running SPESION

### CLI Modes

```bash
# Interactive CLI
python main.py --cli

# API server (port 8100)
python main.py --api

# Telegram bot
python main.py --telegram

# Discord bot
python main.py --discord

# With heartbeat scheduler
python main.py --api --heartbeat --telegram

# System status
python main.py --status

# Trigger reflection
python main.py --reflect
```

### Production Command (Server)

```bash
# Recommended: API + Heartbeat + Telegram
python main.py --api --heartbeat --telegram
```

This starts:
- FastAPI server on port 8100
- HeartbeatRunner (daily digest, weekly review)
- Telegram bot (with approval buttons)
- Background task queue worker

---

## How the Approval System Works

### Flow

```
SPESION wants to do something dangerous
    │
    ▼
Creates approval request in memory store
    │
    ▼
Sends formatted message to Telegram/Discord
    │
    ├─ User taps ✅ → approval.respond_to_approval(step_id, True)
    │                   → plan continues
    │
    ├─ User taps ❌ → approval.respond_to_approval(step_id, False)
    │                   → step skipped, plan continues with next step
    │
    └─ 5 min timeout → auto-rejected (fail-safe)
```

### What's Classified as Dangerous

| Tool | Category | Needs Approval |
|------|----------|---------------|
| `make_phone_call` | dangerous | ✅ Always |
| `send_email` | dangerous | ✅ Always |
| `send_sms` | dangerous | ✅ Always |
| `browser_fill_form` (with submit) | dangerous | ✅ Always |
| `browse_webpage` | safe | ❌ |
| `take_screenshot` | safe | ❌ |
| `search_web_browser` | safe | ❌ |
| `create_calendar_event` | moderate | ❌ |
| `get_tasks` | safe | ❌ |

### Viewing Pending Approvals

Ask SPESION: `"Show pending approvals"` or use the `/approve` command.

---

## Example Autonomous Scenarios

### 1. Call a Company About a Wrong Bill

```
User: "Llama a Endesa porque me han cobrado 47€ de más en la factura de gas de enero"

SPESION:
  Step 1 ✅ search_web_browser("Endesa teléfono reclamaciones España")
           → Found: +34 900 850 840
  Step 2 ✅ Reasoning: Draft call script
           → "Hola, llamo en nombre de Eric González Duro respecto a 
              la factura de gas de enero 2026 que contiene un cargo 
              incorrecto de 47€..."
  Step 3 🔐 make_phone_call("+34900850840", script)
           → Approval sent to Telegram
           → User approves ✅
           → Call made, recorded
  Step 4 ✅ check_call_status(call_sid)
           → Duration: 45s, recording available

Report: "He llamado a Endesa. La llamada duró 45 segundos. 
         Aquí tienes la grabación: [link]"
```

### 2. Email a Complaint

```
User: "Send an email to reclamaciones@endesa.es about my wrong gas receipt"

SPESION:
  Step 1 ✅ draft_email(to, subject, purpose)
  Step 2 ✅ Reasoning: compose email body
  Step 3 🔐 send_email(to, subject, body)
           → Approval sent to Telegram
           → User approves ✅
           → Email sent

Report: "Email sent to reclamaciones@endesa.es. Subject: Reclamación factura gas enero 2026"
```

### 3. Check Order Status Online

```
User: "Check my Amazon order status, order #123-456-789"

SPESION:
  Step 1 ✅ browse_webpage("https://amazon.es/your-orders") → extracted order info
  Step 2 ✅ browser_extract_data(selectors) → "Delivered Feb 20"

Report: "Tu pedido #123-456-789 fue entregado el 20 de febrero."
```

### 4. Research + Act Combo

```
User: "Find the cheapest gym near me, get their schedule, and add 
       'Gym trial' to my calendar for Saturday morning"

SPESION:
  Step 1 ✅ search_web_browser("cheapest gym near [location]")
  Step 2 ✅ browse_webpage(gym_url) → extract schedule
  Step 3 ✅ create_calendar_event("Gym trial", Saturday 10:00)

Report: "Found Basic-Fit at €19.99/month. Added 'Gym trial' to your 
         calendar for Saturday at 10:00."
```

---

## Full Feature Comparison: SPESION vs OpenClaw

| Capability | OpenClaw | SPESION 3.0 |
|-----------|---------|-------------|
| Multi-agent routing | ✅ | ✅ (8 agents, keyword + LLM) |
| Multi-model routing | ✅ | ✅ (11 models, privacy-aware) |
| Agent self-learning | ✅ | ✅ (SkillStore, Jaccard+LLM) |
| Persistent memory | ✅ | ✅ (3-tier: episodic+semantic+skills) |
| Nightly reflection | ✅ | ✅ (CognitiveLoop) |
| Heartbeat scheduler | ✅ | ✅ (HeartbeatRunner) |
| **Phone calls** | ✅ | ✅ **(Twilio + TTS + recording)** |
| **Send emails** | ✅ | ✅ **(SMTP + Gmail API)** |
| **Send SMS** | ❌ | ✅ **(Twilio)** |
| **Browser automation** | ✅ | ✅ **(Playwright — browse, fill, scrape)** |
| **Multi-step planner** | ✅ | ✅ **(LLM plan generation + sequential execution)** |
| **Human approval gates** | ❌ | ✅ **(Telegram/Discord buttons, 5min timeout)** |
| **Background task queue** | ❌ | ✅ **(SQLite-backed, async worker)** |
| Code sandbox | ✅ | ✅ (Docker sandbox) |
| Web search | ✅ | ✅ (Tavily/DuckDuckGo + browser) |
| Finance integration | ❌ | ✅ (IBKR + Bitget + Notion sync) |
| Health integration | ❌ | ✅ (Garmin — stats + HRV + weekly) |
| Calendar management | ❌ | ✅ (Google Calendar — 7 tools) |
| Knowledge base | ❌ | ✅ (Notion — 18 tools, 7 DB types) |
| Workspace identity | ✅ | ✅ (SOUL.md + 5 workspace files) |
| Context compaction | ✅ | ✅ (6000 token budget) |
| Local privacy mode | Partial | ✅ (3 agents fully local) |
| Telegram interface | ❌ | ✅ |
| Discord interface | ✅ | ✅ |
| Docker deployment | ✅ | ✅ |

---

## Production Deployment with Docker

This is the recommended way to run SPESION on your Windows 11 server. Docker containers isolate SPESION, Ollama, and the code sandbox cleanly and make restarts, updates, and rollbacks trivial.

### What the Docker Setup Includes

| Container | Image | Role |
|-----------|-------|------|
| `spesion` | Built from `docker/Dockerfile` | Main app: API + Telegram + Heartbeat |
| `spesion-ollama` | `ollama/ollama:latest` | Local LLM inference — internal only |
| `spesion-caddy` | `caddy:2-alpine` | HTTPS reverse proxy (auto TLS) |
| `spesion-sandbox` | Built from `docker/Dockerfile.sandbox` | Isolated code execution — on demand |

**Network topology:**

```
Internet
    │
    ▼
 Caddy :443 (HTTPS, Let's Encrypt)
    │
    └──► spesion:8100  (internal Docker network)
              │
              └──► ollama:11434 (internal Docker network)
              └──► docker.sock (read-only, for sandbox spawning)

sandbox ─── network_mode: none (completely isolated)
```

**Ollama is never exposed to the internet.** Caddy is the only container with public ports.

---

### Step 1 — Install Docker on Windows 11

```powershell
# Option A: Docker Desktop (easiest — includes GUI)
winget install Docker.DockerDesktop

# Option B: Docker Engine via WSL2 (lighter — no GUI)
# Enable WSL2 first, then install Docker inside WSL2
wsl --install
# Then in WSL2:
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
```

After installing, verify:
```powershell
docker --version
docker compose version
```

---

### Step 2 — Get a Domain Name (Required for HTTPS)

Caddy needs a domain to issue a Let's Encrypt certificate. The easiest free option is **DuckDNS**:

1. Go to https://www.duckdns.org
2. Sign in with Google/GitHub
3. Create a subdomain: e.g. `spesion-eric.duckdns.org`
4. Point it to your **server's public IP address**
   - Find your public IP: `curl ifconfig.me`
5. If your IP is dynamic (changes), install the DuckDNS updater on Windows:

```powershell
# Download DuckDNS auto-update script
# Create C:\DuckDNS\update.ps1:
$token = "your-duckdns-token"
$domain = "spesion-eric"
Invoke-WebRequest "https://www.duckdns.org/update?domains=$domain&token=$token&ip=" -UseBasicParsing

# Schedule it to run every 5 minutes via Task Scheduler
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-File C:\DuckDNS\update.ps1"
$trigger = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Minutes 5) -Once -At (Get-Date)
Register-ScheduledTask -TaskName "DuckDNS Update" -Action $action -Trigger $trigger -RunLevel Highest
```

---

### Step 3 — Open Firewall Ports

```powershell
# Allow HTTP and HTTPS through Windows Firewall
New-NetFirewallRule -DisplayName "Caddy HTTP" -Direction Inbound -Protocol TCP -LocalPort 80 -Action Allow
New-NetFirewallRule -DisplayName "Caddy HTTPS" -Direction Inbound -Protocol TCP -LocalPort 443 -Action Allow
New-NetFirewallRule -DisplayName "Caddy HTTPS UDP (HTTP3)" -Direction Inbound -Protocol UDP -LocalPort 443 -Action Allow

# Block port 8100 externally (Caddy proxies it, no need for direct access)
New-NetFirewallRule -DisplayName "Block SPESION Direct" -Direction Inbound -Protocol TCP -LocalPort 8100 -Action Block

# If your router does NAT, also forward ports 80 and 443 to your server's LAN IP
# Router admin panel → Port Forwarding → 80 & 443 → server LAN IP (e.g. 192.168.1.50)
```

---

### Step 4 — Configure the Caddyfile

Edit `Caddyfile` at the project root (already created):

```
your-domain.duckdns.org {
    reverse_proxy spesion:8100 { ... }
}
```

Replace `your-domain.duckdns.org` with your actual subdomain:

```powershell
# Example: replace the placeholder
(Get-Content Caddyfile) -replace 'your-domain.duckdns.org', 'spesion-eric.duckdns.org' | Set-Content Caddyfile
```

Also update `.env`:
```env
TWILIO_CALLBACK_URL=https://spesion-eric.duckdns.org/twilio/status
```

---

### Step 5 — Prepare the Data Directory

Before the first run, copy your Google Calendar credentials into the data folder. Docker will mount this folder into the container:

```powershell
# Create data folder if not exists
New-Item -ItemType Directory -Force -Path C:\SPESION\data

# Copy your Google credentials
Copy-Item C:\path\to\google_calendar_credentials.json C:\SPESION\data\

# Set permissions (see Security section)
icacls C:\SPESION\data /inheritance:r
icacls C:\SPESION\data /grant spesion_svc:(OI)(CI)F
```

---

### Step 6 — Build and Start

```powershell
cd C:\SPESION

# Build all images (first time — takes 5-10 minutes)
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml build

# Pull Ollama models BEFORE starting (do this once)
docker compose -f docker/docker-compose.yml up -d ollama
Start-Sleep -Seconds 10
docker exec spesion-ollama ollama pull llama3.2:3b
docker exec spesion-ollama ollama pull qwen2.5:7b

# Start everything in production mode
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml up -d

# Check status
docker compose ps
```

After ~60 seconds, verify:
```powershell
# Health check
curl http://localhost:8100/health

# Test HTTPS (from another machine or using your domain)
curl https://spesion-eric.duckdns.org/health
```

---

### Step 7 — Google Calendar OAuth (First Run Only)

The Google Calendar OAuth flow requires a browser, which doesn't work headlessly inside Docker. Run it once on your machine:

```powershell
# Run the auth flow outside Docker (one-time)
cd C:\SPESION
.venv\Scripts\Activate.ps1
python main.py --cli
# Ask: "what's on my calendar today?" → browser opens → authorize → done
# This saves data/google_token.json
```

The token is saved in `data/google_token.json`. Since the `data/` folder is a Docker volume mounted from your host, the container will pick it up automatically:

```powershell
# Copy token into the data folder Docker uses
Copy-Item .\data\google_token.json C:\SPESION\data\
```

---

### Step 8 — Useful Docker Commands

```powershell
# ── Monitoring ──────────────────────────────────────────────────────────
# Watch live logs from all containers
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml logs -f

# Watch only SPESION logs
docker logs -f spesion

# Check resource usage
docker stats

# Check container health
docker inspect --format='{{.State.Health.Status}}' spesion

# ── Updates ─────────────────────────────────────────────────────────────
# Pull latest changes and rebuild
git pull
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml build spesion
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml up -d spesion
# (Ollama and Caddy keep running — zero downtime for non-SPESION changes)

# ── Restart ─────────────────────────────────────────────────────────────
docker restart spesion

# ── Stop everything ──────────────────────────────────────────────────────
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml down

# ── Stop without losing data ─────────────────────────────────────────────
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml stop

# ── Access container shell ───────────────────────────────────────────────
docker exec -it spesion bash

# ── View logs file inside container ─────────────────────────────────────
docker exec spesion tail -100 /app/logs/spesion.log

# ── Ollama: add a new model ─────────────────────────────────────────────
docker exec spesion-ollama ollama pull llama3.3:70b

# ── Backup data volume ───────────────────────────────────────────────────
docker run --rm -v spesion-data:/data -v C:\SPESION\backup:/backup alpine \
    tar czf /backup/spesion-data-$(date +%Y%m%d).tar.gz -C /data .
```

---

### Step 9 — Auto-Start on Windows Boot

Make Docker Desktop start with Windows, then create a scheduled task to start the containers at boot:

```powershell
# Docker Desktop: Settings → General → ✅ "Start Docker Desktop when you log in to Windows"

# Create auto-start task for SPESION containers
$action = New-ScheduledTaskAction `
    -Execute "docker" `
    -Argument "compose -f C:\SPESION\docker\docker-compose.yml -f C:\SPESION\docker\docker-compose.prod.yml up -d" `
    -WorkingDirectory "C:\SPESION"

$trigger = New-ScheduledTaskTrigger -AtStartup

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask `
    -TaskName "SPESION Docker Start" `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -RunLevel Highest `
    -Force
```

---

### Step 10 — Automated Daily Backups

```powershell
# Create C:\SPESION\scripts\backup.ps1:
$date = Get-Date -Format "yyyy-MM-dd"
$backup_dir = "C:\SPESION\backup"
New-Item -ItemType Directory -Force -Path $backup_dir

# Backup Docker volume (ChromaDB, SQLite, OAuth tokens)
docker run --rm `
    -v spesion-data:/data `
    -v ${backup_dir}:/backup `
    alpine tar czf /backup/spesion-data-${date}.tar.gz -C /data .

# Backup Ollama models (optional — large files, skip if disk is limited)
# docker run --rm -v ollama-data:/data -v ${backup_dir}:/backup alpine `
#     tar czf /backup/ollama-models-${date}.tar.gz -C /data .

# Keep only last 7 days
Get-ChildItem $backup_dir -Filter "spesion-data-*.tar.gz" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -Skip 7 |
    Remove-Item

Write-Host "Backup completed: spesion-data-${date}.tar.gz"

# Schedule it daily at 03:00
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-File C:\SPESION\scripts\backup.ps1"
$trigger = New-ScheduledTaskTrigger -Daily -At "03:00"
Register-ScheduledTask -TaskName "SPESION Daily Backup" -Action $action -Trigger $trigger -RunLevel Highest -Force
```

---

### Production Checklist

```
□  1. Docker Desktop installed and running
□  2. DuckDNS subdomain created and pointing to your public IP
□  3. Caddyfile updated with your domain name
□  4. Ports 80 and 443 forwarded in your router to server LAN IP
□  5. Windows Firewall rules set (80, 443 open; 8100, 11434 blocked externally)
□  6. .env fully configured (all credentials)
□  7. Google Calendar credentials in data/ folder
□  8. docker compose build completed without errors
□  9. Ollama models pulled (llama3.2:3b + qwen2.5:7b minimum)
□ 10. docker compose up -d — all 3 containers green
□ 11. https://your-domain/ returns SPESION response (Let's Encrypt cert active)
□ 12. Telegram bot responding
□ 13. Auto-start scheduled task registered
□ 14. Daily backup scheduled task registered
□ 15. All security steps from the Security section applied
```

---

## Troubleshooting

### "Twilio: could not send call"
- Check `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN`
- Ensure your account has credit (free trial = $15)
- International numbers need geographic permissions enabled in Console

### "SMTP: authentication failed"
- Gmail requires **App Passwords** (not your real password)
- Go to https://myaccount.google.com/apppasswords
- If 2FA is off, you need to enable it first, then generate app password

### "Playwright: browser not found"
```bash
playwright install chromium
```

### "Approval timed out"
- Default timeout is 5 minutes
- Increase: `AUTONOMOUS_APPROVAL_TIMEOUT_SECONDS=600`
- Make sure Telegram notifications are not muted

### "Tool not found: make_phone_call"
- Install: `pip install twilio`
- Verify Twilio credentials in `.env`

### "Plan generation failed"
- Ensure at least one cloud LLM is configured (OpenAI or Anthropic)
- The planner uses GPT-4o or Claude for plan decomposition
- Check: `python main.py --status`

---

## What Else to Do Before Going Live

### Checklist

```
□  1. Fill complete .env with ALL credentials
□  2. Install all dependencies: pip install -r requirements.txt twilio playwright
□  3. playwright install chromium
□  4. Pull Ollama models: ollama pull llama3.2:3b && ollama pull qwen2.5:7b
□  5. First-run Google Calendar auth: python main.py --cli
□  6. Test each integration:
       - "Check Garmin connection"
       - "Check Notion connection"
       - "Check IBKR connection"
       - "Check email config"
       - "What's on my calendar today?"
□  7. Test autonomous flow:
       - "Draft an email to test@test.com about nothing"
       - Verify approval appears in Telegram
       - Approve → verify email sends (or reject for safety)
□  8. Set up as Windows service (NSSM) or systemd
□  9. Configure Telegram notifications (don't mute the bot!)
□ 10. Start SPESION: python main.py --api --heartbeat --telegram
```

### Post-Launch

- SPESION learns automatically. The more you use it, the better it gets.
- Check learned skills: `sqlite3 data/skill_store.db "SELECT name, confidence FROM skills"`
- Check task history: `sqlite3 data/task_queue.db "SELECT name, status FROM tasks ORDER BY created_at DESC LIMIT 10"`
- Review call recordings in Twilio Console
- Monitor memory bank growth: `python main.py --status`

---

*SPESION 3.0 — Not just an assistant. An autonomous agent that acts in the real world.*
