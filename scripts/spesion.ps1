# =============================================================================
# SPESION 3.0 — Management Commands (Windows PowerShell)
# =============================================================================
# Quick management commands for your running SPESION instance.
#
# Usage:
#   .\scripts\spesion.ps1 <command>
#
# Commands:
#   start       Start all services
#   stop        Stop all services
#   restart     Restart all services
#   status      Show system status
#   logs        Live-follow container logs
#   health      Check API health
#   shell       Open shell in SPESION container
#   models      List Ollama models
#   pull-model  Pull an Ollama model
#   backup      Backup data directory
#   update      Pull latest code and rebuild
#   reflect     Trigger cognitive reflection
#   tools       List registered custom tools
# =============================================================================

param(
    [Parameter(Position=0)]
    [string]$Command,

    [Parameter(Position=1, ValueFromRemainingArguments)]
    [string[]]$Args
)

$ErrorActionPreference = "Continue"
$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir

function Write-Ok($text)   { Write-Host "  ✅ $text" -ForegroundColor Green }
function Write-Warn($text) { Write-Host "  ⚠️  $text" -ForegroundColor Yellow }
function Write-Err($text)  { Write-Host "  ❌ $text" -ForegroundColor Red }
function Write-Info($text) { Write-Host "  ℹ️  $text" -ForegroundColor Blue }

# Determine compose files
$COMPOSE = "docker compose -f `"$ProjectDir\docker\docker-compose.yml`""
if (Test-Path "$ProjectDir\docker\docker-compose.prod.yml") {
    if (Test-Path "$ProjectDir\.env") {
        $content = Get-Content "$ProjectDir\.env" -Raw -ErrorAction SilentlyContinue
        if ($content -match 'DEPLOY_MODE=production') {
            $COMPOSE += " -f `"$ProjectDir\docker\docker-compose.prod.yml`""
        }
    }
}

function Invoke-Compose {
    param([string]$Arguments)
    Invoke-Expression "$COMPOSE $Arguments"
}

function Show-Help {
    Write-Host ""
    Write-Host "  🧠 SPESION 3.0 Management" -ForegroundColor Magenta
    Write-Host ""
    Write-Host "  Usage: .\scripts\spesion.ps1 <command>" -ForegroundColor White
    Write-Host ""
    Write-Host "  Commands:" -ForegroundColor Cyan
    Write-Host "    start        Start all services"
    Write-Host "    stop         Stop all services"
    Write-Host "    restart      Restart all services"
    Write-Host "    status       Show container & system status"
    Write-Host "    logs         Live-follow container logs"
    Write-Host "    health       Check API + Ollama health"
    Write-Host "    shell        Open shell in SPESION container"
    Write-Host "    models       List Ollama models"
    Write-Host "    pull-model   Pull an Ollama model (e.g., pull-model llama3.2:3b)"
    Write-Host "    backup       Backup data directory"
    Write-Host "    update       Pull latest code and rebuild"
    Write-Host "    reflect      Trigger cognitive reflection"
    Write-Host "    tools        List registered custom tools"
    Write-Host ""
}

