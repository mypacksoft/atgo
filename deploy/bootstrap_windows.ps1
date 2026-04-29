# ATGO production bootstrap on Windows Server 2016+ (designed for farm1).
#
# Idempotent. Safe to re-run.
# Run as Administrator only. SSH from local Windows triggers it via paramiko.
#
# Phases:
#   1. Folders + service account paths
#   2. Download installers (Python, Node.js, NSSM, win-acme, URL Rewrite, ARR)
#   3. Silent install runtimes
#   4. Extract Postgres portable from C:\atgo\pkgs\pgsql\ + init cluster on E:
#   5. Apply schema (init.sql + init_002 + init_003)
#   6. pip install -e apps/api ; npm ci + npm run build apps/portal
#   7. Register Windows services via NSSM
#   8. IIS URL Rewrite + ARR
#   9. Create IIS site `atgo` with bindings + rewrite rules
#  10. Open firewall (29812 already done; add IIS 80/443 if not present)
#  11. Bootstrap super admin
#
# Skip with: -SkipPhases 4,7  (etc.)

[CmdletBinding()]
param(
    [string] $Root           = "E:\atgo",
    [string] $PgDataPath     = "E:\atgo\pgdata",
    [string] $DbName         = "atgo",
    [string] $DbUser         = "atgo",
    [int]    $PgPort         = 5433,
    [int]    $ApiPort        = 8000,
    [int]    $PortalPort     = 3000,
    [int]    $PgsqlAlready   = 0,
    [string] $AdminEmail     = "admin@atgo.io",
    [string] $AdminPassword  = "ChangeMeNow!2026",
    [string] $JwtSecret      = "",
    [string] $BaseDomain     = "atgo.io",
    [int[]]  $SkipPhases     = @()
)

$ErrorActionPreference = "Stop"
$ProgressPreference    = "SilentlyContinue"

function log  ($m) { Write-Host ">> $m" -ForegroundColor Cyan }
function ok   ($m) { Write-Host "OK $m" -ForegroundColor Green }
function warn ($m) { Write-Host "!  $m" -ForegroundColor Yellow }
function fail ($m) { Write-Host "X  $m" -ForegroundColor Red ; throw $m }

# ---- elevation check ----
$current = [Security.Principal.WindowsIdentity]::GetCurrent()
if (-not (New-Object Security.Principal.WindowsPrincipal($current)).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)) {
    fail "must run as Administrator"
}

