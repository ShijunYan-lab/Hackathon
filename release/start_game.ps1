param([string]$GodotPath = '')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw '请先运行 python -m venv .venv，然后用 .venv\Scripts\python.exe -m pip install -r requirements.txt 安装依赖。'
}
if (-not $GodotPath) {
    $GodotPath = 'D:\godot\Godot_v4.5.2-stable_win64.exe\Godot_v4.5.2-stable_win64.exe\Godot_v4.5.2-stable_win64_console.exe'
}
if (-not (Test-Path -LiteralPath $GodotPath)) { throw '请通过 -GodotPath 指定 Godot 4.5.2 可执行文件。' }
$runtimePath = Join-Path $projectRoot 'runtime'
New-Item -ItemType Directory -Path $runtimePath -Force | Out-Null
try { $health = Invoke-RestMethod 'http://127.0.0.1:8765/health' -TimeoutSec 2 } catch { $health = $null }
if (-not $health) {
    Start-Process -FilePath $pythonPath -ArgumentList @('release/run_backend.py') -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtimePath 'backend.stdout.log') -RedirectStandardError (Join-Path $runtimePath 'backend.stderr.log') | Out-Null
} elseif ($health.data.region_id -ne 'overworld' -or $health.data.map_width_tiles -ne 320) {
    throw '8765 端口已有其他地图服务。请先在原终端关闭该服务，再运行此脚本。不会终止其他进程或覆盖旧世界。'
}
# The game window is the interactive application explicitly requested by the user.
Start-Process -FilePath $GodotPath -ArgumentList @('--path', ('"' + (Join-Path $projectRoot 'game') + '"')) -WorkingDirectory $projectRoot | Out-Null
