#!/usr/bin/env bash
# =============================================================================
# SPESION 3.0 — Fully Guided Interactive Production Setup
# =============================================================================
# One script to rule them all. Detects your OS, installs prerequisites,
# walks you through EVERY API key and config, tests connections, pulls
# models, builds Docker, and launches SPESION in production.
#
# Usage:
#   chmod +x scripts/spesion_setup.sh
#   ./scripts/spesion_setup.sh
#
# Supports: macOS (Apple Silicon + Intel), Ubuntu/Debian, WSL2
# =============================================================================

set -euo pipefail

# ─── Colors & Symbols ───────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
NC='\033[0m' # No Color

CHECK="✅"
CROSS="❌"
WARN="⚠️"
ROCKET="🚀"
BRAIN="🧠"
GEAR="⚙️"
KEY="🔑"
SHIELD="🛡️"
DOCKER_EMOJI="🐳"
HEART="💜"

# ─── Project paths ──────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_DIR/.env"
DATA_DIR="$PROJECT_DIR/data"

# ─── Helper functions ───────────────────────────────────────────────────────

banner() {
    clear
    echo -e "${MAGENTA}${BOLD}"
    echo "  ╔═══════════════════════════════════════════════════════════╗"
    echo "  ║                                                           ║"
    echo "  ║     ${BRAIN}  SPESION 3.0 — Production Setup Wizard  ${BRAIN}        ║"
    echo "  ║                                                           ║"
    echo "  ║     Your Personal AGI Operating System                    ║"
    echo "  ║     Multi-Agent • Self-Learning • Autonomous              ║"
    echo "  ║                                                           ║"
    echo "  ╚═══════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo ""
}

section() {
    echo ""
    echo -e "${CYAN}${BOLD}══════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}${BOLD}  $1${NC}"
    echo -e "${CYAN}${BOLD}══════════════════════════════════════════════════════════════${NC}"
    echo ""
}

subsection() {
    echo ""
    echo -e "${BLUE}${BOLD}  ── $1 ──${NC}"
    echo ""
}

success() {
    echo -e "  ${GREEN}${CHECK} $1${NC}"
}

warn() {
    echo -e "  ${YELLOW}${WARN}  $1${NC}"
}

error() {
    echo -e "  ${RED}${CROSS} $1${NC}"
}

info() {
    echo -e "  ${BLUE}ℹ️  $1${NC}"
}

ask() {
    local prompt="$1"
    local var_name="$2"
    local default="${3:-}"
    local secret="${4:-false}"
    
    if [ -n "$default" ]; then
        prompt="$prompt ${YELLOW}[default: $default]${NC}"
    fi
    
    echo -e "  ${GEAR} ${prompt}"
    if [ "$secret" = "true" ]; then
        read -s -p "     → " value
        echo "" # newline after hidden input
    else
        read -p "     → " value
    fi
    
    if [ -z "$value" ] && [ -n "$default" ]; then
        value="$default"
    fi
    
    eval "$var_name='$value'"
}

ask_yes_no() {
    local prompt="$1"
    local default="${2:-y}"
    
    if [ "$default" = "y" ]; then
        prompt="$prompt ${YELLOW}[Y/n]${NC}"
    else
        prompt="$prompt ${YELLOW}[y/N]${NC}"
    fi
    
    echo -e "  ${GEAR} ${prompt}"
    read -p "     → " answer
    
    if [ -z "$answer" ]; then
        answer="$default"
    fi
    
    case "$answer" in
        [yY]|[yY][eE][sS]) return 0 ;;
        *) return 1 ;;
    esac
}

write_env() {
    local key="$1"
    local value="$2"
    
    # If key exists, update it; otherwise append
    if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
        else
            sed -i "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
        fi
    else
        echo "${key}=${value}" >> "$ENV_FILE"
    fi
}

check_command() {
    command -v "$1" &> /dev/null
}

detect_os() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
        if [[ $(uname -m) == "arm64" ]]; then
            ARCH="apple_silicon"
        else
            ARCH="intel"
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if grep -q Microsoft /proc/version 2>/dev/null; then
            OS="wsl"
        else
            OS="linux"
        fi
        ARCH=$(uname -m)
    else
        OS="unknown"
        ARCH="unknown"
    fi
}

# ─── STEP 0: Welcome & OS Detection ─────────────────────────────────────────

banner
detect_os

echo -e "  ${BRAIN} ${BOLD}Welcome to SPESION 3.0 Production Setup!${NC}"
echo ""
echo -e "  This wizard will guide you through EVERYTHING:"
echo -e "    ${GREEN}1.${NC} Install prerequisites (Docker, Ollama, Python)"
echo -e "    ${GREEN}2.${NC} Configure ALL API keys and services"
echo -e "    ${GREEN}3.${NC} Set up your personal profile"
echo -e "    ${GREEN}4.${NC} Pull AI models"
echo -e "    ${GREEN}5.${NC} Build & launch Docker containers"
echo -e "    ${GREEN}6.${NC} Verify everything works"
echo ""
echo -e "  ${BLUE}Detected: ${BOLD}$OS ($ARCH)${NC}"
echo -e "  ${BLUE}Project:  ${BOLD}$PROJECT_DIR${NC}"
echo ""

