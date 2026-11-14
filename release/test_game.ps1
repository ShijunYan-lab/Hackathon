param([string]$GodotPath = '')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw 'Run Setup_Game.bat first.' }
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
$env:LLM_API_KEY = ''
$env:WORLD_MODEL_API_KEY = ''
& $python -m compileall -q server shared
if ($LASTEXITCODE -ne 0) { throw 'Python compilation failed.' }
& $python -m pytest tests -q
if ($LASTEXITCODE -ne 0) { throw 'Tests failed. Stop here; do not publish this build.' }
& $python -m tools.check_client_resources
if ($LASTEXITCODE -ne 0) { throw 'Game resource checks failed.' }
& $python -m tools.check_contracts
if ($LASTEXITCODE -ne 0) { throw 'Protocol examples failed.' }
& $python -m tools.check_evaluation_contracts
if ($LASTEXITCODE -ne 0) { throw 'Evaluation examples failed.' }
if (-not $GodotPath -and (Test-Path 'runtime/godot-path.txt')) { $GodotPath = (Get-Content 'runtime/godot-path.txt' -Raw).Trim() }
if (-not $GodotPath) { Write-Warning 'Python tests passed. Godot was NOT checked. Rerun with -GodotPath or launch Start_Game.bat and perform the manual checklist.'; exit 0 }
if (-not (Test-Path -LiteralPath $GodotPath)) { throw 'GodotPath does not exist.' }
New-Item -ItemType Directory -Path 'runtime' -Force | Out-Null
& $GodotPath --headless --path (Join-Path $root 'game') --import --log-file (Join-Path $root 'runtime/godot-import.log')
if ($LASTEXITCODE -ne 0 -or (Select-String -Path 'runtime/godot-import.log' -Pattern 'SCRIPT ERROR|Parse Error|Failed to load script' -Quiet)) { throw 'Godot resource import or GDScript check failed. Read runtime/godot-import.log.' }
& $GodotPath --headless --path (Join-Path $root 'game') --script res://tests/r6_client_smoke.gd --log-file (Join-Path $root 'runtime/godot-smoke.log')
if ($LASTEXITCODE -ne 0 -or (Select-String -Path 'runtime/godot-smoke.log' -Pattern 'SCRIPT ERROR|Parse Error|Failed to load script' -Quiet)) { throw 'Client smoke test failed. Read runtime/godot-smoke.log.' }
Write-Host 'Local tests passed. Real API and visual gameplay still require the manual checklist.' -ForegroundColor Green