switch ($Command) {
    "start" {
        Write-Info "Starting SPESION..."
        Invoke-Compose "up -d"
        Write-Ok "Services started!"
        Start-Sleep -Seconds 3
        Invoke-Compose "ps"
    }

    "stop" {
        Write-Info "Stopping SPESION..."
        Invoke-Compose "down"
        Write-Ok "Services stopped"
    }

    "restart" {
        Write-Info "Restarting SPESION..."
        Invoke-Compose "restart"
        Write-Ok "Services restarted"
    }

    "status" {
        Write-Host ""
        Write-Host "  🧠 SPESION System Status" -ForegroundColor Magenta
        Write-Host "  ─────────────────────────" -ForegroundColor Magenta
        Write-Host ""
        Write-Host "  Docker Containers:" -ForegroundColor Cyan
        docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" --filter "name=spesion"
        Write-Host ""

        Write-Host "  API Health:" -ForegroundColor Cyan
        try {
            $r = Invoke-RestMethod -Uri "http://localhost:8100/health" -TimeoutSec 5
            Write-Ok "API is healthy"
            $r | ConvertTo-Json -Depth 3 | Write-Host
        } catch { Write-Warn "API not responding" }
        Write-Host ""

        Write-Host "  Ollama Models:" -ForegroundColor Cyan
        docker exec spesion-ollama ollama list 2>$null

        Write-Host ""
        Write-Host "  Data Size:" -ForegroundColor Cyan
        $dataPath = Join-Path $ProjectDir "data"
        if (Test-Path $dataPath) {
            $size = (Get-ChildItem -Path $dataPath -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum / 1MB
            Write-Host "    $([math]::Round($size,2)) MB in data/" -ForegroundColor White
        }
    }

    "logs" {
        $svc = if ($Args) { $Args[0] } else { "" }
        Invoke-Compose "logs -f --tail=100 $svc"
    }

    "health" {
        Write-Host ""
        Write-Host "  Health Checks:" -ForegroundColor Cyan
        Write-Host ""

        # API
        try {
            Invoke-RestMethod -Uri "http://localhost:8100/health" -TimeoutSec 5 | Out-Null
            Write-Ok "SPESION API   — healthy (port 8100)"
        } catch { Write-Err "SPESION API   — unreachable" }

        # Ollama
        try {
            docker exec spesion-ollama curl -sf http://localhost:11434/api/tags 2>$null | Out-Null
            Write-Ok "Ollama        — healthy (port 11434)"
        } catch { Write-Err "Ollama        — unreachable" }

        # Caddy
        try {
            Invoke-RestMethod -Uri "https://localhost" -TimeoutSec 5 -SkipCertificateCheck | Out-Null
            Write-Ok "Caddy HTTPS   — healthy (port 443)"
        } catch { Write-Info "Caddy HTTPS   — not running (OK in home server mode)" }
    }

    "shell" {
        docker exec -it spesion-brain /bin/bash
    }

    "models" {
        Write-Host ""
        Write-Host "  Ollama Models:" -ForegroundColor Cyan
        docker exec spesion-ollama ollama list 2>$null
    }

    "pull-model" {
        $model = if ($Args) { $Args[0] } else { "llama3.2:3b" }
        Write-Info "Pulling $model..."
        docker exec spesion-ollama ollama pull $model
        Write-Ok "$model pulled"
    }

    "backup" {
        $dataPath = Join-Path $ProjectDir "data"
        $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
        $backupDir = Join-Path $ProjectDir "backups"
        $backupFile = Join-Path $backupDir "spesion_backup_$timestamp.zip"

        if (-not (Test-Path $backupDir)) { New-Item -ItemType Directory -Path $backupDir -Force | Out-Null }

        Write-Info "Creating backup..."
        Compress-Archive -Path $dataPath -DestinationPath $backupFile -Force
        $sizeMB = [math]::Round((Get-Item $backupFile).Length / 1MB, 2)
        Write-Ok "Backup saved: $backupFile ($sizeMB MB)"

        # Prune old backups (keep last 10)
        $backups = Get-ChildItem $backupDir -Filter "spesion_backup_*.zip" | Sort-Object CreationTime -Descending
        if ($backups.Count -gt 10) {
            $backups | Select-Object -Skip 10 | Remove-Item -Force
            Write-Info "Pruned old backups (keeping 10)"
        }
    }

    "update" {
        Write-Info "Pulling latest code..."
        Push-Location $ProjectDir
        git pull
        Write-Info "Rebuilding images..."
        Invoke-Compose "build"
        Write-Info "Restarting..."
        Invoke-Compose "up -d"
        Pop-Location
        Write-Ok "Updated and restarted!"
    }

    "reflect" {
        Write-Info "Triggering cognitive reflection..."
        docker exec spesion-brain python -m src.cognitive.reflection 2>$null
        Write-Ok "Reflection complete"
    }

    "tools" {
        Write-Host ""
        Write-Host "  🔧 Registered Custom Tools:" -ForegroundColor Cyan
        Write-Host ""

        $manifestDir = Join-Path $ProjectDir "tools\manifests"
        if (Test-Path $manifestDir) {
            $files = Get-ChildItem $manifestDir -Filter "*.yaml"
            if ($files.Count -eq 0) { $files = Get-ChildItem $manifestDir -Filter "*.yml" }
            foreach ($f in $files) {
                $name = $f.BaseName
                Write-Host "    📦 $name" -ForegroundColor Green
                Get-Content $f.FullName | Select-Object -First 5 | ForEach-Object { Write-Host "       $_" -ForegroundColor Blue }
                Write-Host ""
            }
        } else {
            Write-Info "No tool manifests found in tools/manifests/"
        }
    }

    default { Show-Help }
}
