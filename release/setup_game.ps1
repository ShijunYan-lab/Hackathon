$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$python = Join-Path (Get-Location) '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    $py = Get-Command py -ErrorAction SilentlyContinue
    $base = Get-Command python -ErrorAction SilentlyContinue
    if ($py) { & py -3.11 -m venv .venv; if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 was not found. Install Python 3.11, or activate your Conda environment and run: python -m venv .venv' } }
    elseif ($base) { & python -m venv .venv; if ($LASTEXITCODE -ne 0) { throw 'Cannot create .venv. Activate Python 3.11 and try again.' } }
    else { throw 'Python was not found. Install Python 3.11 and rerun Setup_Game.bat.' }
}
& $python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check the network and retry; existing development environments were not modified.' }
& $python -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Dependency compatibility check failed.' }
Write-Host 'Setup complete. Run Start_Game.bat. The first run will ask for your Godot 4.5.2 executable.' -ForegroundColor Green
