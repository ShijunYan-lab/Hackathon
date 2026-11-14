param([string]$GodotPath = '', [switch]$Replay)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
Set-Location $root
if (-not $GodotPath) {
    $GodotPath=Get-ChildItem (Join-Path $env:USERPROFILE 'Downloads/Godot*') -File -Filter 'Godot*_win64.exe' -Recurse | Select-Object -First 1 -ExpandProperty FullName
}
if (-not $GodotPath -or -not (Test-Path -LiteralPath $GodotPath)) { throw 'Specify -GodotPath.' }
try { $health=Invoke-RestMethod 'http://127.0.0.1:8781/health' -TimeoutSec 2 } catch { $health=$null }
if (-not $health) {
    $previous=$env:PSModulePath
    try {
        $env:PSModulePath="$env:WINDIR\System32\WindowsPowerShell\v1.0\Modules"
        Start-Process powershell.exe -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',('"'+$root+'/server/start_world_model.ps1"'),'-Integrated','-NpcDemo','-DebugViews','-Port','8781','-Db','runtime/generative-live.sqlite3') -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput "$root/runtime/generative.stdout.log" -RedirectStandardError "$root/runtime/generative.stderr.log" | Out-Null
    } finally { $env:PSModulePath=$previous }
    for ($i=0;$i -lt 30;$i++) {
        Start-Sleep -Seconds 1
        try { $health=Invoke-RestMethod 'http://127.0.0.1:8781/health' -TimeoutSec 2; break } catch {}
    }
}
if (-not $health -or $health.data.region_id -ne 'overworld') { throw 'Integrated backend unavailable on 8781.' }
if ($Replay -or -not (Test-Path 'runtime/generative-session.json')) {
    & runtime/venv311/Scripts/python.exe -m server.api.generative_live_demo --godot $GodotPath
} else {
    $session=Get-Content runtime/generative-session.json -Raw -Encoding UTF8 | ConvertFrom-Json
    $existing = Get-CimInstance Win32_Process | Where-Object {
        $_.Name -like 'Godot*' -and $_.CommandLine -like '*generative_demo.gd*' -and
        $_.CommandLine -like ('*--world=' + $session.world_id + '*')
    }
    if ($existing) {
        Write-Host 'This world is already open. Use the existing experimental game window.'
        return
    }
    Start-Process $GodotPath -ArgumentList @('--path',('"'+$root+'/game"'),'--script',('"'+$root+'/server/api/generative_demo.gd"'),'--','--no-autostart','--fresh','--server=http://127.0.0.1:8781',('--world='+$session.world_id)) -WorkingDirectory $root | Out-Null
    Write-Host 'Opened experimental world. E: dialogue; Tab: items and offers; J: chronicle.'
}
