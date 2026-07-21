@echo off
setlocal EnableExtensions EnableDelayedExpansion
REM HKIA Docker startup. Args: hkia_start.bat cn|intl "repo_root"
REM cn   = mainland China  -> docker.cn.env
REM intl = overseas/HK/MO -> docker.intl.env

set "HKIA_REGION=%~1"
if /i not "%HKIA_REGION%"=="cn" if /i not "%HKIA_REGION%"=="intl" (
  echo [error] Usage: hkia_start.bat cn^|intl repo_root
  pause
  exit /b 1
)

set "ROOT=%~2"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

set "DOCKER_OK=0"
where docker >nul 2>&1
if errorlevel 1 goto DOCKER_MISSING

docker info >nul 2>&1
if not errorlevel 1 set "DOCKER_OK=1"

if "!DOCKER_OK!"=="0" (
  echo [start] Docker engine not ready. Starting Docker Desktop...
  set "DOCKER_DESKTOP_STARTED=0"
  if exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" (
    start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
    set "DOCKER_DESKTOP_STARTED=1"
  ) else if exist "%ProgramFiles(x86)%\Docker\Docker\Docker Desktop.exe" (
    start "" "%ProgramFiles(x86)%\Docker\Docker\Docker Desktop.exe"
    set "DOCKER_DESKTOP_STARTED=1"
  )
  if "!DOCKER_DESKTOP_STARTED!"=="0" (
    echo [error] docker is in PATH but Docker Desktop.exe was not found.
    echo Install from https://www.docker.com/products/docker-desktop/
    pause
    exit /b 1
  )
  echo [start] Waiting for Docker ^(first launch may take 1-3 min^)...
)

set "_TRY=0"
:WAIT_DOCKER
docker info >nul 2>&1
if not errorlevel 1 goto DOCKER_READY
set /a _TRY+=1
if !_TRY! GEQ 180 (
  echo [error] Docker did not become ready in time. Open Docker Desktop manually, then run again.
  pause
  exit /b 1
)
timeout /t 2 /nobreak >nul
goto WAIT_DOCKER

:DOCKER_READY
set "COMPOSE_FILE=%ROOT%\docker-compose.yml"

if /i "%HKIA_REGION%"=="cn" (
  set "COMPOSE_ENV=%ROOT%\docker.cn.env"
  set "PULL_SCRIPT=%ROOT%\scripts\pull_docker_images_cn.ps1"
  set "REGION_LABEL=Mainland China"
) else (
  set "COMPOSE_ENV=%ROOT%\docker.intl.env"
  set "PULL_SCRIPT=%ROOT%\scripts\pull_docker_images_intl.ps1"
  set "REGION_LABEL=Overseas / HK / Macao"
)

if not exist "%COMPOSE_ENV%" (
  echo [error] Missing env file: %COMPOSE_ENV%
  pause
  exit /b 1
)

echo [start] Region: !REGION_LABEL!
echo [start] Docker env: %COMPOSE_ENV%
echo [start] Pre-pulling base images ^(first run may take several minutes^)...
powershell -NoProfile -ExecutionPolicy Bypass -File "%PULL_SCRIPT%"
if errorlevel 1 (
  echo [warn] Pre-pull had issues; continuing with compose build anyway...
)

set "DOTENV=%ROOT%\.env"
if not exist "%DOTENV%" (
  echo [error] Missing secrets file: %DOTENV%
  echo Copy .env.example to .env and set DEEPSEEK_API_KEY / JWT_SECRET first.
  pause
  exit /b 1
)

REM Region file first (image mirrors), then .env so DEEPSEEK_API_KEY and secrets win.
echo [start] docker compose up -d --build ...
echo [start] Env: %COMPOSE_ENV% + %DOTENV%
docker compose -f "%COMPOSE_FILE%" --env-file "%COMPOSE_ENV%" --env-file "%DOTENV%" --project-directory "%ROOT%." up -d --build
if errorlevel 1 (
  echo [error] docker compose failed.
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "$u='http://127.0.0.1:3000/';$d=(Get-Date).AddSeconds(240);while((Get-Date) -lt $d){try{Invoke-WebRequest -Uri $u -UseBasicParsing -TimeoutSec 3|Out-Null;exit 0}catch{Start-Sleep -Seconds 2}};exit 1"
if errorlevel 1 (
  echo [warn] Frontend not responding yet. Browser will open anyway - refresh if needed.
)

set "RUN_DIR=%TEMP%\hkia-phase3-run"
if not exist "%RUN_DIR%" mkdir "%RUN_DIR%" >nul 2>&1
set "BROWSER_PROFILE=%RUN_DIR%\browser-profile"
set "PID_FILE=%RUN_DIR%\browser.pid"

set "CHROME_EXE="
for %%C in ("%ProgramFiles%\Google\Chrome\Application\chrome.exe" "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" "%LocalAppData%\Google\Chrome\Application\chrome.exe") do if not defined CHROME_EXE if exist "%%~C" set "CHROME_EXE=%%~C"
set "EDGE_EXE="
for %%E in ("%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe") do if not defined EDGE_EXE if exist "%%~E" set "EDGE_EXE=%%~E"

if defined CHROME_EXE (
  set "HKIA_BROWSER_EXE=%CHROME_EXE%"
  set "HKIA_BROWSER_PROFILE=%BROWSER_PROFILE%"
  set "HKIA_PID_FILE=%PID_FILE%"
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$e=$env:HKIA_BROWSER_EXE;$p=$env:HKIA_BROWSER_PROFILE;$f=$env:HKIA_PID_FILE;$a=@('--app=http://localhost:3000',('--user-data-dir='+$p),'--disable-features=IsolateOrigins,site-per-process');$pr=Start-Process -FilePath $e -ArgumentList $a -PassThru -WindowStyle Normal;$pr.Id|Out-File -FilePath $f -Encoding ascii -NoNewline"
  set "HKIA_BROWSER_EXE="
  set "HKIA_BROWSER_PROFILE="
  set "HKIA_PID_FILE="
  goto DONE_BROWSER
)

if defined EDGE_EXE (
  set "HKIA_BROWSER_EXE=%EDGE_EXE%"
  set "HKIA_BROWSER_PROFILE=%BROWSER_PROFILE%"
  set "HKIA_PID_FILE=%PID_FILE%"
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$e=$env:HKIA_BROWSER_EXE;$p=$env:HKIA_BROWSER_PROFILE;$f=$env:HKIA_PID_FILE;$a=@('--app=http://localhost:3000',('--user-data-dir='+$p));$pr=Start-Process -FilePath $e -ArgumentList $a -PassThru -WindowStyle Normal;$pr.Id|Out-File -FilePath $f -Encoding ascii -NoNewline"
  set "HKIA_BROWSER_EXE="
  set "HKIA_BROWSER_PROFILE="
  set "HKIA_PID_FILE="
  goto DONE_BROWSER
)

echo [note] Chrome/Edge not found. Using default browser.
start "" "http://localhost:3000/"

:DONE_BROWSER
echo [start] Done. UI: http://localhost:3000/  API: http://localhost:8000/
echo.
echo Press any key to close this window. ^(Docker services keep running.^)
pause
exit /b 0

:DOCKER_MISSING
echo [error] docker was not found in PATH. Install Docker Desktop.
echo https://www.docker.com/products/docker-desktop/
pause
exit /b 1
