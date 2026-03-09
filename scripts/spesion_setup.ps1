# =============================================================================
# SPESION 3.0 — Fully Guided Interactive Production Setup (Windows PowerShell)
# =============================================================================
# One script to rule them all. Installs prerequisites, walks you through
# EVERY API key and config, tests connections, pulls models, builds Docker,
# and launches SPESION in production.
#
# Usage (run as Administrator for prerequisite installs):
#   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
#   .\scripts\spesion_setup.ps1
#
# Supports: Windows 10/11 (x64), Windows Server 2019+
# =============================================================================

#Requires -Version 5.1
$ErrorActionPreference = "Stop"

# ─── Colors & Helpers ───────────────────────────────────────────────────────
function Write-Banner {
    Clear-Host
    Write-Host ""
    Write-Host "  ╔═══════════════════════════════════════════════════════════╗" -ForegroundColor Magenta
    Write-Host "  ║                                                           ║" -ForegroundColor Magenta
    Write-Host "  ║     🧠  SPESION 3.0 — Production Setup Wizard  🧠        ║" -ForegroundColor Magenta
    Write-Host "  ║                                                           ║" -ForegroundColor Magenta
    Write-Host "  ║     Your Personal AGI Operating System                    ║" -ForegroundColor Magenta
    Write-Host "  ║     Multi-Agent • Self-Learning • Autonomous              ║" -ForegroundColor Magenta
    Write-Host "  ║                                                           ║" -ForegroundColor Magenta
    Write-Host "  ╚═══════════════════════════════════════════════════════════╝" -ForegroundColor Magenta
    Write-Host ""
}

function Write-Section($text) {
    Write-Host ""
    Write-Host "  ══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host "    $text" -ForegroundColor Cyan
    Write-Host "  ══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Subsection($text) {
    Write-Host ""
    Write-Host "    ── $text ──" -ForegroundColor Blue
    Write-Host ""
}

function Write-Ok($text)   { Write-Host "  ✅ $text" -ForegroundColor Green }
function Write-Warn($text) { Write-Host "  ⚠️  $text" -ForegroundColor Yellow }
function Write-Err($text)  { Write-Host "  ❌ $text" -ForegroundColor Red }
function Write-Info($text) { Write-Host "  ℹ️  $text" -ForegroundColor Blue }

