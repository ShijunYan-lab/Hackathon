param([string]$StatusPath = '')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Write-GameSetupStatus([string]$Status, [string]$Message) {
    if (-not $StatusPath) { return }
    $statusDir = Split-Path -Parent $StatusPath
    if (-not (Test-Path -LiteralPath $statusDir)) {
        New-Item -ItemType Directory -Path $statusDir -Force | Out-Null
    }
    $payload = @{ status = $Status; message = $Message } | ConvertTo-Json -Compress
    [System.IO.File]::WriteAllText($StatusPath, $payload, (New-Object System.Text.UTF8Encoding $false))
}

try {
    if (Test-Path '.runtime\python\python.exe') {
        $env:PYTHONHOME = (Resolve-Path '.runtime\python').Path
        & '.\.runtime\python\python.exe' -m pip check
        if ($LASTEXITCODE -ne 0) { throw 'Bundled dependencies failed verification.' }
        Write-GameSetupStatus 'ready' 'The bundled Python runtime is available.'
        Write-Host 'Bundled runtime is ready. Run Start_Game.bat.' -ForegroundColor Green
        return
    }
    $python = Join-Path $root '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) {
        $py = Get-Command py -ErrorAction SilentlyContinue
        $base = Get-Command python -ErrorAction SilentlyContinue
        if ($py) {
            & py -3.11 -m venv .venv
            if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 not found. Install Python 3.11 or use a compatible interpreter.' }
        } elseif ($base) {
            & python -m venv .venv
            if ($LASTEXITCODE -ne 0) { throw 'Cannot create .venv; activate Python 3.11 and try again.' }
        } else {
            throw 'Python not found. Install Python 3.11 and rerun setup.'
        }
    }
    & $python -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed; check internet connection and retry.' }
    & $python -m pip check
    if ($LASTEXITCODE -ne 0) { throw 'Dependency verification failed.' }
    # The marker is written ONLY after the dependency check succeeds. Godot
    # must not start a half-created .venv during pip installation.
    Write-GameSetupStatus 'ready' 'The local Python environment is ready.'
    Write-Host 'Setup complete. You can start the game.' -ForegroundColor Green
} catch {
    $reason = $_.Exception.Message
    Write-GameSetupStatus 'failed' $reason
    Write-Error $reason
    exit 1
}
