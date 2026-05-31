@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set "PID_FILE=%TEMP%\hkia-phase3-run\browser.pid"
set "BPID="

if exist "%PID_FILE%" (
  for /f "usebackq delims=" %%P in ("%PID_FILE%") do set "BPID=%%P"
)

if defined BPID (
  echo [stop] Ending browser instance PID !BPID! ...
  taskkill /PID !BPID! /T /F >nul 2>&1
)

if exist "%PID_FILE%" del "%PID_FILE%" >nul 2>&1

where docker >nul 2>&1
if errorlevel 1 (
  echo [note] docker not in PATH. Skipping compose down.
  goto :END_COMPOSE
)

echo [stop] docker compose down ...
docker compose -f "%~dp0docker-compose.yml" --project-directory "%~dp0." down
if errorlevel 1 (
  echo [note] docker compose down returned an error ^(e.g. Docker Desktop already closed^).
)

:END_COMPOSE
echo [stop] Finished.
echo.
echo Press any key to close this window.
pause
exit /b 0
