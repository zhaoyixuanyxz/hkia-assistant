@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ========================================
echo   HKIA Docker Startup
echo ========================================
echo.
echo   1 = Mainland China  ^(docker.cn.env^)
echo   2 = Overseas / HK / Macao  ^(docker.intl.env^)
echo   Q = Quit
echo.
set /p "HKIA_PICK=Choose region [1/2/Q]: "
if /i "%HKIA_PICK%"=="Q" exit /b 0
if "%HKIA_PICK%"=="1" (
  call "%~dp0scripts\hkia_start.bat" cn "%~dp0"
  goto AFTER_START
)
if "%HKIA_PICK%"=="2" (
  call "%~dp0scripts\hkia_start.bat" intl "%~dp0"
  goto AFTER_START
)
echo [error] Invalid choice. Enter 1, 2, or Q.
pause
exit /b 1

:AFTER_START
set "ERR=%ERRORLEVEL%"
if not "%ERR%"=="0" (
  echo.
  echo [error] Startup failed with code %ERR%.
  pause
)
exit /b %ERR%
