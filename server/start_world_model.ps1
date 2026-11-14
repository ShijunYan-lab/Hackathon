param(
    [int]$Port = 8765,
    [switch]$DebugViews,
    [switch]$NpcDemo,
    [switch]$Integrated,
    [string]$Db
)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$credentialPath = Join-Path (Get-Location) 'runtime/director-key.dpapi'
if (!(Test-Path -LiteralPath $credentialPath)) { throw 'Configure runtime/director-key.dpapi using Read-Host -AsSecureString first.' }
if ($Integrated -and !(Test-Path -LiteralPath 'release/run_backend.py')) {
    throw 'The integrated backend is available on main.'
}
$secureKey = Get-Content -LiteralPath $credentialPath | ConvertTo-SecureString
$env:WORLD_MODEL_API_KEY = [System.Net.NetworkCredential]::new('', $secureKey).Password
$env:WORLD_MODEL_BASE_URL = 'https://api.deepseek.com'
$env:WORLD_MODEL_NAME = 'deepseek-flash'
if ($NpcDemo) { $env:WORLD_NPC_MODEL_DEMO = 'true' }
if ($DebugViews) { $env:ALLOW_DEBUG = 'true' }
$serverArgs = @('--port', $Port)
if ($Db) { $serverArgs += @('--db', $Db) }
$useSharedModel = $Integrated -and $NpcDemo
$previousNpcModel = @{}
if ($useSharedModel) {
    foreach ($name in @('LLM_API_KEY', 'LLM_BASE_URL', 'LLM_MODEL')) {
        $previousNpcModel[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
    }
    $env:LLM_API_KEY = $env:WORLD_MODEL_API_KEY
    $env:LLM_BASE_URL = $env:WORLD_MODEL_BASE_URL
    $env:LLM_MODEL = $env:WORLD_MODEL_NAME
}
try {
    if ($Integrated) { & 'runtime/venv311/Scripts/python.exe' 'release/run_backend.py' @serverArgs }
    else { & 'runtime/venv311/Scripts/python.exe' -m server.launch @serverArgs }
}
finally {
    Remove-Item Env:WORLD_MODEL_API_KEY -ErrorAction SilentlyContinue
    foreach ($name in $previousNpcModel.Keys) {
        [Environment]::SetEnvironmentVariable($name, $previousNpcModel[$name], 'Process')
    }
}
