#Requires -Version 5.1
$ErrorActionPreference = "Stop"

function WOk([string]$t){Write-Host("[OK] "+$t)-ForegroundColor Green}
function WWarn([string]$t){Write-Host("[WARN] "+$t)-ForegroundColor Yellow}
function WErr([string]$t){Write-Host("[ERR] "+$t)-ForegroundColor Red}
function WInfo([string]$t){Write-Host("[INFO] "+$t)-ForegroundColor Cyan}
function Section([string]$t){Write-Host "`n============================================================" -ForegroundColor Cyan;Write-Host $t -ForegroundColor Cyan;Write-Host "============================================================" -ForegroundColor Cyan}

function Ask([string]$Prompt,[string]$Default="",[switch]$Secret){
  if($Default){Write-Host "$Prompt [default: $Default]"}else{Write-Host $Prompt}
  if($Secret){
    $s=Read-Host "->" -AsSecureString
    $b=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($s)
    $v=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($b)
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($b)
  }else{$v=Read-Host "->"}
  if([string]::IsNullOrWhiteSpace($v) -and $Default){return $Default}
  return $v
}

function AskYesNo([string]$Prompt,[ValidateSet('y','n')][string]$Default='y'){
  $s=if($Default -eq 'y'){'[Y/n]'}else{'[y/N]'}
  Write-Host "$Prompt $s"
  $a=Read-Host "->"
  if([string]::IsNullOrWhiteSpace($a)){$a=$Default}
  return ($a -match '^[yY]')
}

$ScriptDir=Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir=Split-Path -Parent $ScriptDir
$EnvFile=Join-Path $ProjectDir ".env"
$DataDir=Join-Path $ProjectDir "data"
if(-not(Test-Path $DataDir)){New-Item -ItemType Directory -Path $DataDir -Force|Out-Null}

function WriteEnv([string]$k,[string]$v){
  if(-not(Test-Path $EnvFile)){New-Item -ItemType File -Path $EnvFile -Force|Out-Null}
  $c=Get-Content $EnvFile -Raw -ErrorAction SilentlyContinue
  if($null -eq $c){$c=""}
  if($c -match "(?m)^$([regex]::Escape($k))="){
    $c=$c -replace "(?m)^$([regex]::Escape($k))=.*$", "$k=$v"
    Set-Content $EnvFile -Value $c -Encoding ASCII
  }else{Add-Content $EnvFile -Value "$k=$v" -Encoding ASCII}
}

function RunCompose([string[]]$Args){
  $composeArgs=@("compose","--env-file",$EnvFile,"-f","docker/docker-compose.yml")
  if((Get-Content $EnvFile -Raw -ErrorAction SilentlyContinue) -match "(?m)^DEPLOY_MODE=production$"){
    $composeArgs+=@("-f","docker/docker-compose.prod.yml")
  }
  $composeArgs += $Args
  & docker @composeArgs
}

Section "SPESION 3.0 setup (Windows safe mode)"
Write-Host "Project: $ProjectDir"
if(-not(AskYesNo "Start setup now?" 'y')){exit 0}

Section "1/5 Prerequisites"
if(Get-Command winget -ErrorAction SilentlyContinue){WOk "winget found"}else{WWarn "winget not found"}

if(-not(Get-Command docker -ErrorAction SilentlyContinue)){
  if(Get-Command winget -ErrorAction SilentlyContinue){
    WInfo "Installing Docker Desktop"
    winget install --id Docker.DockerDesktop --accept-source-agreements --accept-package-agreements
    throw "Start Docker Desktop and re-run this script."
  }else{throw "Install Docker Desktop manually first."}
}

try{docker info|Out-Null;WOk "Docker daemon running"}catch{
  $dex="C:\Program Files\Docker\Docker\Docker Desktop.exe"
  if(Test-Path $dex){Start-Process $dex}
  WInfo "Waiting for Docker daemon"
  $ok=$false
  1..60|ForEach-Object{Start-Sleep 2;try{docker info|Out-Null;$ok=$true;break}catch{}}
  if(-not $ok){throw "Docker daemon not ready. Open Docker Desktop then rerun."}
}

if(-not(Get-Command ollama -ErrorAction SilentlyContinue) -and (Get-Command winget -ErrorAction SilentlyContinue)){
  WInfo "Installing Ollama"
  winget install --id Ollama.Ollama --accept-source-agreements --accept-package-agreements
}

Section "2/5 Environment"
if(Test-Path $EnvFile){
  if(AskYesNo "Existing .env found. Rebuild from scratch?" 'n'){
    Copy-Item $EnvFile ($EnvFile+".backup."+(Get-Date -Format "yyyyMMddHHmmss")) -Force
    Set-Content $EnvFile -Value "" -Encoding ASCII
  }
}

