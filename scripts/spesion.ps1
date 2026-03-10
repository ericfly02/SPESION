# =============================================================================
# SPESION 3.0 - Management Commands (Windows PowerShell)
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
    [string]$Command = "help",

    [Parameter(Position=1, ValueFromRemainingArguments=$true)]
    [string[]]$RemainingArgs
)

$ErrorActionPreference = "Continue"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$EnvFile = Join-Path $ProjectDir ".env"
$BaseComposeFile = Join-Path $ProjectDir "docker\docker-compose.yml"
$ProdComposeFile = Join-Path $ProjectDir "docker\docker-compose.prod.yml"

function Write-Ok([string]$Text) { Write-Host ("[OK] " + $Text) -ForegroundColor Green }
function Write-Warn([string]$Text) { Write-Host ("[WARN] " + $Text) -ForegroundColor Yellow }
function Write-Err([string]$Text) { Write-Host ("[ERR] " + $Text) -ForegroundColor Red }
function Write-Info([string]$Text) { Write-Host ("[INFO] " + $Text) -ForegroundColor Cyan }

function Get-UseProduction {
    if (-not (Test-Path $EnvFile)) { return $false }
    $content = Get-Content $EnvFile -Raw -ErrorAction SilentlyContinue
    return ($content -match "(?m)^DEPLOY_MODE=production$")
}

function Invoke-Compose {
    param([string[]]$ComposeArgs)

    $args = @("compose", "--env-file", $EnvFile, "-f", $BaseComposeFile)
    if ((Get-UseProduction) -and (Test-Path $ProdComposeFile)) {
        $args += @("-f", $ProdComposeFile)
    }
    $args += $ComposeArgs
    & docker @args
}

function Show-Help {
    Write-Host ""
    Write-Host "SPESION 3.0 Management" -ForegroundColor Magenta
    Write-Host ""
    Write-Host "Usage: powershell -File scripts\spesion.ps1 status" -ForegroundColor White
    Write-Host ""
    Write-Host "Commands:" -ForegroundColor Cyan
    Write-Host "  start       Start all services"
    Write-Host "  stop        Stop all services"
    Write-Host "  restart     Restart all services"
    Write-Host "  status      Show container and API status"
    Write-Host "  logs        Follow logs; optional service name"
    Write-Host "  health      Check API, Ollama, and optional Caddy"
    Write-Host "  shell       Open shell in spesion container"
    Write-Host "  models      List Ollama models"
    Write-Host "  pull-model  Pull an Ollama model"
    Write-Host "  backup      Zip data directory"
    Write-Host "  update      git pull, rebuild, restart"
    Write-Host "  reflect     Run reflection module"
    Write-Host "  tools       List YAML tool manifests"
    Write-Host ""
}