function Ask {
    param(
        [string]$Prompt,
        [string]$Default = "",
        [switch]$Secret
    )
    $display = $Prompt
    if ($Default) { $display += " [default: $Default]" }
    Write-Host "  ⚙️  $display" -ForegroundColor White
    if ($Secret) {
        $secure = Read-Host "     →" -AsSecureString
        $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
        $value = [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    } else {
        $value = Read-Host "     →"
    }
    if ([string]::IsNullOrWhiteSpace($value) -and $Default) { $value = $Default }
    return $value
}

function Ask-YesNo {
    param(
        [string]$Prompt,
        [string]$Default = "y"
    )
    if ($Default -eq "y") { $display = "$Prompt [Y/n]" }
    else                   { $display = "$Prompt [y/N]" }
    Write-Host "  ⚙️  $display" -ForegroundColor White
    $answer = Read-Host "     →"
    if ([string]::IsNullOrWhiteSpace($answer)) { $answer = $Default }
    return ($answer -match '^[yY]')
}

function Write-Env {
    param([string]$Key, [string]$Value)
    $content = Get-Content $script:EnvFile -Raw -ErrorAction SilentlyContinue
    if ($content -match "(?m)^$Key=") {
        $content = $content -replace "(?m)^$Key=.*", "$Key=$Value"
        Set-Content $script:EnvFile -Value $content -NoNewline
    } else {
        Add-Content $script:EnvFile -Value "$Key=$Value"
    }
}

function Test-CommandExists($cmd) {
    return [bool](Get-Command $cmd -ErrorAction SilentlyContinue)
}

# ─── Project Paths ──────────────────────────────────────────────────────────
$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$script:EnvFile = Join-Path $ProjectDir ".env"
$DataDir    = Join-Path $ProjectDir "data"

# Ensure data dir
if (-not (Test-Path $DataDir)) { New-Item -ItemType Directory -Path $DataDir -Force | Out-Null }

# =============================================================================
# STEP 0: Welcome
# =============================================================================

Write-Banner

$WinVer = [System.Environment]::OSVersion.VersionString
$Arch   = if ([Environment]::Is64BitOperatingSystem) { "x64" } else { "x86" }

Write-Host "  🧠 Welcome to SPESION 3.0 Production Setup!" -ForegroundColor White
Write-Host ""
Write-Host "  This wizard will guide you through EVERYTHING:"
Write-Host "    1. Install prerequisites (Docker Desktop, Ollama, Python)" -ForegroundColor Green
Write-Host "    2. Configure ALL API keys and services" -ForegroundColor Green
Write-Host "    3. Set up your personal profile" -ForegroundColor Green
Write-Host "    4. Pull AI models" -ForegroundColor Green
Write-Host "    5. Build & launch Docker containers" -ForegroundColor Green
Write-Host "    6. Verify everything works" -ForegroundColor Green
Write-Host ""
Write-Host "  Detected: Windows $Arch ($WinVer)" -ForegroundColor Blue
Write-Host "  Project:  $ProjectDir" -ForegroundColor Blue
Write-Host ""

if (-not (Ask-YesNo "Ready to begin?")) {
    Write-Host "`n  💜 No worries! Run this script again when you're ready.`n"
    exit 0
}

# =============================================================================
# STEP 1: Prerequisites
# =============================================================================

Write-Section "⚙️  STEP 1/6 — Installing Prerequisites"

# ─── winget ─────────────────────────────────────────────────────────────────
Write-Subsection "📦 Package Manager (winget)"
if (Test-CommandExists winget) {
    Write-Ok "winget available"
} else {
    Write-Warn "winget not found — you may need to install prerequisites manually"
    Write-Info "Get it from: https://aka.ms/getwinget"
}

# ─── Docker ─────────────────────────────────────────────────────────────────
Write-Subsection "🐳 Docker Desktop"

if (Test-CommandExists docker) {
    $dockerVer = docker --version 2>$null
    Write-Ok "Docker installed: $dockerVer"

    # Check daemon
    try {
        docker info 2>$null | Out-Null
        Write-Ok "Docker daemon is running"
    } catch {
        Write-Warn "Docker daemon is NOT running"
        Write-Info "Starting Docker Desktop..."
        Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe" -ErrorAction SilentlyContinue
        Write-Host "  Waiting for Docker to start (30-90 seconds)..." -ForegroundColor Yellow
        for ($i = 0; $i -lt 60; $i++) {
            Start-Sleep -Seconds 2
            try { docker info 2>$null | Out-Null; Write-Ok "Docker daemon started!"; break }
            catch { Write-Host "." -NoNewline }
        }
        Write-Host ""
        try { docker info 2>$null | Out-Null } catch {
            Write-Err "Docker didn't start. Please open Docker Desktop manually and re-run."
            exit 1
        }
    }
} else {
    Write-Info "Docker Desktop not found. Installing..."
    if (Test-CommandExists winget) {
        winget install --id Docker.DockerDesktop --accept-source-agreements --accept-package-agreements
        Write-Warn "Docker Desktop installed — you may need to RESTART your computer"
        Write-Warn "After restart, re-run this script."
        Read-Host "Press Enter to continue (or Ctrl+C to restart first)"
    } else {
        Write-Err "Please install Docker Desktop manually: https://www.docker.com/products/docker-desktop/"
        exit 1
    }
}

# Check docker compose
try {
    $composeVer = docker compose version 2>$null
    Write-Ok "Docker Compose available: $composeVer"
} catch {
    Write-Err "Docker Compose not available. Make sure Docker Desktop is installed."
    exit 1
}

# ─── Ollama ─────────────────────────────────────────────────────────────────
Write-Subsection "🧠 Ollama (Local AI Models)"

if (Test-CommandExists ollama) {
    Write-Ok "Ollama already installed"
} else {
    Write-Info "Installing Ollama..."
    if (Test-CommandExists winget) {
        winget install --id Ollama.Ollama --accept-source-agreements --accept-package-agreements
        # Refresh PATH
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    } else {
        Write-Info "Download Ollama from: https://ollama.ai/download/windows"
        Read-Host "Install it, then press Enter to continue"
    }
    if (Test-CommandExists ollama) { Write-Ok "Ollama installed" }
    else { Write-Warn "Ollama not in PATH yet — Docker will handle models instead" }
}

# ─── Python ─────────────────────────────────────────────────────────────────
Write-Subsection "🐍 Python"

if (Test-CommandExists python) {
    $pyVer = python --version 2>$null
    Write-Ok "Python installed: $pyVer"
} elseif (Test-CommandExists python3) {
    $pyVer = python3 --version 2>$null
    Write-Ok "Python installed: $pyVer"
} else {
    Write-Info "Installing Python 3.11..."
    if (Test-CommandExists winget) {
        winget install --id Python.Python.3.11 --accept-source-agreements --accept-package-agreements
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    } else {
        Write-Info "Download Python from: https://www.python.org/downloads/"
    }
}

# ─── Git ────────────────────────────────────────────────────────────────────
if (Test-CommandExists git) { Write-Ok "Git available" }
else {
    if (Test-CommandExists winget) { winget install --id Git.Git --accept-source-agreements --accept-package-agreements }
    else { Write-Info "Download Git from: https://git-scm.com/download/win" }
}

# ─── curl ───────────────────────────────────────────────────────────────────
if (Test-CommandExists curl.exe) { Write-Ok "curl available" }
else { Write-Info "curl.exe should come with Windows 10+. If missing, install Git Bash." }

Write-Host ""
Write-Ok "Prerequisite check complete!"

# =============================================================================
# STEP 2: Configure Environment
# =============================================================================

Write-Section "🔑 STEP 2/6 — Configuring Environment"

if (Test-Path $script:EnvFile) {
    Write-Info "Existing .env file found!"
    if (Ask-YesNo "Reconfigure from scratch? (No = keep existing, fill gaps)" "n") {
        $backup = "$($script:EnvFile).backup.$(Get-Date -Format 'yyyyMMddHHmmss')"
        Copy-Item $script:EnvFile $backup
        Write-Info "Backup saved to $backup"
        Set-Content $script:EnvFile -Value ""
    }
} else {
    New-Item -ItemType File -Path $script:EnvFile -Force | Out-Null
}

# Header
$content = Get-Content $script:EnvFile -Raw -ErrorAction SilentlyContinue
if ([string]::IsNullOrWhiteSpace($content)) {
    Set-Content $script:EnvFile -Value @"
# =============================================================================
# SPESION 3.0 — Environment Configuration
# =============================================================================
# Generated by spesion_setup.ps1
# NEVER commit this file to git!
# =============================================================================

"@
}

# ─── LLM Configuration ─────────────────────────────────────────────────────
Write-Subsection "🧠 LLM Providers"

Write-Host "  SPESION uses a hybrid AI model architecture:" -ForegroundColor White
Write-Host "    • Local models (Ollama) — for privacy-sensitive tasks" -ForegroundColor Green
Write-Host "    • Cloud models (OpenAI/Anthropic) — for complex reasoning" -ForegroundColor Green
Write-Host ""
Write-Host "  You NEED at least one cloud provider for full functionality." -ForegroundColor Yellow
Write-Host ""

Write-Env "OLLAMA_BASE_URL" "http://ollama:11434"

$HAS_OPENAI    = $false
$HAS_ANTHROPIC = $false

if (Ask-YesNo "Do you have an OpenAI API key?") {
    $key = Ask -Prompt "Enter your OpenAI API key (sk-...)" -Secret
    Write-Env "OPENAI_API_KEY" $key
    Write-Ok "OpenAI configured"
    $HAS_OPENAI = $true
} else { Write-Warn "Skipping OpenAI" }

if (Ask-YesNo "Do you have an Anthropic API key?") {
    $key = Ask -Prompt "Enter your Anthropic API key (sk-ant-...)" -Secret
    Write-Env "ANTHROPIC_API_KEY" $key
    Write-Ok "Anthropic configured"
    $HAS_ANTHROPIC = $true
} else { Write-Warn "Skipping Anthropic" }

if (-not $HAS_OPENAI -and -not $HAS_ANTHROPIC) {
    Write-Host ""
    Write-Warn "No cloud LLM provider configured!"
    Write-Host "  Get an API key from:" -ForegroundColor Yellow
    Write-Host "    OpenAI:    https://platform.openai.com/api-keys" -ForegroundColor Cyan
    Write-Host "    Anthropic: https://console.anthropic.com/settings/keys" -ForegroundColor Cyan
}

if ($HAS_OPENAI -and $HAS_ANTHROPIC) {
    Write-Host "  Which cloud provider should be primary?"
    Write-Host "    1. OpenAI (GPT-4o) — faster, better tools" -ForegroundColor Green
    Write-Host "    2. Anthropic (Claude) — better reasoning, larger context" -ForegroundColor Green
    $choice = Read-Host "     → [1/2]"
    if ($choice -eq "2") { Write-Env "CLOUD_PROVIDER" "anthropic" }
    else                  { Write-Env "CLOUD_PROVIDER" "openai" }
} elseif ($HAS_OPENAI)    { Write-Env "CLOUD_PROVIDER" "openai" }
  elseif ($HAS_ANTHROPIC) { Write-Env "CLOUD_PROVIDER" "anthropic" }

# ─── Telegram ───────────────────────────────────────────────────────────────
Write-Subsection "📱 Telegram Bot"

Write-Host "  Telegram is SPESION's primary interface."
Write-Host "  To create a bot:" -ForegroundColor White
Write-Host "    1. Open Telegram, search for @BotFather" -ForegroundColor Cyan
Write-Host "    2. Send /newbot" -ForegroundColor Cyan
Write-Host "    3. Choose name: SPESION" -ForegroundColor Cyan
Write-Host "    4. Copy the token" -ForegroundColor Cyan
Write-Host ""
Write-Host "  To get your user ID:" -ForegroundColor White
Write-Host "    Search for @userinfobot → send /start" -ForegroundColor Cyan
Write-Host ""

if (Ask-YesNo "Configure Telegram now?") {
    $token = Ask -Prompt "Telegram Bot Token" -Secret
    Write-Env "TELEGRAM_BOT_TOKEN" $token
    $uid = Ask -Prompt "Your Telegram User ID (numeric)"
    Write-Env "TELEGRAM_ALLOWED_USER_IDS" $uid
    Write-Ok "Telegram configured"
} else { Write-Warn "Telegram skipped — you can use --cli mode" }

# ─── Discord ────────────────────────────────────────────────────────────────
Write-Subsection "🎮 Discord Bot (Optional)"

if (Ask-YesNo "Configure Discord bot?" "n") {
    $token = Ask -Prompt "Discord Bot Token" -Secret
    Write-Env "DISCORD_BOT_TOKEN" $token
    $guild = Ask -Prompt "Discord Server (Guild) ID"
    Write-Env "DISCORD_GUILD_ID" $guild
    Write-Ok "Discord configured"
} else { Write-Info "Discord skipped" }

# ─── Notion ─────────────────────────────────────────────────────────────────
Write-Subsection "📓 Notion (Knowledge Base)"

Write-Host "  Notion is SPESION's external knowledge base."
Write-Host "  Setup: https://www.notion.so/my-integrations" -ForegroundColor Cyan
Write-Host ""

if (Ask-YesNo "Configure Notion now?") {
    $key = Ask -Prompt "Notion API Key (secret_...)" -Secret
    Write-Env "NOTION_API_KEY" $key
    Write-Host ""
    Write-Host "  Database IDs — from each database's URL (or Enter to skip)."
    foreach ($db in @("TASKS","JOURNAL","CRM","BOOKS","TRAININGS","FINANCE","TRANSACTIONS")) {
        $id = Ask -Prompt "  $db Database ID"
        if ($id) { Write-Env "NOTION_${db}_DATABASE_ID" $id }
    }
    Write-Ok "Notion configured"
} else { Write-Info "Notion skipped" }

# ─── Google Calendar ────────────────────────────────────────────────────────
Write-Subsection "📅 Google Calendar"

Write-Host "  Place your OAuth JSON at: data\google_calendar_credentials.json" -ForegroundColor Cyan
$gcalPath = Join-Path $DataDir "google_calendar_credentials.json"
if (Test-Path $gcalPath) {
    Write-Ok "Google Calendar credentials found!"
    Write-Env "GOOGLE_CREDENTIALS_PATH" "/app/data/google_calendar_credentials.json"
} else {
    if (Ask-YesNo "Do you have the Google OAuth JSON file ready?" "n") {
        $src = Ask -Prompt "Full path to google credentials JSON file"
        if (Test-Path $src) {
            Copy-Item $src $gcalPath
            Write-Env "GOOGLE_CREDENTIALS_PATH" "/app/data/google_calendar_credentials.json"
            Write-Ok "Credentials copied"
        } else { Write-Err "File not found: $src" }
    } else { Write-Info "Google Calendar skipped" }
}

# ─── Garmin ─────────────────────────────────────────────────────────────────
Write-Subsection "⌚ Garmin Connect"

if (Ask-YesNo "Configure Garmin Connect?" "n") {
    $email = Ask -Prompt "Garmin email"
    Write-Env "GARMIN_EMAIL" $email
    $pass = Ask -Prompt "Garmin password" -Secret
    Write-Env "GARMIN_PASSWORD" $pass
    Write-Ok "Garmin configured"
} else { Write-Info "Garmin skipped" }

# ─── IBKR ───────────────────────────────────────────────────────────────────
Write-Subsection "💹 Interactive Brokers"

if (Ask-YesNo "Configure IBKR (Flex Web Service)?" "n") {
    $token = Ask -Prompt "IBKR Flex Token (18 digits)"
    Write-Env "IBKR_FLEX_TOKEN" $token
    $qid = Ask -Prompt "IBKR Flex Query ID (7 digits)"
    Write-Env "IBKR_FLEX_QUERY_ID" $qid
    Write-Ok "IBKR configured"
} else { Write-Info "IBKR skipped" }

# ─── Twilio ─────────────────────────────────────────────────────────────────
Write-Subsection "📞 Twilio (Phone Calls & SMS)"

if (Ask-YesNo "Configure Twilio?" "n") {
    $sid   = Ask -Prompt "Twilio Account SID (AC...)"
    Write-Env "TWILIO_ACCOUNT_SID" $sid
    $token = Ask -Prompt "Twilio Auth Token" -Secret
    Write-Env "TWILIO_AUTH_TOKEN" $token
    $phone = Ask -Prompt "Twilio Phone Number (+34...)"
    Write-Env "TWILIO_PHONE_NUMBER" $phone
    Write-Ok "Twilio configured"
} else { Write-Info "Twilio skipped" }

# ─── Email ──────────────────────────────────────────────────────────────────
Write-Subsection "📧 Email (SMTP)"

Write-Host "  For Gmail: Use an App Password, NOT your real password." -ForegroundColor Yellow
Write-Host "    → https://myaccount.google.com/apppasswords" -ForegroundColor Cyan

if (Ask-YesNo "Configure email (SMTP)?" "n") {
    $h = Ask -Prompt "SMTP Host" -Default "smtp.gmail.com"
    Write-Env "SMTP_HOST" $h
    $p = Ask -Prompt "SMTP Port" -Default "587"
    Write-Env "SMTP_PORT" $p
    $u = Ask -Prompt "SMTP Username (email)"
    Write-Env "SMTP_USERNAME" $u
    $pw = Ask -Prompt "SMTP Password (app password)" -Secret
    Write-Env "SMTP_PASSWORD" $pw
    $name = Ask -Prompt "Sender display name" -Default "SPESION"
    Write-Env "SMTP_FROM_NAME" $name
    Write-Ok "Email configured"
} else { Write-Info "Email skipped" }

# ─── Search ─────────────────────────────────────────────────────────────────
Write-Subsection "🔍 Web Search"

if (Ask-YesNo "Configure Tavily search API key?" "n") {
    $key = Ask -Prompt "Tavily API Key (tvly-...)" -Secret
    Write-Env "TAVILY_API_KEY" $key
    Write-Ok "Tavily configured"
} else { Write-Info "Using DuckDuckGo (free)" }

# ─── GitHub ─────────────────────────────────────────────────────────────────
Write-Subsection "🐙 GitHub"

if (Ask-YesNo "Configure GitHub integration?" "n") {
    $token = Ask -Prompt "GitHub Personal Access Token" -Secret
    Write-Env "GITHUB_TOKEN" $token
    Write-Ok "GitHub configured"
} else { Write-Info "GitHub skipped" }

# ─── Bitget ─────────────────────────────────────────────────────────────────
Write-Subsection "₿ Crypto Exchange (Bitget)"

if (Ask-YesNo "Configure Bitget crypto exchange?" "n") {
    $k = Ask -Prompt "Bitget API Key" -Secret
    Write-Env "BITGET_API_KEY" $k
    $s = Ask -Prompt "Bitget API Secret" -Secret
    Write-Env "BITGET_API_SECRET" $s
    $p = Ask -Prompt "Bitget Passphrase" -Secret
    Write-Env "BITGET_PASSPHRASE" $p
    Write-Ok "Bitget configured"
} else { Write-Info "Bitget skipped" }

# ─── System Settings ───────────────────────────────────────────────────────
Write-Subsection "🛡️ System Settings"

$apiKey = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 32 | ForEach-Object { [char]$_ })
Write-Env "SPESION_API_KEY" $apiKey
Write-Ok "Generated secure API key"