if ! ask_yes_no "Ready to begin?"; then
    echo -e "\n  ${HEART} No worries! Run this script again when you're ready.\n"
    exit 0
fi

# =============================================================================
# STEP 1: Prerequisites
# =============================================================================

section "${GEAR} STEP 1/6 — Installing Prerequisites"

# ─── Homebrew (macOS only) ──────────────────────────────────────────────────
if [ "$OS" = "macos" ]; then
    if ! check_command brew; then
        info "Installing Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        
        # Add to path for Apple Silicon
        if [ "$ARCH" = "apple_silicon" ]; then
            eval "$(/opt/homebrew/bin/brew shellenv)"
        fi
        success "Homebrew installed"
    else
        success "Homebrew already installed"
    fi
fi

# ─── Docker ─────────────────────────────────────────────────────────────────
subsection "${DOCKER_EMOJI} Docker"

if check_command docker; then
    DOCKER_VERSION=$(docker --version 2>/dev/null || echo "unknown")
    success "Docker installed: $DOCKER_VERSION"
    
    # Check if Docker daemon is running
    if docker info &>/dev/null; then
        success "Docker daemon is running"
    else
        warn "Docker daemon is NOT running"
        if [ "$OS" = "macos" ]; then
            info "Starting Docker Desktop..."
            open -a Docker
            echo -e "  ${YELLOW}Waiting for Docker to start (this can take 30-60 seconds)...${NC}"
            for i in {1..60}; do
                if docker info &>/dev/null; then
                    success "Docker daemon started!"
                    break
                fi
                sleep 2
                echo -n "."
            done
            echo ""
            if ! docker info &>/dev/null; then
                error "Docker didn't start. Please open Docker Desktop manually and re-run this script."
                exit 1
            fi
        fi
    fi
else
    if [ "$OS" = "macos" ]; then
        info "Installing Docker Desktop via Homebrew..."
        brew install --cask docker
        info "Opening Docker Desktop (first launch takes a minute)..."
        open -a Docker
        echo -e "  ${YELLOW}Waiting for Docker to initialize...${NC}"
        for i in {1..90}; do
            if docker info &>/dev/null; then
                success "Docker installed and running!"
                break
            fi
            sleep 2
            echo -n "."
        done
        echo ""
    elif [ "$OS" = "linux" ] || [ "$OS" = "wsl" ]; then
        info "Installing Docker..."
        curl -fsSL https://get.docker.com | sh
        sudo systemctl enable --now docker
        sudo usermod -aG docker "$USER"
        success "Docker installed (you may need to log out/in for group changes)"
    fi
fi

# Check docker compose
if docker compose version &>/dev/null; then
    success "Docker Compose available: $(docker compose version --short 2>/dev/null)"
else
    error "Docker Compose not found. Please install Docker Desktop."
    exit 1
fi

# ─── Ollama ─────────────────────────────────────────────────────────────────
subsection "${BRAIN} Ollama (Local AI Models)"

if check_command ollama; then
    success "Ollama already installed"
else
    if [ "$OS" = "macos" ]; then
        info "Installing Ollama..."
        brew install ollama
    elif [ "$OS" = "linux" ] || [ "$OS" = "wsl" ]; then
        info "Installing Ollama..."
        curl -fsSL https://ollama.ai/install.sh | sh
    fi
    success "Ollama installed"
fi

# ─── Python (for local dev/testing) ────────────────────────────────────────
subsection "🐍 Python"

if check_command python3; then
    PY_VERSION=$(python3 --version)
    success "Python installed: $PY_VERSION"
else
    if [ "$OS" = "macos" ]; then
        brew install python@3.11
    fi
fi

# ─── curl, git, jq ─────────────────────────────────────────────────────────
for cmd in curl git jq; do
    if check_command "$cmd"; then
        success "$cmd available"
    else
        if [ "$OS" = "macos" ]; then
            brew install "$cmd"
        elif [ "$OS" = "linux" ] || [ "$OS" = "wsl" ]; then
            sudo apt-get install -y "$cmd"
        fi
        success "$cmd installed"
    fi
done

echo ""
success "All prerequisites installed!"

# =============================================================================
# STEP 2: Configure Environment
# =============================================================================

section "${KEY} STEP 2/6 — Configuring Environment"

# Create .env if it doesn't exist
if [ -f "$ENV_FILE" ]; then
    info "Existing .env file found!"
    if ask_yes_no "Do you want to reconfigure from scratch? (No = keep existing and fill gaps)" "n"; then
        cp "$ENV_FILE" "${ENV_FILE}.backup.$(date +%s)"
        info "Backup saved to ${ENV_FILE}.backup.*"
        cat /dev/null > "$ENV_FILE"
    fi
