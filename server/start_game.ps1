param([string]$GodotPath = '')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
if (-not $GodotPath) {
    $command = Get-Command godot -ErrorAction SilentlyContinue
    if ($command) { $GodotPath = $command.Source }
    else {
        $GodotPath = Get-ChildItem (Join-Path $env:USERPROFILE 'Downloads/Godot*') -File -Filter 'Godot*_win64.exe' -Recurse -ErrorAction SilentlyContinue |
            Select-Object -First 1 -ExpandProperty FullName
    }
}
if (-not $GodotPath -or -not (Test-Path -LiteralPath $GodotPath)) {
    throw 'Godot not found. Run with -GodotPath pointing to your Godot 4.5.2 executable.'
}
if (-not (Test-Path 'runtime/venv311/Scripts/python.exe')) { throw 'Missing runtime/venv311 Python environment.' }
try { $health = Invoke-RestMethod 'http://127.0.0.1:8765/health' -TimeoutSec 2 } catch { $health = $null }
if (-not $health) {
    if (-not (Test-Path 'runtime/director-key.dpapi')) { throw 'Missing local encrypted model credential: runtime/director-key.dpapi.' }
    $backend = Start-Process powershell.exe -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + (Join-Path $PSScriptRoot 'start_world_model.ps1') + '"'), '-Integrated', '-NpcDemo') -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput "$root/runtime/game-backend.stdout.log" -RedirectStandardError "$root/runtime/game-backend.stderr.log"
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        Start-Sleep -Seconds 1
        try { $health = Invoke-RestMethod 'http://127.0.0.1:8765/health' -TimeoutSec 2; break } catch {}
        if ($backend.HasExited) { throw 'Backend exited. Check runtime/game-backend.stderr.log.' }
    }
    if (-not $health) { throw 'Backend not ready. Check runtime/game-backend.stderr.log.' }
}
if ($health.data.region_id -ne 'overworld' -or $health.data.map_width_tiles -ne 320) {
    throw 'Port 8765 belongs to another map service. Close that service first; no processes were terminated.'
}
Start-Process -FilePath $GodotPath -ArgumentList @('--path', ('"' + (Join-Path $root 'game') + '"'), '--log-file', ('"' + (Join-Path $root 'runtime/game-play.log') + '"')) -WorkingDirectory $root | Out-Null
Write-Host 'Game launched. API: http://127.0.0.1:8765/docs'
Write-Host 'The backend stays running after the game closes. Saves: runtime/overworld.sqlite3'