Write-Env "SPESION_HOST" "0.0.0.0"
Write-Env "SPESION_PORT" "8100"
Write-Env "DEBUG" "false"
Write-Env "LOG_LEVEL" "INFO"

Write-Env "AUTONOMOUS_ENABLED" "true"
Write-Env "AUTONOMOUS_APPROVAL_TIMEOUT_SECONDS" "300"
Write-Env "AUTONOMOUS_MAX_PLAN_STEPS" "15"
Write-Env "AUTONOMOUS_BACKGROUND_WORKER_ENABLED" "true"

$tz = Ask -Prompt "Your timezone" -Default "Europe/Madrid"
Write-Env "HEARTBEAT_ENABLED" "true"
Write-Env "HEARTBEAT_CHECK_INTERVAL_MINUTES" "30"
Write-Env "HEARTBEAT_ACTIVE_HOURS_START" "07:00"
Write-Env "HEARTBEAT_ACTIVE_HOURS_END" "23:30"
Write-Env "HEARTBEAT_TIMEZONE" $tz

Write-Env "CHROMA_PERSIST_DIR" "/app/data/chroma"
Write-Env "SQLITE_DB_PATH" "/app/data/spesion.db"

Write-Ok "System settings configured!"

# =============================================================================
# STEP 3: User Profile
# =============================================================================