else
    touch "$ENV_FILE"
fi

# ─── Header ─────────────────────────────────────────────────────────────────
if [ ! -s "$ENV_FILE" ]; then
    cat > "$ENV_FILE" << 'ENVHEADER'
# =============================================================================
# SPESION 3.0 — Environment Configuration
# =============================================================================
# Generated by spesion_setup.sh
# NEVER commit this file to git!
# =============================================================================

ENVHEADER
fi

# ─── LLM Configuration ─────────────────────────────────────────────────────
subsection "${BRAIN} LLM Providers"

echo -e "  SPESION uses a hybrid AI model architecture:"
echo -e "    ${GREEN}•${NC} ${BOLD}Local models${NC} (Ollama) — for privacy-sensitive tasks (health, emotions)"
echo -e "    ${GREEN}•${NC} ${BOLD}Cloud models${NC} (OpenAI/Anthropic) — for complex reasoning & research"
echo ""
echo -e "  ${YELLOW}You NEED at least one cloud provider for full functionality.${NC}"
echo -e "  ${YELLOW}Local Ollama models are pulled automatically by Docker.${NC}"
echo ""

# Ollama (always configured)
write_env "OLLAMA_BASE_URL" "http://ollama:11434"

# OpenAI
if ask_yes_no "Do you have an OpenAI API key?"; then
    ask "Enter your OpenAI API key (sk-...)" OPENAI_KEY "" "true"
    write_env "OPENAI_API_KEY" "$OPENAI_KEY"
    success "OpenAI configured"
    HAS_OPENAI=true
else
    warn "Skipping OpenAI (you'll need at least one cloud provider)"
    HAS_OPENAI=false
fi

# Anthropic
if ask_yes_no "Do you have an Anthropic API key?"; then
    ask "Enter your Anthropic API key (sk-ant-...)" ANTHROPIC_KEY "" "true"
    write_env "ANTHROPIC_API_KEY" "$ANTHROPIC_KEY"
    success "Anthropic configured"
    HAS_ANTHROPIC=true
else
    HAS_ANTHROPIC=false
fi

if [ "$HAS_OPENAI" = false ] && [ "$HAS_ANTHROPIC" = false ]; then
    echo ""
    warn "No cloud LLM provider configured!"
    echo -e "  ${YELLOW}SPESION will work with local models only, but agents like${NC}"
    echo -e "  ${YELLOW}Scholar, Tycoon, and TechLead need cloud models for complex tasks.${NC}"
    echo ""
    echo -e "  Get an API key from:"
    echo -e "    OpenAI:    https://platform.openai.com/api-keys"
    echo -e "    Anthropic: https://console.anthropic.com/settings/keys"
    echo ""
fi

# Cloud provider preference
if [ "$HAS_OPENAI" = true ] && [ "$HAS_ANTHROPIC" = true ]; then
    echo -e "  Which cloud provider should be the primary?"
    echo -e "    ${GREEN}1.${NC} OpenAI (GPT-4o) — faster, better tools"
    echo -e "    ${GREEN}2.${NC} Anthropic (Claude) — better reasoning, larger context"
    read -p "     → [1/2]: " cloud_choice
    if [ "$cloud_choice" = "2" ]; then
        write_env "CLOUD_PROVIDER" "anthropic"
    else
        write_env "CLOUD_PROVIDER" "openai"
    fi
elif [ "$HAS_OPENAI" = true ]; then
    write_env "CLOUD_PROVIDER" "openai"
elif [ "$HAS_ANTHROPIC" = true ]; then
    write_env "CLOUD_PROVIDER" "anthropic"
fi

# ─── Telegram ───────────────────────────────────────────────────────────────
subsection "📱 Telegram Bot"

echo -e "  Telegram is SPESION's primary interface."
echo -e "  ${BOLD}To create a bot:${NC}"
echo -e "    1. Open Telegram, search for ${CYAN}@BotFather${NC}"
echo -e "    2. Send ${CYAN}/newbot${NC}"
echo -e "    3. Choose name: ${CYAN}SPESION${NC}"
echo -e "    4. Choose username: ${CYAN}spesion_yourname_bot${NC}"
echo -e "    5. Copy the token"
echo ""
echo -e "  ${BOLD}To get your user ID:${NC}"
echo -e "    Search for ${CYAN}@userinfobot${NC} in Telegram → send ${CYAN}/start${NC}"
echo ""

if ask_yes_no "Configure Telegram now?"; then
    ask "Telegram Bot Token" TG_TOKEN "" "true"
    write_env "TELEGRAM_BOT_TOKEN" "$TG_TOKEN"
    
    ask "Your Telegram User ID (numeric)" TG_USER_ID ""
    write_env "TELEGRAM_ALLOWED_USER_IDS" "$TG_USER_ID"
    success "Telegram configured"
