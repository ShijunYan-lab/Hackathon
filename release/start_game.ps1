param([string]$GodotPath = '', [switch]$DebugUI, [int]$Port = 8765, [int]$SmokeFrames = 0)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$python = Join-Path $root '.venv\Scripts\python.exe'
$portable = Join-Path $root '.runtime\python\python.exe'
if (Test-Path -LiteralPath $portable) { $python = $portable; $env:PYTHONHOME = Split-Path -Parent $portable }
if (-not (Test-Path -LiteralPath $python)) {
    Write-Host 'No local Python runtime found. Preparing this game environment...' -ForegroundColor Yellow
    & (Join-Path $PSScriptRoot 'setup_game.ps1')
    if ($LASTEXITCODE -ne 0) { throw 'Automatic setup failed. See the setup error above.' }
    # The setup script creates a local virtual environment, not a global one.
    if (Test-Path -LiteralPath $portable) { $python = $portable; $env:PYTHONHOME = Split-Path -Parent $portable }
    else { $python = Join-Path $root '.venv\Scripts\python.exe' }
    if (-not (Test-Path -LiteralPath $python)) { throw 'Python runtime is still missing after setup.' }
}
$runtime = Join-Path $root 'runtime'
New-Item -ItemType Directory -Path $runtime -Force | Out-Null
$pathFile = Join-Path $runtime 'godot-path.txt'
if (-not $GodotPath -and (Test-Path (Join-Path $root '.runtime\godot\Godot_v4.5.2-stable_win64.exe'))) { $GodotPath = Join-Path $root '.runtime\godot\Godot_v4.5.2-stable_win64.exe' }
if (-not $GodotPath -and $env:GODOT_PATH) { $GodotPath = $env:GODOT_PATH }
if (-not $GodotPath -and (Test-Path $pathFile)) { $GodotPath = (Get-Content $pathFile -Raw).Trim() }
if (-not $GodotPath) {
    foreach ($name in @('godot', 'godot4')) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($command) { $GodotPath = $command.Source; break }
    }
}
if (-not $GodotPath -or -not (Test-Path -LiteralPath $GodotPath)) {
    Add-Type -AssemblyName System.Windows.Forms
    $picker = New-Object System.Windows.Forms.OpenFileDialog
    $picker.Title = 'Select Godot 4.5.2 Standard executable (not the project.godot file)'
    $picker.Filter = 'Godot executable (*.exe)|*.exe'
    if ($picker.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) { throw 'No Godot executable was selected.' }
    $GodotPath = $picker.FileName
}
$GodotPath = (Resolve-Path -LiteralPath $GodotPath).Path
$GodotPath | Set-Content -LiteralPath $pathFile -Encoding UTF8
# Import and parse resources before launching the interactive scene.
$importLog = Join-Path $runtime 'godot-import.log'
$importArgs = @('--headless', '--import', '--path', ('"' + (Join-Path $root 'game') + '"'), '--log-file', ('"' + $importLog + '"'))
$importJob = Start-Process -FilePath $GodotPath -ArgumentList $importArgs -WorkingDirectory $root -PassThru -Wait -WindowStyle Hidden
if ($importJob.ExitCode -ne 0 -or ((Test-Path $importLog) -and (Select-String -Path $importLog -Pattern 'SCRIPT ERROR|Parse Error|Failed to load script' -Quiet))) {
    throw 'Godot import/parse check failed. Read runtime/godot-import.log before running or publishing.'
}
function Test-AvailablePort([int]$Number) {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Number)
    try { $listener.Start(); return $true } catch { return $false } finally { $listener.Stop() }
}
$healthUrl = "http://127.0.0.1:$Port/health"
try { $health = Invoke-RestMethod $healthUrl -TimeoutSec 2 } catch { $health = $null }
$compatible = $health -and $health.ok -and $health.data.play_revision -eq 'r7' -and $health.data.region_id -eq 'overworld' -and $health.data.map_width_tiles -eq 320
if (-not $compatible) {
    $health = $null
    if (-not (Test-AvailablePort $Port)) {
        $found = $false
        foreach ($candidate in 8766..8865) {
            if (Test-AvailablePort $candidate) { $Port = $candidate; $found = $true; break }
        }
        if (-not $found) { throw 'No free local port is available for this game.' }
        Write-Host "Starting this version on free local port $Port. The existing service is left running."
    }
    $healthUrl = "http://127.0.0.1:$Port/health"
}
$owned = $null
try {
    if (-not $health) {
        $owned = Start-Process -FilePath $python -ArgumentList @('-u', 'release/run_backend.py', '--db', 'runtime/playable-r7.sqlite3', '--port', $Port) -WorkingDirectory $root -PassThru -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtime 'backend.stdout.log') -RedirectStandardError (Join-Path $runtime 'backend.stderr.log')
        for ($i=0; $i -lt 40; $i++) {
            if ($owned.HasExited) { throw 'Backend exited. Read runtime/backend.stderr.log.' }
            Start-Sleep -Milliseconds 500
            try { $health = Invoke-RestMethod $healthUrl -TimeoutSec 2; if ($health.ok) { break } } catch {}
        }
    }
    if (-not $health -or -not $health.ok) { throw 'Backend health check failed. Read runtime/backend.stderr.log.' }
    if ($health.data.play_revision -ne 'r7' -or $health.data.region_id -ne 'overworld' -or $health.data.map_width_tiles -ne 320) {
        throw "The service on port $Port is not this game version. No unrelated process has been killed."
    }
    $arguments = @('--path', ('"' + (Join-Path $root 'game') + '"'), '--log-file', ('"' + (Join-Path $runtime 'godot.log') + '"'))
    if ($SmokeFrames -gt 0) { $arguments += @('--quit-after', $SmokeFrames) }
    $arguments += @('--', "--server=http://127.0.0.1:$Port")
    if ($DebugUI) { $arguments += '--debug-ui' }
    $game = Start-Process -FilePath $GodotPath -ArgumentList $arguments -WorkingDirectory $root -PassThru
    $game.WaitForExit()
    if ($game.ExitCode -ne 0) { throw 'Godot exited with an error. Read runtime/godot.log.' }
} finally {
    if ($owned -and -not $owned.HasExited) { Stop-Process -Id $owned.Id -ErrorAction SilentlyContinue }
}