Write-Section "👤 STEP 3/6 — Your Personal Profile"

$profilePath = Join-Path $DataDir "user_profile.md"
if (Test-Path $profilePath) {
    Write-Ok "User profile found!"
    Write-Host ""
    Get-Content $profilePath -TotalCount 20 | ForEach-Object { Write-Host "    $_" -ForegroundColor Blue }
} else {
    if (Ask-YesNo "Create a basic user profile now?") {
        $name = Ask -Prompt "Your full name"
        $age  = Ask -Prompt "Your age"
        $prof = Ask -Prompt "Your profession"
        $loc  = Ask -Prompt "Your location"
        $ints = Ask -Prompt "Your main interests (comma-separated)"

        @"
## Perfil del Usuario: $name

### Datos Basicos
- **Edad**: $age años
- **Profesion**: $prof
- **Ubicacion**: $loc

### Intereses
$ints

### Personalidad
- (SPESION will learn this from your conversations)
"@ | Set-Content $profilePath -Encoding UTF8
        Write-Ok "Profile created"
    }
}

Write-Host ""
Write-Host "  📍 Where ALL your personal data is stored:" -ForegroundColor White
Write-Host "    📁 data\user_profile.md        — Your identity & preferences" -ForegroundColor Cyan
Write-Host "    📁 data\memory_bank.db         — Episodic memories" -ForegroundColor Cyan
Write-Host "    📁 data\skill_store.db         — Learned task patterns" -ForegroundColor Cyan
Write-Host "    📁 data\chroma\                — Vector embeddings" -ForegroundColor Cyan
Write-Host "    📁 workspace\SOUL.md           — SPESION's personality" -ForegroundColor Cyan
Write-Host "    📁 workspace\MEMORY.md         — Curated long-term memories" -ForegroundColor Cyan
Write-Host ""
Write-Host "  🛡️ Everything stays on YOUR machine." -ForegroundColor Green