else
    warn "Telegram skipped — you can use --cli mode"
fi

# ─── Discord ────────────────────────────────────────────────────────────────
subsection "🎮 Discord Bot (Optional)"

if ask_yes_no "Configure Discord bot?" "n"; then
    echo -e "  ${BOLD}Steps:${NC}"
    echo -e "    1. Go to ${CYAN}https://discord.com/developers/applications${NC}"
    echo -e "    2. New Application → name it SPESION"
    echo -e "    3. Bot tab → Add Bot → copy token"
    echo -e "    4. Enable: Server Members Intent + Message Content Intent"
    echo ""
    
    ask "Discord Bot Token" DC_TOKEN "" "true"
    write_env "DISCORD_BOT_TOKEN" "$DC_TOKEN"
    
    ask "Discord Server (Guild) ID" DC_GUILD ""
    write_env "DISCORD_GUILD_ID" "$DC_GUILD"
    success "Discord configured"
else
    info "Discord skipped"
fi

# ─── Notion ─────────────────────────────────────────────────────────────────
subsection "📓 Notion (Knowledge Base)"

echo -e "  Notion is SPESION's external knowledge base: tasks, journal, CRM, books."
echo -e "  ${BOLD}To set up:${NC}"
echo -e "    1. Go to ${CYAN}https://www.notion.so/my-integrations${NC}"
echo -e "    2. Create new integration → copy the API key"
echo -e "    3. Share your databases with the integration"
echo ""

if ask_yes_no "Configure Notion now?"; then
    ask "Notion API Key (secret_...)" NOTION_KEY "" "true"
    write_env "NOTION_API_KEY" "$NOTION_KEY"
    
    echo ""
    echo -e "  ${BOLD}Database IDs${NC} — find them in each database's URL:"
    echo -e "  URL format: ${CYAN}https://notion.so/workspace/${BOLD}DATABASE_ID${NC}${CYAN}?v=...${NC}"
    echo -e "  You can skip any database you don't use (press Enter to skip)."
    echo ""
    
    for db in TASKS JOURNAL CRM BOOKS TRAININGS FINANCE TRANSACTIONS; do
        ask "  ${db} Database ID (or Enter to skip)" "DB_ID" ""
        if [ -n "$DB_ID" ]; then
            write_env "NOTION_${db}_DATABASE_ID" "$DB_ID"
        fi
    done
    
    success "Notion configured"
    
    if ask_yes_no "Auto-create Notion databases? (runs --setup-notion)" "n"; then
        SETUP_NOTION=true
    fi
else
    info "Notion skipped"
    SETUP_NOTION=false
fi

# ─── Google Calendar ────────────────────────────────────────────────────────
subsection "📅 Google Calendar"

echo -e "  SPESION can manage your Google Calendar (view/create/edit/delete events)."
echo -e "  ${BOLD}To set up:${NC}"
echo -e "    1. Go to ${CYAN}https://console.cloud.google.com${NC}"
echo -e "    2. Create project → Enable Calendar API"
echo -e "    3. Create OAuth 2.0 credentials → Download JSON"
echo -e "    4. Place the file at: ${CYAN}data/google_calendar_credentials.json${NC}"
echo ""

if [ -f "$DATA_DIR/google_calendar_credentials.json" ]; then
    success "Google Calendar credentials found!"
    write_env "GOOGLE_CREDENTIALS_PATH" "/app/data/google_calendar_credentials.json"
else
    if ask_yes_no "Do you have the Google OAuth JSON file ready?" "n"; then
        ask "Full path to google credentials JSON file" GCAL_PATH ""
        if [ -f "$GCAL_PATH" ]; then
            cp "$GCAL_PATH" "$DATA_DIR/google_calendar_credentials.json"
            write_env "GOOGLE_CREDENTIALS_PATH" "/app/data/google_calendar_credentials.json"
            success "Google Calendar credentials copied"
        else
            error "File not found: $GCAL_PATH"
        fi
    else
        info "Google Calendar skipped — you can add it later"
    fi
fi

# ─── Garmin ─────────────────────────────────────────────────────────────────
subsection "⌚ Garmin Connect (Health & Fitness)"

if ask_yes_no "Configure Garmin Connect?" "n"; then
    ask "Garmin email" GARMIN_EMAIL ""
    write_env "GARMIN_EMAIL" "$GARMIN_EMAIL"
    
    ask "Garmin password" GARMIN_PASS "" "true"
    write_env "GARMIN_PASSWORD" "$GARMIN_PASS"
    success "Garmin configured"
else
    info "Garmin skipped"
fi

# ─── IBKR ───────────────────────────────────────────────────────────────────
subsection "💹 Interactive Brokers (Investments)"

