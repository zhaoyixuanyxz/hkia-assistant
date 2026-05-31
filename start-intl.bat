@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo ========================================
echo   HKIA Start - Overseas / HK / Macao
echo   docker.intl.env ^(Docker Hub^)
echo ========================================
echo.
call "%~dp0scripts\hkia_start.bat" intl "%~dp0"
set "ERR=%ERRORLEVEL%"
if not "%ERR%"=="0" (
  echo.
  echo [error] Startup failed with code %ERR%.
  pause
)
exit /b %ERR%