# =============================================================================
# STEP 4: Pull AI Models
# =============================================================================

Write-Section "🧠 STEP 4/6 — Pulling AI Models"

Write-Host "  Required models:" -ForegroundColor White
Write-Host "    🔹 llama3.2:3b    (~2GB) — Fast routing, companion, sentinel, coach" -ForegroundColor Cyan
Write-Host "    🔹 qwen2.5:7b     (~5GB) — Executive, connector" -ForegroundColor Cyan
Write-Host ""

if (Ask-YesNo "Pre-pull models locally now? (Docker will also pull them)") {
    # Start Ollama if available
    $ollamaRunning = $false
    try { Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 3 | Out-Null; $ollamaRunning = $true } catch {}

    if (-not $ollamaRunning -and (Test-CommandExists ollama)) {
        Write-Info "Starting Ollama..."
        Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden
        Start-Sleep -Seconds 5
    }

    foreach ($model in @("llama3.2:3b", "qwen2.5:7b")) {
        Write-Info "Pulling $model (this may take several minutes)..."
        try { ollama pull $model 2>$null; Write-Ok "$model downloaded" }
        catch { Write-Warn "Failed to pull $model — Docker will try again" }
    }
} else { Write-Info "Models will be pulled automatically by Docker" }

# =============================================================================
# STEP 5: Build & Launch Docker
# =============================================================================