if ask_yes_no "Configure IBKR (Flex Web Service)?" "n"; then
    echo -e "  ${BOLD}To set up Flex Queries:${NC}"
    echo -e "    1. Log in to IBKR Account Management"
    echo -e "    2. Settings → Reporting → Flex Queries"
    echo -e "    3. Create Activity Flex Query → get Token & Query ID"
    echo ""
    
    ask "IBKR Flex Token (18 digits)" IBKR_TOKEN ""
    write_env "IBKR_FLEX_TOKEN" "$IBKR_TOKEN"
    
    ask "IBKR Flex Query ID (7 digits)" IBKR_QUERY ""
    write_env "IBKR_FLEX_QUERY_ID" "$IBKR_QUERY"
    success "IBKR configured"
else
    info "IBKR skipped"
fi

# ─── Twilio (Phone/SMS) ────────────────────────────────────────────────────
subsection "📞 Twilio (Autonomous Phone Calls & SMS)"

echo -e "  Twilio lets SPESION make phone calls and send SMS autonomously."
echo -e "  ${BOLD}Always requires your approval before dangerous actions.${NC}"
echo ""

if ask_yes_no "Configure Twilio?" "n"; then
    ask "Twilio Account SID (AC...)" TWIL_SID ""
    write_env "TWILIO_ACCOUNT_SID" "$TWIL_SID"
    
    ask "Twilio Auth Token" TWIL_TOKEN "" "true"
    write_env "TWILIO_AUTH_TOKEN" "$TWIL_TOKEN"
    
    ask "Twilio Phone Number (+34...)" TWIL_PHONE ""
    write_env "TWILIO_PHONE_NUMBER" "$TWIL_PHONE"
    success "Twilio configured"
else
    info "Twilio skipped"
fi

# ─── Email (SMTP) ──────────────────────────────────────────────────────────
subsection "📧 Email (SMTP)"

echo -e "  SPESION can send emails autonomously (with your approval)."
echo -e "  ${BOLD}For Gmail:${NC} Use an App Password, NOT your real password."
echo -e "    → ${CYAN}https://myaccount.google.com/apppasswords${NC}"
echo ""

if ask_yes_no "Configure email (SMTP)?" "n"; then
    ask "SMTP Host" SMTP_H "smtp.gmail.com"
    write_env "SMTP_HOST" "$SMTP_H"
    
    ask "SMTP Port" SMTP_P "587"
    write_env "SMTP_PORT" "$SMTP_P"
    
    ask "SMTP Username (email)" SMTP_U ""
    write_env "SMTP_USERNAME" "$SMTP_U"
    
    ask "SMTP Password (app password)" SMTP_PW "" "true"
    write_env "SMTP_PASSWORD" "$SMTP_PW"
    
    ask "Sender display name" SMTP_NAME "SPESION"
    write_env "SMTP_FROM_NAME" "$SMTP_NAME"
    success "Email configured"
else
    info "Email skipped"
fi

# ─── Search ─────────────────────────────────────────────────────────────────
subsection "🔍 Web Search"

echo -e "  SPESION can search the web. Tavily is better but optional."
echo -e "  Without Tavily, SPESION uses DuckDuckGo (free, no API key)."
echo ""

if ask_yes_no "Configure Tavily API key?" "n"; then
    ask "Tavily API Key (tvly-...)" TAVILY_KEY "" "true"
    write_env "TAVILY_API_KEY" "$TAVILY_KEY"
    success "Tavily configured"
else
    info "Using DuckDuckGo (free, no setup needed)"
fi

# ─── GitHub ─────────────────────────────────────────────────────────────────
subsection "🐙 GitHub"

if ask_yes_no "Configure GitHub integration?" "n"; then
    ask "GitHub Personal Access Token" GH_TOKEN "" "true"
    write_env "GITHUB_TOKEN" "$GH_TOKEN"
    success "GitHub configured"
else
    info "GitHub skipped"
fi

# ─── Crypto (Bitget) ───────────────────────────────────────────────────────
subsection "₿ Crypto Exchange (Bitget)"

if ask_yes_no "Configure Bitget crypto exchange?" "n"; then
    ask "Bitget API Key" BG_KEY "" "true"
    write_env "BITGET_API_KEY" "$BG_KEY"
    
    ask "Bitget API Secret" BG_SECRET "" "true"
    write_env "BITGET_API_SECRET" "$BG_SECRET"
    
    ask "Bitget Passphrase" BG_PASS "" "true"
    write_env "BITGET_PASSPHRASE" "$BG_PASS"
    success "Bitget configured"
else
    info "Bitget skipped"
fi

# ─── System Settings ───────────────────────────────────────────────────────
subsection "${SHIELD} System Settings"

# Generate API key
API_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))" 2>/dev/null || openssl rand -base64 32)
write_env "SPESION_API_KEY" "$API_KEY"
success "Generated secure API key"

