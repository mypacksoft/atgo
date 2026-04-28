$ErrorActionPreference = "Stop"
$hostsPath = "C:\Windows\System32\drivers\etc\hosts"
$pgBin = "C:\Users\phuoc\postgres-portable\pgsql\bin\psql.exe"

# Query tenants
$rawSlugs = & $pgBin -h localhost -p 5433 -U atgo -d atgo -t -A -c "SELECT slug FROM tenants WHERE is_active = TRUE ORDER BY slug" 2>$null
$slugs = @($rawSlugs | Where-Object { $_ -and $_.Trim() -ne "" } | ForEach-Object { $_.Trim() })

$systemSubs = @("atgo.local","www.atgo.local","api.atgo.local","adms.atgo.local",
                "admin.atgo.local","cname.atgo.local","status.atgo.local","docs.atgo.local")
$entries = @()
foreach ($h in ($systemSubs + ($slugs | ForEach-Object { "$_.atgo.local" }))) {
    $entries += "127.0.0.1`t$h"
}

$marker_start = "# >>> ATGO autogen - do not edit between markers <<<"
$marker_end   = "# <<< ATGO autogen end >>>"
$ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$header = "# Sync-ed at $ts | $($slugs.Count) tenant(s): $($slugs -join ', ')"
$newSection = (@($marker_start, $header) + $entries + @($marker_end)) -join "`r`n"

$current = Get-Content $hostsPath -Raw -Encoding ASCII

# Remove old autogen section
$pattern = [regex]::Escape($marker_start) + "[\s\S]*?" + [regex]::Escape($marker_end)
$cleaned = [regex]::Replace($current, $pattern, "")

# Remove old "# ATGO local dev" ad-hoc block
$adhoc = "(?m)^# ATGO local dev\r?\n(?:127\.0\.0\.1\s+\S+\.atgo\.local\r?\n?)+"
$cleaned = [regex]::Replace($cleaned, $adhoc, "")

$final = $cleaned.TrimEnd() + "`r`n`r`n" + $newSection + "`r`n"

# Backup + write
$backup = "$hostsPath.atgo-backup-$(Get-Date -Format 'yyyyMMdd-HHmmss').txt"
Copy-Item $hostsPath $backup -Force
[System.IO.File]::WriteAllText($hostsPath, $final, [System.Text.Encoding]::ASCII)

ipconfig /flushdns | Out-Null

Write-Host "OK: $($slugs.Count) tenants synced -> $($entries.Count) entries"