WriteEnv "SPESION_HOST" "0.0.0.0"
WriteEnv "SPESION_PORT" "8100"
WriteEnv "DEBUG" "false"
WriteEnv "LOG_LEVEL" "INFO"
WriteEnv "OLLAMA_BASE_URL" "http://ollama:11434"
WriteEnv "OPENAI_API_KEY" ""
WriteEnv "ANTHROPIC_API_KEY" ""
WriteEnv "TELEGRAM_BOT_TOKEN" ""
WriteEnv "TELEGRAM_ALLOWED_USER_IDS" ""
WriteEnv "DISCORD_BOT_TOKEN" ""
WriteEnv "DISCORD_GUILD_ID" ""
WriteEnv "NOTION_API_KEY" ""
WriteEnv "NOTION_TASKS_DATABASE_ID" ""
WriteEnv "NOTION_JOURNAL_DATABASE_ID" ""
WriteEnv "NOTION_CRM_DATABASE_ID" ""
WriteEnv "NOTION_BOOKS_DATABASE_ID" ""
WriteEnv "NOTION_TRAININGS_DATABASE_ID" ""
WriteEnv "NOTION_FINANCE_DATABASE_ID" ""
WriteEnv "NOTION_TRANSACTIONS_DATABASE_ID" ""
WriteEnv "GARMIN_EMAIL" ""
WriteEnv "GARMIN_PASSWORD" ""
WriteEnv "IBKR_FLEX_TOKEN" ""
WriteEnv "IBKR_FLEX_QUERY_ID" ""
WriteEnv "TWILIO_ACCOUNT_SID" ""
WriteEnv "TWILIO_AUTH_TOKEN" ""
WriteEnv "TWILIO_PHONE_NUMBER" ""
WriteEnv "SMTP_USERNAME" ""
WriteEnv "SMTP_PASSWORD" ""
WriteEnv "SMTP_FROM_NAME" "SPESION"
WriteEnv "TAVILY_API_KEY" ""
WriteEnv "GITHUB_TOKEN" ""
WriteEnv "AUTONOMOUS_ENABLED" "true"
WriteEnv "HEARTBEAT_ENABLED" "true"
WriteEnv "HEARTBEAT_TIMEZONE" (Ask "Timezone" "Europe/Madrid")
WriteEnv "CHROMA_PERSIST_DIR" "/app/data/chroma"
WriteEnv "SQLITE_DB_PATH" "/app/data/spesion.db"
WriteEnv "SMTP_HOST" "smtp.gmail.com"
WriteEnv "SMTP_PORT" "587"
WriteEnv "TWILIO_CALLBACK_URL" ""

$key=-join ((48..57)+(65..90)+(97..122)|Get-Random -Count 32|ForEach-Object{[char]$_})
WriteEnv "SPESION_API_KEY" $key

if(AskYesNo "Configure OpenAI key?" 'y'){WriteEnv "OPENAI_API_KEY" (Ask "OpenAI API key" -Secret);WriteEnv "CLOUD_PROVIDER" "openai"}
if(AskYesNo "Configure Anthropic key?" 'n'){WriteEnv "ANTHROPIC_API_KEY" (Ask "Anthropic API key" -Secret);if(-not((Get-Content $EnvFile -Raw)-match "(?m)^CLOUD_PROVIDER=")){WriteEnv "CLOUD_PROVIDER" "anthropic"}}
if(AskYesNo "Configure Telegram?" 'y'){
  WriteEnv "TELEGRAM_BOT_TOKEN" (Ask "Telegram bot token" -Secret)
  WriteEnv "TELEGRAM_ALLOWED_USER_IDS" (Ask "Telegram user id")
}
if(AskYesNo "Configure Notion?" 'n'){
  WriteEnv "NOTION_API_KEY" (Ask "Notion API key" -Secret)
  foreach($db in @('TASKS','JOURNAL','CRM','BOOKS','TRAININGS','FINANCE','TRANSACTIONS')){
    $v=Ask "Notion $db database id"
    if($v){WriteEnv ("NOTION_"+$db+"_DATABASE_ID") $v}
  }
}

Section "3/5 User profile"
$profile=Join-Path $DataDir "user_profile.md"
if(-not(Test-Path $profile) -and (AskYesNo "Create basic user profile?" 'y')){
  $name=Ask "Name"
  $age=Ask "Age"
  $job=Ask "Profession"
  $loc=Ask "Location"
  @"
## Perfil del Usuario: $name

### Datos Basicos
- Edad: $age
- Profesion: $job
- Ubicacion: $loc
"@ | Set-Content $profile -Encoding UTF8
}

Section "4/5 Deploy"
Set-Location $ProjectDir
Write-Host "Home mode is the best first boot on Windows Docker Desktop."
Write-Host "Production mode adds Caddy and expects your public domain to already be configured."
if(AskYesNo "Use production compose with Caddy?" 'n'){WriteEnv "DEPLOY_MODE" "production"}else{WriteEnv "DEPLOY_MODE" "home"}
RunCompose @("build")
$upResult = RunCompose @("up","-d")

try{docker exec spesion-ollama ollama pull llama3.2:3b|Out-Null}catch{WWarn "Could not pull llama3.2:3b inside container"}
try{docker exec spesion-ollama ollama pull qwen2.5:7b|Out-Null}catch{WWarn "Could not pull qwen2.5:7b inside container"}

Section "5/5 Verify"
docker ps --format "table {{.Names}}`t{{.Status}}" --filter "name=spesion"
try{Invoke-RestMethod -Uri "http://localhost:8100/health" -TimeoutSec 5|Out-Null;WOk "API healthy at http://localhost:8100/health"}catch{WWarn "API not healthy yet. Check logs."}

Write-Host ""
Write-Host "Run these after setup:" -ForegroundColor Magenta
Write-Host "powershell -File scripts\spesion.ps1 status"
Write-Host "powershell -File scripts\spesion.ps1 logs"