switch ($Command) {
    "start" {
        Write-Info "Starting services"
        $withBuild = $false
        if ($RemainingArgs -and ($RemainingArgs -contains "--build")) {
            $withBuild = $true
        }

        if ($withBuild) {
            Write-Info "Rebuilding images before start"
            Invoke-Compose @("build")
            Invoke-Compose @("up", "-d", "--force-recreate")
        } else {
            Invoke-Compose @("up", "-d")
        }
        Start-Sleep -Seconds 3
        Invoke-Compose @("ps")
        Write-Host ""
        try {
            Invoke-RestMethod -Uri "http://localhost:8100/health" -TimeoutSec 5 | Out-Null
            Write-Ok "API healthy"
        } catch {
            Write-Warn "API not healthy yet; showing recent logs"
            docker logs --tail 80 spesion 2>$null
            docker logs --tail 80 spesion-ollama 2>$null
        }
    }
    "stop" {
        Write-Info "Stopping services"
        Invoke-Compose @("down")
    }
    "restart" {
        Write-Info "Restarting services"
        Invoke-Compose @("restart")
    }
    "status" {
        Write-Host ""
        Write-Host "Containers:" -ForegroundColor Cyan
        docker ps --format "table {{.Names}}`t{{.Status}}`t{{.Ports}}" --filter "name=spesion"
        Write-Host ""
        Write-Host "Containers (including exited):" -ForegroundColor Cyan
        docker ps -a --format "table {{.Names}}`t{{.Status}}`t{{.Image}}" --filter "name=spesion"
        Write-Host ""
        Write-Host "API health:" -ForegroundColor Cyan
        try {
            $response = Invoke-RestMethod -Uri "http://localhost:8100/health" -TimeoutSec 5
            Write-Ok "API healthy"
            $response | ConvertTo-Json -Depth 4 | Write-Host
        } catch {
            Write-Warn "API not responding"
        }
        Write-Host ""
        Write-Host "Ollama models:" -ForegroundColor Cyan
        try {
            docker exec spesion-ollama ollama list
        } catch {
            Write-Warn "spesion-ollama container not available"
            Write-Host ""
            Write-Host "Recent logs (spesion-ollama):" -ForegroundColor Cyan
            docker logs --tail 80 spesion-ollama 2>$null
            Write-Host ""
            Write-Host "Recent logs (spesion):" -ForegroundColor Cyan
            docker logs --tail 80 spesion 2>$null
        }
    }
    "logs" {
        $service = if ($RemainingArgs -and $RemainingArgs.Count -gt 0) { $RemainingArgs[0] } else { "" }
        if ($service) {
            Invoke-Compose @("logs", "-f", "--tail=100", $service)
        } else {
            Invoke-Compose @("logs", "-f", "--tail=100")
        }
    }
    "health" {
        Write-Host ""
        Write-Host "Health checks:" -ForegroundColor Cyan
        try {
            Invoke-RestMethod -Uri "http://localhost:8100/health" -TimeoutSec 5 | Out-Null
            Write-Ok "SPESION API healthy on 8100"
        } catch {
            Write-Err "SPESION API unreachable"
        }
        try {
            docker exec spesion-ollama curl -sf http://localhost:11434/api/tags | Out-Null
            Write-Ok "Ollama healthy"
        } catch {
            Write-Err "Ollama unreachable"
        }
        try {
            if (Get-Command curl.exe -ErrorAction SilentlyContinue) {
                curl.exe -k -sSf https://localhost > $null
                Write-Ok "Caddy reachable on 443"
            } else {
                Write-Info "curl.exe not available; skipping Caddy check"
            }
        } catch {
            Write-Info "Caddy not running or not used"
        }
    }
    "shell" {
        docker exec -it spesion /bin/bash
    }
    "models" {
        try {
            docker exec spesion-ollama ollama list
        } catch {
            Write-Warn "spesion-ollama container not available"
        }
    }
    "pull-model" {
        $model = if ($RemainingArgs -and $RemainingArgs.Count -gt 0) { $RemainingArgs[0] } else { "llama3.2:3b" }
        Write-Info ("Pulling model: " + $model)
        docker exec spesion-ollama ollama pull $model
    }
    "backup" {
        $dataPath = Join-Path $ProjectDir "data"
        $backupDir = Join-Path $ProjectDir "backups"
        $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
        $backupFile = Join-Path $backupDir ("spesion_backup_" + $timestamp + ".zip")
        if (-not (Test-Path $backupDir)) { New-Item -ItemType Directory -Path $backupDir -Force | Out-Null }
        Compress-Archive -Path $dataPath -DestinationPath $backupFile -Force
        Write-Ok ("Backup created: " + $backupFile)
    }
    "update" {
        Push-Location $ProjectDir
        try {
            git pull
            Invoke-Compose @("build")
            Invoke-Compose @("up", "-d")
            Write-Ok "Update complete"
        } finally {
            Pop-Location
        }
    }
    "reflect" {
        docker exec spesion python -m src.cognitive.reflection
    }
    "tools" {
        $manifestDir = Join-Path $ProjectDir "tools\manifests"
        if (-not (Test-Path $manifestDir)) {
            Write-Warn "tools/manifests not found"
        } else {
            Get-ChildItem $manifestDir -Include *.yaml,*.yml | ForEach-Object {
                Write-Host $_.Name -ForegroundColor Green
            }
        }
    }
    default {
        Show-Help
    }
}