if (-not $JwtSecret) {
    Add-Type -AssemblyName System.Web
    $bytes = New-Object byte[] 48
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $JwtSecret = [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+','_').Replace('/','-')
}

$pkgs    = "$Root\pkgs"
$repo    = "$Root\repo"
$logs    = "$Root\logs"
$envFile = "$Root\atgo.env"

New-Item -ItemType Directory -Force -Path $Root,$pkgs,$logs | Out-Null

function Phase($n, $name) {
    if ($SkipPhases -contains $n) {
        warn "Phase $n - $name (skipped)"; return $false
    }
    log "Phase $n - $name"
    return $true
}

# ============================================================
# Phase 2 - Download installers
# ============================================================
function Download-If-Missing($url, $out) {
    if (Test-Path $out) { return }
    log "  downloading $url"
    Invoke-WebRequest -Uri $url -OutFile $out -UseBasicParsing
}

if (Phase 2 "Download installers") {
    Download-If-Missing "https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe"  "$pkgs\python-3.12.7.exe"
    Download-If-Missing "https://nodejs.org/dist/v20.18.0/node-v20.18.0-x64.msi"             "$pkgs\node-20.18.msi"
    Download-If-Missing "https://nssm.cc/release/nssm-2.24.zip"                              "$pkgs\nssm.zip"
    Download-If-Missing "https://github.com/win-acme/win-acme/releases/download/v2.2.9.1701/win-acme.v2.2.9.1701.x64.pluggable.zip" "$pkgs\winacme.zip"
    Download-If-Missing "https://download.microsoft.com/download/D/D/E/DDE57C26-C62C-4C59-A1BB-31D58B36ADA0/rewrite_amd64_en-US.msi" "$pkgs\urlrewrite.msi"
    Download-If-Missing "https://download.microsoft.com/download/E/9/8/E9849D6A-020E-47E4-9FD0-A023E99B54EB/requestRouter_amd64.msi" "$pkgs\arr.msi"
    ok "downloads ready"
}

# ============================================================
# Phase 3 - Silent install runtimes
# ============================================================
function Test-Cmd($name) { return [bool](Get-Command $name -ErrorAction SilentlyContinue) }

if (Phase 3 "Install runtimes") {
    # Python 3.12 (we want 3.12 specifically, even if 3.14 is on PATH)
    if (-not (Test-Path "C:\Program Files\Python312\python.exe")) {
        log "  installing Python 3.12.7"
        Start-Process -Wait -FilePath "$pkgs\python-3.12.7.exe" -ArgumentList @(
            "/quiet","InstallAllUsers=1","Include_pip=1","Include_test=0","Include_doc=0",
            "Include_launcher=0","TargetDir=C:\Program Files\Python312"
        )
    }
    $py = "C:\Program Files\Python312\python.exe"
    if (-not (Test-Path $py)) { fail "Python 3.12 install failed" }

    # Node.js 20 LTS
    if (-not (Test-Cmd node) -or ((& node -v 2>$null) -notlike "v20*")) {
        log "  installing Node.js 20"
        Start-Process -Wait -FilePath msiexec -ArgumentList @(
            "/i", "$pkgs\node-20.18.msi", "/qn", "/norestart"
        )
        $env:Path = "C:\Program Files\nodejs;$env:Path"
    }

    # NSSM
    if (-not (Test-Path "$pkgs\nssm-2.24\win64\nssm.exe")) {
        log "  extracting NSSM"
        Expand-Archive -Path "$pkgs\nssm.zip" -DestinationPath $pkgs -Force
    }
    $nssm = "$pkgs\nssm-2.24\win64\nssm.exe"

    # win-acme
    if (-not (Test-Path "$pkgs\winacme")) {
        log "  extracting win-acme"
        Expand-Archive -Path "$pkgs\winacme.zip" -DestinationPath "$pkgs\winacme" -Force
    }

    # URL Rewrite + ARR
    if (-not (Test-Path "$env:SystemRoot\System32\inetsrv\rewrite.dll")) {
        log "  installing IIS URL Rewrite"
        Start-Process -Wait -FilePath msiexec -ArgumentList @("/i","$pkgs\urlrewrite.msi","/qn","/norestart")
    }
    if (-not (Test-Path "$env:SystemRoot\System32\inetsrv\config\arr.config*") -and `
        -not (Test-Path "$env:ProgramFiles\IIS\Application Request Routing")) {
        log "  installing IIS ARR"
        Start-Process -Wait -FilePath msiexec -ArgumentList @("/i","$pkgs\arr.msi","/qn","/norestart")
    }
    ok "runtimes installed"
}

# ============================================================
# Phase 4 - Postgres cluster init
# ============================================================
$pgBin = "$pkgs\pgsql\bin"
if (Phase 4 "Postgres cluster") {
    if (-not (Test-Path "$pgBin\postgres.exe")) {
        fail "Postgres portable missing at $pgBin (expected to be uploaded by push script)"
    }
    if (-not (Test-Path "$PgDataPath\PG_VERSION")) {
        log "  initdb on $PgDataPath"
        New-Item -ItemType Directory -Force -Path $PgDataPath | Out-Null
        & "$pgBin\initdb.exe" -D $PgDataPath -U $DbUser --auth=trust --encoding=UTF8 --no-locale | Out-Null
        # Set port
        (Get-Content "$PgDataPath\postgresql.conf") `
            -replace '^#?port = \d+', "port = $PgPort" `
            | Set-Content "$PgDataPath\postgresql.conf"
        # listen_addresses=localhost only (security: postgres must NOT be public)
        (Get-Content "$PgDataPath\postgresql.conf") `
            -replace "^#?listen_addresses = .*", "listen_addresses = 'localhost'" `
            | Set-Content "$PgDataPath\postgresql.conf"
    }

    # Register postgres as Windows service if missing
    $pgService = Get-Service "atgo-postgres" -ErrorAction SilentlyContinue
    $nssm = "$pkgs\nssm-2.24\win64\nssm.exe"
    if (-not $pgService) {
        log "  registering atgo-postgres service"
        & $nssm install "atgo-postgres" "$pgBin\postgres.exe" "-D" "$PgDataPath"
        & $nssm set "atgo-postgres" Start SERVICE_AUTO_START
        & $nssm set "atgo-postgres" AppStdout "$logs\postgres.log"
        & $nssm set "atgo-postgres" AppStderr "$logs\postgres.err.log"
        & $nssm set "atgo-postgres" AppRotateFiles 1
        & $nssm set "atgo-postgres" AppRotateBytes 10485760
    }
    Start-Service "atgo-postgres" -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 3

    # Create DB if missing
    & "$pgBin\psql.exe" -h localhost -p $PgPort -U $DbUser -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$DbName'" 2>$null `
        | Tee-Object -Variable dbCheck | Out-Null
    if (-not ($dbCheck -match "1")) {
        log "  creating database $DbName"
        & "$pgBin\createdb.exe" -h localhost -p $PgPort -U $DbUser $DbName
    }

    # Apply schemas
    foreach ($sql in @("$repo\infra\postgres\init.sql",
                       "$repo\infra\postgres\init_002_features.sql",
                       "$repo\infra\postgres\init_003_attendance_features.sql")) {
        if (Test-Path $sql) {
            log "  applying $(Split-Path -Leaf $sql)"
            & "$pgBin\psql.exe" -h localhost -p $PgPort -U $DbUser -d $DbName -v ON_ERROR_STOP=0 -f $sql 2>&1 | Out-Null
        }
    }
    ok "postgres ready (port $PgPort, data $PgDataPath)"
}

# ============================================================
# Phase 5 - .env file
# ============================================================
if (Phase 5 ".env") {
    $envContent = @"
ENVIRONMENT=production
BASE_DOMAIN=$BaseDomain
DATABASE_URL=postgresql+asyncpg://${DbUser}@127.0.0.1:${PgPort}/${DbName}
REDIS_URL=redis://disabled
JWT_SECRET=$JwtSecret
JWT_ALGORITHM=HS256
JWT_ACCESS_TTL_MINUTES=60
JWT_REFRESH_TTL_DAYS=30
CORS_ORIGINS=https://$BaseDomain,https://api.$BaseDomain,https://admin.$BaseDomain
NEXT_PUBLIC_API_BASE=https://api.$BaseDomain
NEXT_PUBLIC_BASE_DOMAIN=$BaseDomain
INTERNAL_API_BASE=http://127.0.0.1:$ApiPort
"@
    Set-Content -Path $envFile -Value $envContent -Encoding ASCII
    ok ".env -> $envFile"
}

# ============================================================
# Phase 6 - pip install + npm build
# ============================================================
$py    = "C:\Program Files\Python312\python.exe"
$venv  = "$Root\.venv"
if (Phase 6 "Python deps + portal build") {
    if (-not (Test-Path "$venv\Scripts\python.exe")) {
        log "  creating venv"
        & $py -m venv $venv
    }
    & "$venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
    & "$venv\Scripts\pip.exe" install -e "$repo\apps\api" tzdata --quiet

    log "  building Next.js portal"
    Push-Location "$repo\apps\portal"
    try {
        & "C:\Program Files\nodejs\npm.cmd" ci --no-audit --no-fund --silent
        $env:NEXT_PUBLIC_API_BASE     = "https://api.$BaseDomain"
        $env:NEXT_PUBLIC_BASE_DOMAIN  = $BaseDomain
        $env:INTERNAL_API_BASE        = "http://127.0.0.1:$ApiPort"
        & "C:\Program Files\nodejs\npm.cmd" run build --silent
    } finally { Pop-Location }
    ok "app built"
}

# ============================================================
# Phase 7 - NSSM services
# ============================================================
$nssm = "$pkgs\nssm-2.24\win64\nssm.exe"
if (Phase 7 "Register Windows services") {
    # API
    if (-not (Get-Service "atgo-api" -ErrorAction SilentlyContinue)) {
        log "  registering atgo-api"
        & $nssm install "atgo-api" "$venv\Scripts\python.exe" "-m" "uvicorn" "atgo_api.main:app" "--host" "127.0.0.1" "--port" "$ApiPort" "--workers" "4" "--proxy-headers" "--forwarded-allow-ips=*"
        & $nssm set "atgo-api" AppDirectory "$repo\apps\api"
        & $nssm set "atgo-api" AppEnvironmentExtra ":ATGO_ENV_FILE=$envFile"
        # Read env file values into NSSM env (so uvicorn sees them)
        $envLines = Get-Content $envFile | Where-Object { $_ -match "=" -and -not $_.StartsWith("#") }
        $envExtra = $envLines -join [char]0
        & $nssm set "atgo-api" AppEnvironmentExtra $envExtra
        & $nssm set "atgo-api" Start SERVICE_AUTO_START
        & $nssm set "atgo-api" AppStdout "$logs\api.log"
        & $nssm set "atgo-api" AppStderr "$logs\api.err.log"
        & $nssm set "atgo-api" AppRotateFiles 1
        & $nssm set "atgo-api" AppRotateBytes 10485760
    } else {
        # Update env on re-run
        $envLines = Get-Content $envFile | Where-Object { $_ -match "=" -and -not $_.StartsWith("#") }
        & $nssm set "atgo-api" AppEnvironmentExtra ($envLines -join [char]0) | Out-Null
    }

    # Portal
    if (-not (Get-Service "atgo-portal" -ErrorAction SilentlyContinue)) {
        log "  registering atgo-portal"
        & $nssm install "atgo-portal" "C:\Program Files\nodejs\node.exe" "node_modules\next\dist\bin\next" "start" "-p" "$PortalPort"
        & $nssm set "atgo-portal" AppDirectory "$repo\apps\portal"
        & $nssm set "atgo-portal" Start SERVICE_AUTO_START
        & $nssm set "atgo-portal" AppStdout "$logs\portal.log"
        & $nssm set "atgo-portal" AppStderr "$logs\portal.err.log"
        $envLines = Get-Content $envFile | Where-Object { $_ -match "=" -and -not $_.StartsWith("#") }
        & $nssm set "atgo-portal" AppEnvironmentExtra ($envLines -join [char]0) | Out-Null
    }

    Restart-Service "atgo-api","atgo-portal" -ErrorAction SilentlyContinue
    ok "services running"
}

# ============================================================
# Phase 8 - IIS reverse proxy
# ============================================================
if (Phase 8 "IIS reverse proxy") {
    Import-Module WebAdministration

    # Enable proxy in ARR globally
    & "$env:SystemRoot\System32\inetsrv\appcmd.exe" set config -section:system.webServer/proxy /enabled:"True" /commit:apphost | Out-Null

    $sitePath = "$Root\iis-stub"
    New-Item -ItemType Directory -Force -Path $sitePath | Out-Null
    Set-Content -Path "$sitePath\index.html" -Value "<h1>ATGO</h1><p>routed by IIS ARR.</p>"

    # Create site if missing
    if (-not (Get-Website -Name "atgo" -ErrorAction SilentlyContinue)) {
        log "  creating IIS site 'atgo'"
        New-Website -Name "atgo" -PhysicalPath $sitePath -Port 80 -HostHeader "$BaseDomain" -Force | Out-Null
    }

    # Add bindings (idempotent)
    $hosts = @($BaseDomain, "www.$BaseDomain", "api.$BaseDomain", "admin.$BaseDomain",
               "adms.$BaseDomain", "cname.$BaseDomain")
    foreach ($h in $hosts) {
        $existing = Get-WebBinding -Name "atgo" -HostHeader $h -Protocol http -ErrorAction SilentlyContinue
        if (-not $existing) {
            New-WebBinding -Name "atgo" -Protocol http -Port 80 -HostHeader $h | Out-Null
        }
    }
    # Wildcard binding via empty host header is tricky in IIS; we add specific
    # tenant subdomain bindings dynamically when they sign up. For now, manual.

    # Write web.config with rewrite rules
    $webConfig = @'
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
  <system.webServer>
    <rewrite>
      <rules>
        <rule name="ATGO ADMS" stopProcessing="true">
          <match url="(.*)" />
          <conditions>
            <add input="{HTTP_HOST}" pattern="^adms\." />
          </conditions>
          <action type="Rewrite" url="http://127.0.0.1:__APIPORT__/{R:1}" />
        </rule>
        <rule name="ATGO API" stopProcessing="true">
          <match url="(.*)" />
          <conditions>
            <add input="{HTTP_HOST}" pattern="^api\." />
          </conditions>
          <action type="Rewrite" url="http://127.0.0.1:__APIPORT__/{R:1}" />
        </rule>
        <rule name="ATGO API path" stopProcessing="true">
          <match url="^(api|iclock)/(.*)" />
          <action type="Rewrite" url="http://127.0.0.1:__APIPORT__/{R:1}/{R:2}" />
        </rule>
        <rule name="ATGO Portal" stopProcessing="true">
          <match url="(.*)" />
          <action type="Rewrite" url="http://127.0.0.1:__PORTALPORT__/{R:1}" />
        </rule>
      </rules>
      <outboundRules>
        <preConditions>
          <preCondition name="IsHTML">
            <add input="{RESPONSE_CONTENT_TYPE}" pattern="^text/html" />
          </preCondition>
        </preConditions>
      </outboundRules>
    </rewrite>
    <httpProtocol>
      <customHeaders>
        <remove name="X-Powered-By" />
      </customHeaders>
    </httpProtocol>
  </system.webServer>
</configuration>
'@.Replace("__APIPORT__", "$ApiPort").Replace("__PORTALPORT__", "$PortalPort")
    Set-Content -Path "$sitePath\web.config" -Value $webConfig -Encoding UTF8

    Restart-WebItem "IIS:\Sites\atgo" -ErrorAction SilentlyContinue
    ok "IIS site 'atgo' ready (HTTP only — SSL added by win-acme later)"
}

# ============================================================
# Phase 11 - bootstrap super admin
# ============================================================
if (Phase 11 "Bootstrap super admin") {
    Push-Location "$repo\apps\api"
    try {
        $envLines = Get-Content $envFile
        foreach ($line in $envLines) {
            if ($line -match "^([^=#]+)=(.*)$") {
                Set-Item "Env:$($Matches[1].Trim())" $Matches[2]
            }
        }
        & "$venv\Scripts\python.exe" -m scripts.bootstrap_admin $AdminEmail --password=$AdminPassword --name="ATGO Admin"
    } finally { Pop-Location }
    ok "super admin: $AdminEmail / $AdminPassword"
}

Write-Host ""
Write-Host "================================================================" -ForegroundColor Green
Write-Host "  ATGO bootstrap complete"                                          -ForegroundColor Green
Write-Host "================================================================" -ForegroundColor Green
Write-Host "  Postgres   :  127.0.0.1:$PgPort  data=$PgDataPath"
Write-Host "  API        :  127.0.0.1:$ApiPort  (Windows service: atgo-api)"
Write-Host "  Portal     :  127.0.0.1:$PortalPort  (Windows service: atgo-portal)"
Write-Host "  IIS site   :  atgo  (HTTP/80 -> ARR -> 127.0.0.1)"
Write-Host "  Admin      :  $AdminEmail / $AdminPassword"
Write-Host "  JWT secret :  saved in $envFile"
Write-Host ""
Write-Host "Next:"
Write-Host "  1. Add A records at Dynadot:"
Write-Host "       atgo.io       115.78.15.192"
Write-Host "       www.atgo.io   115.78.15.192"
Write-Host "       *.atgo.io     115.78.15.192"
Write-Host "       api/admin/adms/cname.atgo.io  115.78.15.192"
Write-Host "  2. Run win-acme to issue SSL cert (interactive)"
