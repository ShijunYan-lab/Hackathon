param([int]$Port = 8765, [switch]$DebugViews)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$credentialPath = Join-Path (Get-Location) 'runtime/director-key.dpapi'
if (!(Test-Path -LiteralPath $credentialPath)) { throw 'Configure runtime/director-key.dpapi using Read-Host -AsSecureString first.' }
$secureKey = Get-Content -LiteralPath $credentialPath | ConvertTo-SecureString
$env:WORLD_MODEL_API_KEY = [System.Net.NetworkCredential]::new('', $secureKey).Password
$env:WORLD_MODEL_BASE_URL = 'https://api.deepseek.com'
$env:WORLD_MODEL_NAME = 'deepseek-flash'
if ($DebugViews) { $env:ALLOW_DEBUG = 'true' }
try { & 'runtime/venv311/Scripts/python.exe' -m server.launch --port $Port }
finally { Remove-Item Env:WORLD_MODEL_API_KEY -ErrorAction SilentlyContinue }