Write-Section "🐳 STEP 5/6 — Building & Launching Docker"

Set-Location $ProjectDir

Write-Host "  Docker Architecture:" -ForegroundColor White
Write-Host ""
Write-Host "    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐"
Write-Host "    │   SPESION    │    │    OLLAMA     │    │    CADDY     │" -ForegroundColor Cyan
Write-Host "    │  (brain +    │◄──►│ (local LLM)  │    │(HTTPS proxy) │" -ForegroundColor Cyan
Write-Host "    │  Telegram)   │    │ llama3.2:3b  │    │ Let's Encrypt│" -ForegroundColor Cyan
Write-Host "    └──────────────┘    └──────────────┘    └──────────────┘"
Write-Host ""

Write-Host "  Deployment mode:" -ForegroundColor White
Write-Host "    1. Production — With Caddy HTTPS proxy (needs domain)" -ForegroundColor Green
Write-Host "    2. Home server — Direct port access (local network)" -ForegroundColor Green
Write-Host "    3. Development — Debug logs, exposed ports" -ForegroundColor Green
$mode = Read-Host "     → Choose [1/2/3]"

switch ($mode) {
    "1" {
        Write-Info "Production mode requires a domain name for HTTPS."
        Write-Host "  Free option: https://www.duckdns.org" -ForegroundColor Cyan
        $domain = Ask -Prompt "Your domain (e.g., spesion.duckdns.org)"
        if ($domain) {
            (Get-Content "$ProjectDir\Caddyfile") -replace 'your-domain\.duckdns\.org', $domain |
                Set-Content "$ProjectDir\Caddyfile"
            Write-Ok "Caddyfile updated with: $domain"
        }
        $ComposeFiles = "-f docker/docker-compose.yml -f docker/docker-compose.prod.yml"
    }
    "3" {
        $ComposeFiles = "-f docker/docker-compose.yml"
        Write-Env "DEBUG" "true"
        Write-Env "LOG_LEVEL" "DEBUG"
    }
    default {
        $ComposeFiles = "-f docker/docker-compose.yml"
        try { $localIP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notmatch "Loopback" } | Select-Object -First 1).IPAddress }
        catch { $localIP = "your-ip" }
        Write-Info "Home server mode — accessible at http://${localIP}:8100"
    }
}

