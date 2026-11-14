param([int]$Port = 8765)
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
Write-Host "R9 connection diagnostic" -ForegroundColor Cyan
Write-Host "Project: $root"
Write-Host "Python .venv: $(Test-Path (Join-Path $root '.venv\Scripts\python.exe'))"
Write-Host "Python portable: $(Test-Path (Join-Path $root '.runtime\python\python.exe'))"
$ports = @($Port)
try {
    $extra = @(Get-NetTCPConnection -State Listen -ErrorAction Stop | Where-Object { $_.LocalPort -ge 8765 -and $_.LocalPort -le 8865 } | Select-Object -ExpandProperty LocalPort -Unique)
    $ports += $extra
} catch { Write-Host 'Cannot inspect open ports; probing configured port only.' }
$ports = @($ports | Sort-Object -Unique)
$found = $false
foreach ($p in $ports) {
    try {
        $result = Invoke-RestMethod "http://127.0.0.1:$p/health" -TimeoutSec 2 -ErrorAction Stop
        if ($result.ok -and $result.data.play_revision -eq 'r7' -and $result.data.region_id -eq 'overworld') {
            Write-Host "READY: R9-compatible service on http://127.0.0.1:$p" -ForegroundColor Green
            $found = $true
        } else { Write-Host "Port ${p}: responded, but wrong or incompatible service." -ForegroundColor Yellow }
    } catch {
        if ($p -eq $Port) { Write-Host "Port ${p}: no healthy service ($($_.Exception.Message))" -ForegroundColor Yellow }
    }
}
if (-not $found) { Write-Host 'NO COMPATIBLE BACKEND FOUND. Start with Start_Game.bat.' -ForegroundColor Red }
$logs = @('runtime\backend.stderr.log','runtime\backend.stdout.log','runtime\backend.log','runtime\godot.log','runtime\godot-import.log')
foreach ($rel in $logs) {
    $f = Join-Path $root $rel
    if (Test-Path -LiteralPath $f) {
        Write-Host "--- $rel (last 15 lines) ---" -ForegroundColor Cyan
        Get-Content -LiteralPath $f -Tail 15 | ForEach-Object { Write-Host $_ }
    }
}