write_env "SPESION_HOST" "0.0.0.0"
write_env "SPESION_PORT" "8100"
write_env "DEBUG" "false"
write_env "LOG_LEVEL" "INFO"

# Autonomous settings
write_env "AUTONOMOUS_ENABLED" "true"
write_env "AUTONOMOUS_APPROVAL_TIMEOUT_SECONDS" "300"
write_env "AUTONOMOUS_MAX_PLAN_STEPS" "15"
write_env "AUTONOMOUS_BACKGROUND_WORKER_ENABLED" "true"

# Heartbeat
ask "Your timezone" TZ "Europe/Madrid"
write_env "HEARTBEAT_ENABLED" "true"
write_env "HEARTBEAT_CHECK_INTERVAL_MINUTES" "30"
write_env "HEARTBEAT_ACTIVE_HOURS_START" "07:00"
write_env "HEARTBEAT_ACTIVE_HOURS_END" "23:30"
write_env "HEARTBEAT_TIMEZONE" "$TZ"

# Storage (Docker paths)
write_env "CHROMA_PERSIST_DIR" "/app/data/chroma"
write_env "SQLITE_DB_PATH" "/app/data/spesion.db"

echo ""
success "System settings configured!"

# =============================================================================
# STEP 3: Personal Data / User Profile
# =============================================================================

section "👤 STEP 3/6 — Your Personal Profile"

echo -e "  SPESION learns about you to be a better assistant."
echo -e "  Your profile is stored locally at: ${CYAN}data/user_profile.md${NC}"
echo -e "  Memory banks are at: ${CYAN}data/memory_bank.db${NC} and ${CYAN}data/chroma/${NC}"
echo ""

if [ -f "$DATA_DIR/user_profile.md" ]; then
    success "User profile found!"
    echo ""
    echo -e "  ${BLUE}Preview of your profile:${NC}"
    head -20 "$DATA_DIR/user_profile.md" | sed 's/^/    /'
    echo ""
else
    if ask_yes_no "Create a basic user profile now?" "y"; then
        ask "Your full name" USER_NAME ""
        ask "Your age" USER_AGE ""
        ask "Your profession" USER_PROF ""
        ask "Your location" USER_LOC ""
        ask "Your main interests (comma-separated)" USER_INT ""
        
        cat > "$DATA_DIR/user_profile.md" << PROFILE
## Perfil del Usuario: $USER_NAME

### Datos Básicos
- **Edad**: $USER_AGE años
- **Profesión**: $USER_PROF
- **Ubicación**: $USER_LOC

### Intereses
$USER_INT

### Personalidad
- (SPESION will learn this from your conversations)

### Contexto Emocional
- (SPESION will adapt to your communication style)
PROFILE
        success "Profile created at data/user_profile.md"
    fi
fi

echo ""
echo -e "  ${BOLD}📍 Where is ALL your personal data stored:${NC}"
echo ""
echo -e "    📁 ${CYAN}data/user_profile.md${NC}        — Your identity & preferences"
echo -e "    📁 ${CYAN}data/memory_bank.db${NC}         — Episodic memories (every conversation)"
echo -e "    📁 ${CYAN}data/skill_store.db${NC}         — Learned task patterns"
echo -e "    📁 ${CYAN}data/chroma/${NC}                — Vector embeddings (semantic search)"
echo -e "    📁 ${CYAN}data/spesion.db${NC}             — Session state & task queue"
echo -e "    📁 ${CYAN}data/spesion.log${NC}            — Application logs"
echo -e "    📁 ${CYAN}data/google_token.json${NC}      — Google OAuth token"
echo -e "    📁 ${CYAN}workspace/MEMORY.md${NC}         — Curated long-term memories"
echo -e "    📁 ${CYAN}workspace/SOUL.md${NC}           — SPESION's personality (editable)"
echo -e "    📁 ${CYAN}workspace/memory/*.md${NC}       — Daily conversation logs"
echo ""
echo -e "  ${SHIELD} ${BOLD}Everything stays on YOUR machine. Nothing is sent to cloud"
echo -e "     unless you explicitly use a cloud LLM model.${NC}"
echo ""

# =============================================================================
# STEP 4: Pull AI Models
# =============================================================================

section "${BRAIN} STEP 4/6 — Pulling AI Models"

echo -e "  SPESION needs local AI models for privacy-sensitive tasks."
echo -e "  These models run on YOUR hardware via Ollama."
echo ""
echo -e "  ${BOLD}Required models:${NC}"
echo -e "    🔹 ${CYAN}llama3.2:3b${NC}    (~2GB) — Fast routing, companion, sentinel, coach"
echo -e "    🔹 ${CYAN}qwen2.5:7b${NC}     (~5GB) — Executive, connector (medium complexity)"
echo ""