Write-Host ""
Write-Info "Building Docker images (3-5 min first time)..."
Invoke-Expression "docker compose $ComposeFiles build"
Write-Ok "Docker images built!"

Write-Info "Starting services..."
Invoke-Expression "docker compose $ComposeFiles up -d"

# Wait for Ollama
Write-Info "Waiting for Ollama..."
for ($i = 0; $i -lt 30; $i++) {
    try {
        docker exec spesion-ollama curl -sf http://localhost:11434/api/tags 2>$null | Out-Null
        Write-Ok "Ollama ready!"
        break
    } catch { Start-Sleep -Seconds 2; Write-Host "." -NoNewline }
}
Write-Host ""

# Pull models in Docker
Write-Info "Pulling AI models inside Docker..."
docker exec spesion-ollama ollama pull llama3.2:3b 2>$null
docker exec spesion-ollama ollama pull qwen2.5:7b 2>$null
Write-Ok "Models ready!"

# Wait for SPESION
Write-Info "Waiting for SPESION to start..."
for ($i = 0; $i -lt 30; $i++) {
    try {
        Invoke-RestMethod -Uri "http://localhost:8100/health" -TimeoutSec 3 | Out-Null
        Write-Ok "SPESION is alive!"
        break
    } catch { Start-Sleep -Seconds 3; Write-Host "." -NoNewline }
}
Write-Host ""

