# ATGO — auto-sync tenant slugs into Windows hosts file.
#
# Reads all active tenant slugs from Postgres and rewrites the ATGO section
# of C:\Windows\System32\drivers\etc\hosts. Always self-elevates via UAC.
#
# Usage (from any shell):
#   powershell -ExecutionPolicy Bypass -File D:\ATGO\scripts\sync_hosts.ps1

$ErrorActionPreference = "Stop"

# ---- 1. Self-elevate ----
$current = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($current)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "Re-launching as admin via UAC..." -ForegroundColor Yellow
    $args = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    Start-Process powershell -Verb RunAs -ArgumentList $args -Wait
    exit 0
}

# ---- 2. Query slugs from Postgres ----
$pgBin = "C:\Users\phuoc\postgres-portable\pgsql\bin\psql.exe"
if (-not (Test-Path $pgBin)) {
    Write-Error "psql.exe not found at $pgBin — adjust path"
    exit 1
}

$rawSlugs = & $pgBin -h localhost -p 5433 -U atgo -d atgo -t -A `
    -c "SELECT slug FROM tenants WHERE is_active = TRUE ORDER BY slug" 2>$null

$slugs = @($rawSlugs | Where-Object { $_ -and $_.Trim() -ne "" } | ForEach-Object { $_.Trim() })

# ---- 3. Build the section ----
$systemSubs = @("atgo.local", "www.atgo.local", "api.atgo.local",
                "adms.atgo.local", "admin.atgo.local", "cname.atgo.local",
                "status.atgo.local", "docs.atgo.local")
$tenantSubs = $slugs | ForEach-Object { "$_.atgo.local" }
$allHosts = $systemSubs + $tenantSubs

$marker_start = "# >>> ATGO autogen — do not edit between markers <<<"
$marker_end   = "# <<< ATGO autogen end >>>"

$lines = New-Object System.Collections.Generic.List[string]
$lines.Add($marker_start) | Out-Null
$lines.Add("# Sync-ed at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') · $($slugs.Count) tenant(s)") | Out-Null
foreach ($h in $allHosts) {
    $lines.Add("127.0.0.1`t$h") | Out-Null
}
$lines.Add($marker_end) | Out-Null
$newSection = $lines -join "`r`n"

# ---- 4. Splice into hosts file ----
$hostsPath = "$env:WINDIR\System32\drivers\etc\hosts"
$current = Get-Content $hostsPath -Raw -Encoding ASCII

# Strip old ATGO section if present (between markers)
$pattern = [regex]::Escape($marker_start) + "[\s\S]*?" + [regex]::Escape($marker_end)
$cleaned = [regex]::Replace($current, $pattern, "")

# Strip old ad-hoc "# ATGO local dev" block we wrote earlier
$adhoc = "(?m)^# ATGO local dev\r?\n(?:127\.0\.0\.1\s+\S+\.atgo\.local\r?\n)+"
$cleaned = [regex]::Replace($cleaned, $adhoc, "")

$cleaned = $cleaned.TrimEnd() + "`r`n`r`n" + $newSection + "`r`n"

# ---- 5. Backup + write ----
$backup = "$hostsPath.atgo-backup-$(Get-Date -Format 'yyyyMMdd-HHmmss').txt"
Copy-Item $hostsPath $backup -Force
[System.IO.File]::WriteAllText($hostsPath, $cleaned, [System.Text.Encoding]::ASCII)

# Flush DNS so new entries take effect immediately
ipconfig /flushdns | Out-Null

Write-Host ""
Write-Host "✓ hosts file updated" -ForegroundColor Green
Write-Host "  - $($systemSubs.Count) system hosts"
Write-Host "  - $($slugs.Count) tenant hosts: $($slugs -join ', ')"
Write-Host "  - backup: $backup"
Write-Host ""
Write-Host "Press any key to close..."
[void][System.Console]::ReadKey($true)
