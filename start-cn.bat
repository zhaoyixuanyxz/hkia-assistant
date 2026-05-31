@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo ========================================
echo   HKIA Start - Mainland China
echo   docker.cn.env ^(mirror^)
echo ========================================
echo.
call "%~dp0scripts\hkia_start.bat" cn "%~dp0"
set "ERR=%ERRORLEVEL%"
if not "%ERR%"=="0" (
  echo.
  echo [error] Startup failed with code %ERR%.
  pause
)
exit /b %ERR%