# We'll pull models via Docker during compose build, but also offer local pull
if ask_yes_no "Pre-pull models locally now? (Docker will also pull them)" "y"; then
    
    # Start Ollama if not running
    if ! curl -sf http://localhost:11434/api/tags &>/dev/null; then
        info "Starting Ollama service..."
        if [ "$OS" = "macos" ]; then
            ollama serve &>/dev/null &
            OLLAMA_PID=$!
            sleep 3
        else
            sudo systemctl start ollama 2>/dev/null || ollama serve &>/dev/null &
            OLLAMA_PID=$!
            sleep 3
        fi
    fi
    
    for model in llama3.2:3b qwen2.5:7b; do
        info "Pulling $model (this may take several minutes)..."
        if ollama pull "$model" 2>&1; then
            success "$model downloaded"
        else
            warn "Failed to pull $model — Docker will try again"
        fi
    done
    
    # Kill our Ollama if we started it (Docker runs its own)
    if [ -n "${OLLAMA_PID:-}" ]; then
        kill "$OLLAMA_PID" 2>/dev/null || true
    fi
else
    info "Models will be pulled automatically by Docker"
fi

# =============================================================================
# STEP 5: Build & Launch Docker
# =============================================================================

section "${DOCKER_EMOJI} STEP 5/6 — Building & Launching Docker"

cd "$PROJECT_DIR"

echo -e "  ${BOLD}Docker Architecture:${NC}"
echo ""
echo -e "    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐"
echo -e "    │   ${CYAN}SPESION${NC}    │    │   ${CYAN}OLLAMA${NC}    │    │    ${CYAN}CADDY${NC}    │"
echo -e "    │  (brain +    │◄──►│ (local LLM)  │    │(HTTPS proxy) │"
echo -e "    │  Telegram +  │    │ llama3.2:3b  │    │ Let's Encrypt│"
echo -e "    │  heartbeat)  │    │ qwen2.5:7b   │    │              │"
echo -e "    └──────┬───────┘    └──────────────┘    └──────┬───────┘"
echo -e "           │                                        │"
echo -e "    ┌──────▼────────────────────────────────────────▼──────┐"
echo -e "    │              ${BLUE}Docker Internal Network${NC}                   │"
echo -e "    └─────────────────────────────────────────────────────┘"
echo ""

# Choose deployment mode
echo -e "  ${BOLD}Deployment mode:${NC}"
echo -e "    ${GREEN}1.${NC} ${BOLD}Production${NC} — With Caddy HTTPS proxy (needs domain name)"
echo -e "    ${GREEN}2.${NC} ${BOLD}Home server${NC} — Without Caddy, direct port access (local network)"
echo -e "    ${GREEN}3.${NC} ${BOLD}Development${NC} — With debug logs, exposed ports"
echo ""
read -p "     → Choose [1/2/3]: " DEPLOY_MODE

COMPOSE_CMD="docker compose"

case "$DEPLOY_MODE" in
    1)
        # Production with Caddy
        echo ""
        info "Production mode requires a domain name for HTTPS."
        echo -e "  ${BOLD}Free option:${NC} ${CYAN}https://www.duckdns.org${NC} (2 minutes to set up)"
        echo ""
        ask "Your domain name (e.g., spesion.duckdns.org)" DOMAIN ""
        
        if [ -n "$DOMAIN" ]; then
            # Update Caddyfile
            if [[ "$OSTYPE" == "darwin"* ]]; then
                sed -i '' "s|your-domain.duckdns.org|${DOMAIN}|g" "$PROJECT_DIR/Caddyfile"
            else
                sed -i "s|your-domain.duckdns.org|${DOMAIN}|g" "$PROJECT_DIR/Caddyfile"
            fi
            success "Caddyfile updated with domain: $DOMAIN"
        fi
        
        COMPOSE_FILES="-f docker/docker-compose.yml -f docker/docker-compose.prod.yml"
        ;;
    2)
        # Home server (no Caddy)
        COMPOSE_FILES="-f docker/docker-compose.yml"
        info "Home server mode — accessible at http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo 'your-ip'):8100"
        ;;
    3)
        # Development
        COMPOSE_FILES="-f docker/docker-compose.yml"
        write_env "DEBUG" "true"
        write_env "LOG_LEVEL" "DEBUG"
        ;;
    *)
        COMPOSE_FILES="-f docker/docker-compose.yml"
        ;;
esac

echo ""
info "Building Docker images (this takes 3-5 minutes on first run)..."
echo ""

$COMPOSE_CMD $COMPOSE_FILES build 2>&1 | tail -20

echo ""
success "Docker images built!"
echo ""

info "Starting services..."
$COMPOSE_CMD $COMPOSE_FILES up -d 2>&1

echo ""

# Wait for Ollama to be healthy
info "Waiting for Ollama to initialize..."
for i in {1..30}; do
    if docker exec spesion-ollama curl -sf http://localhost:11434/api/tags &>/dev/null; then
        success "Ollama is ready!"
        break
    fi
    sleep 2
    echo -n "."
