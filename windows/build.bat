@echo off
rem Runs windows\build.ps1 with a process-scoped execution policy bypass. No administrator rights needed.
rem Prefers PowerShell 7 (pwsh) and falls back to Windows PowerShell 5.1. Propagates the exit code.
setlocal EnableExtensions

set "PS_EXE=pwsh"
where pwsh >nul 2>&1 || set "PS_EXE=powershell"

"%PS_EXE%" -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%~dp0build.ps1" %*
set "RC=%ERRORLEVEL%"
endlocal & exit /b %RC%
