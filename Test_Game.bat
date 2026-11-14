@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0release\test_game.ps1" %*
if errorlevel 1 (echo. & echo Failed. Read the message above and runtime logs.)
pause