done
echo ""

# Pull models inside Docker's Ollama
info "Pulling AI models inside Docker (if not cached)..."
docker exec spesion-ollama ollama pull llama3.2:3b 2>&1 | tail -5
docker exec spesion-ollama ollama pull qwen2.5:7b 2>&1 | tail -5
success "Models ready!"

# Wait for SPESION health
info "Waiting for SPESION to start..."
for i in {1..30}; do
    if curl -sf http://localhost:8100/health &>/dev/null; then
        success "SPESION is alive!"
        break
    fi
    sleep 3
    echo -n "."
done
echo ""

# =============================================================================
# STEP 6: Verify Everything
# =============================================================================

section "${CHECK} STEP 6/6 — Verification"

echo -e "  Running system checks...\n"

# Docker containers
CONTAINERS=$(docker ps --format "{{.Names}} {{.Status}}" --filter "name=spesion" 2>/dev/null)
echo -e "  ${BOLD}Docker Containers:${NC}"
while IFS= read -r line; do
    name=$(echo "$line" | awk '{print $1}')
    status=$(echo "$line" | cut -d' ' -f2-)
    if echo "$status" | grep -q "Up"; then
        success "$name: $status"
    else
        error "$name: $status"
    fi
done <<< "$CONTAINERS"

echo ""

# Health endpoint
echo -e "  ${BOLD}API Health:${NC}"
if HEALTH=$(curl -sf http://localhost:8100/health 2>/dev/null); then
    success "API responding at :8100"
    echo "$HEALTH" | python3 -m json.tool 2>/dev/null | sed 's/^/    /' || echo "    $HEALTH"
else
    warn "API not responding yet (may still be starting — check logs below)"
fi

echo ""

# Ollama models
echo -e "  ${BOLD}AI Models:${NC}"
if MODELS=$(docker exec spesion-ollama ollama list 2>/dev/null); then
    echo "$MODELS" | head -10 | sed 's/^/    /'
else
    warn "Could not list Ollama models"
fi

echo ""

# Data directories
echo -e "  ${BOLD}Data Persistence:${NC}"
for dir in data data/chroma workspace workspace/memory; do
    if [ -d "$PROJECT_DIR/$dir" ]; then
        success "$dir/ exists"
    else
        mkdir -p "$PROJECT_DIR/$dir"
        success "$dir/ created"
    fi
done

# =============================================================================
# Summary
# =============================================================================

echo ""
echo -e "${MAGENTA}${BOLD}"
echo "  ╔═══════════════════════════════════════════════════════════╗"
echo "  ║                                                           ║"
echo "  ║     ${ROCKET}  SPESION 3.0 IS LIVE!  ${ROCKET}                        ║"
echo "  ║                                                           ║"
echo "  ╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || ipconfig getifaddr en0 2>/dev/null || echo "localhost")

echo -e "  ${BOLD}Access Points:${NC}"
echo -e "    ${GREEN}•${NC} API:       http://localhost:8100/health"
echo -e "    ${GREEN}•${NC} Local Net: http://${LOCAL_IP}:8100"
if [ -n "${DOMAIN:-}" ]; then
    echo -e "    ${GREEN}•${NC} Public:    https://${DOMAIN}"
fi
echo ""
echo -e "  ${BOLD}Useful Commands:${NC}"
echo -e "    ${CYAN}docker logs -f spesion${NC}                    — View live logs"
echo -e "    ${CYAN}docker compose $COMPOSE_FILES ps${NC}     — Container status"
echo -e "    ${CYAN}docker compose $COMPOSE_FILES restart${NC} — Restart all"
echo -e "    ${CYAN}docker compose $COMPOSE_FILES down${NC}    — Stop all"
echo -e "    ${CYAN}docker exec -it spesion python main.py --status${NC} — System status"
echo -e "    ${CYAN}docker exec -it spesion python main.py --reflect${NC} — Force reflection"
echo ""
echo -e "  ${BOLD}Your Data Lives At:${NC}"
echo -e "    Docker volume: ${CYAN}spesion-data${NC} → /app/data (persists across restarts)"
echo -e "    Local backup:  ${CYAN}$PROJECT_DIR/data/${NC}"
echo ""
echo -e "  ${BOLD}Next Steps:${NC}"
echo -e "    1. Open Telegram → message your bot → say ${CYAN}\"Hello SPESION\"${NC}"
echo -e "    2. Try: ${CYAN}\"What can you do?\"${NC}"
echo -e "    3. Try: ${CYAN}\"Run full system status\"${NC}"
echo -e "    4. Read: ${CYAN}SPESION_3_0.md${NC} for the full feature reference"
echo ""
echo -e "  ${HEART} ${BOLD}SPESION learns from every interaction. The more you use it,"
echo -e "     the smarter it gets.${NC}"
echo ""
