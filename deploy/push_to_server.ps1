# ATGO — push local source to remote server and bootstrap.
#
# Run from Windows. Uses built-in OpenSSH client.
#
# Examples:
#   pwsh deploy\push_to_server.ps1 -Server your-server.example.com -RemoteUser root -Domain atgo.example.com
#   pwsh deploy\push_to_server.ps1 -Server your-server.example.com -RemoteUser deploy -KeyPath $HOME\.ssh\id_ed25519 -Domain atgo.io
#
# What it does:
#   1. Tars the project (excluding venv / node_modules / .pgdata)
#   2. scp to /tmp on server
#   3. scp deploy/bootstrap_server.sh to /tmp
#   4. ssh + run bootstrap as root (sudo)
#   5. Pulls back the deploy private key to ./deploy/atgo_deploy_key
#
# Re-running pushes new code & bootstrap. Bootstrap is idempotent.

[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string] $Server,
    [Parameter(Mandatory)] [string] $Domain,
    [string] $RemoteUser  = "root",
    [int]    $RemotePort  = 22,
    [string] $KeyPath     = "",
    [string] $AdminEmail  = "",
    [switch] $SkipPush
)

$ErrorActionPreference = "Stop"
$root  = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$tar   = "$env:TEMP\atgo-source.tgz"
$keyFile = Join-Path $root "deploy\atgo_deploy_key"

function Ssh($cmd) {
    $args = @("-p", "$RemotePort")
    if ($KeyPath) { $args += @("-i", $KeyPath, "-o", "IdentitiesOnly=yes") }
    $args += @("-o", "StrictHostKeyChecking=accept-new", "$RemoteUser@$Server", $cmd)
    & ssh @args
}
function Scp($local, $remote) {
    $args = @("-P", "$RemotePort")
    if ($KeyPath) { $args += @("-i", $KeyPath, "-o", "IdentitiesOnly=yes") }
    $args += @("-o", "StrictHostKeyChecking=accept-new", $local, "${RemoteUser}@${Server}:$remote")
    & scp @args
}
function ScpFrom($remote, $local) {
    $args = @("-P", "$RemotePort")
    if ($KeyPath) { $args += @("-i", $KeyPath, "-o", "IdentitiesOnly=yes") }
    $args += @("-o", "StrictHostKeyChecking=accept-new", "${RemoteUser}@${Server}:$remote", $local)
    & scp @args
}

if (-not $SkipPush) {
    Write-Host "▶ Tar-ing project..." -ForegroundColor Cyan
    Push-Location $root
    try {
        $excludes = @(".venv","node_modules",".next","__pycache__",".pytest_cache",
                       ".pgdata",".env","deploy/atgo_deploy_key","atgo-source.tgz",
                       "*.pyc",".mypy_cache",".ruff_cache",".git")
        $excludeArgs = $excludes | ForEach-Object { "--exclude=$_" }
        & tar -czf $tar @excludeArgs apps infra scripts deploy README.md .env.example .gitignore
    } finally { Pop-Location }
    Write-Host "  tarball: $tar ($((Get-Item $tar).Length / 1MB) MB)"

    Write-Host "▶ Pushing to ${RemoteUser}@${Server}:/tmp/..." -ForegroundColor Cyan
    Scp $tar "/tmp/atgo-source.tgz"
    Scp (Join-Path $root "deploy\bootstrap_server.sh") "/tmp/bootstrap_server.sh"
}

$adminEmailEnv = if ($AdminEmail) { "ADMIN_EMAIL='$AdminEmail'" } else { "" }
$bootstrapCmd = "sudo DOMAIN='$Domain' $adminEmailEnv bash /tmp/bootstrap_server.sh"

Write-Host "▶ Running bootstrap on $Server..." -ForegroundColor Cyan
Ssh $bootstrapCmd

# Fetch deploy key for future Claude Code SSH access.
Write-Host "▶ Fetching deploy key to $keyFile..." -ForegroundColor Cyan
ScpFrom "/opt/atgo/.ssh/atgo_deploy" $keyFile
if (Test-Path $keyFile) {
    # Restrict perms (Windows ACL — required by ssh.exe)
    & icacls $keyFile /inheritance:r | Out-Null
    & icacls $keyFile /grant:r "$($env:USERNAME):(R)" | Out-Null
}

Write-Host ""
Write-Host "✓ Done." -ForegroundColor Green
Write-Host ""
Write-Host "Test the deploy key:"
Write-Host "  ssh -i $keyFile -p $RemotePort atgo@$Server 'systemctl status atgo-api'"
Write-Host ""
Write-Host "URLs:"
Write-Host "  https://$Domain"
Write-Host "  https://api.$Domain"
Write-Host "  https://admin.$Domain"
Write-Host "  https://adms.$Domain/iclock/cdata"