# =============================================================================
# STEP 6: Verify
# =============================================================================

Write-Section "✅ STEP 6/6 — Verification"

Write-Host "  Docker Containers:" -ForegroundColor White
docker ps --format "table {{.Names}}\t{{.Status}}" --filter "name=spesion"

Write-Host ""
Write-Host "  API Health:" -ForegroundColor White
try {
    $health = Invoke-RestMethod -Uri "http://localhost:8100/health" -TimeoutSec 5
    Write-Ok "API responding at :8100"
    $health | ConvertTo-Json -Depth 3 | ForEach-Object { Write-Host "    $_" }
} catch { Write-Warn "API not responding yet (may still be starting)" }

Write-Host ""
Write-Host "  AI Models:" -ForegroundColor White
docker exec spesion-ollama ollama list 2>$null

# =============================================================================
# Summary
# =============================================================================

Write-Host ""
Write-Host "  ╔═══════════════════════════════════════════════════════════╗" -ForegroundColor Magenta
Write-Host "  ║     🚀  SPESION 3.0 IS LIVE!  🚀                        ║" -ForegroundColor Magenta
Write-Host "  ╚═══════════════════════════════════════════════════════════╝" -ForegroundColor Magenta
Write-Host ""

try { $localIP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notmatch "Loopback" } | Select-Object -First 1).IPAddress }
catch { $localIP = "localhost" }

Write-Host "  Access Points:" -ForegroundColor White
Write-Host "    • API:       http://localhost:8100/health" -ForegroundColor Green
Write-Host "    • Local Net: http://${localIP}:8100" -ForegroundColor Green
if ($domain) { Write-Host "    • Public:    https://$domain" -ForegroundColor Green }
Write-Host ""
Write-Host "  Useful Commands:" -ForegroundColor White
Write-Host "    .\scripts\spesion.ps1 start     — Start all services" -ForegroundColor Cyan
Write-Host "    .\scripts\spesion.ps1 stop      — Stop all" -ForegroundColor Cyan
Write-Host "    .\scripts\spesion.ps1 logs      — Live logs" -ForegroundColor Cyan
Write-Host "    .\scripts\spesion.ps1 status    — System status" -ForegroundColor Cyan
Write-Host "    .\scripts\spesion.ps1 backup    — Backup data" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Next Steps:" -ForegroundColor White
Write-Host "    1. Open Telegram → message your bot → say 'Hello SPESION'" -ForegroundColor Green
Write-Host "    2. Try: 'What can you do?'" -ForegroundColor Green
Write-Host "    3. Try: 'Run full system status'" -ForegroundColor Green
Write-Host ""
Write-Host "  💜 SPESION learns from every interaction. The more you use it," -ForegroundColor Magenta
Write-Host "     the smarter it gets." -ForegroundColor Magenta
Write-Host ""
