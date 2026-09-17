@echo off
chcp 65001 >nul
title KVITKA - checks before deploying
rem This script lives in a subfolder, the project is one level up - hence "..".
cd /d "%~dp0.."

set "VPY=.venv\Scripts\python.exe"
if not exist "%VPY%" (
    echo [X] Run start.bat first - it creates the environment.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo   CHECKS BEFORE DEPLOYING TO THE SERVER
echo ==========================================
echo.

echo [1/5] Settings check (manage.py check)...
"%VPY%" manage.py check
if errorlevel 1 goto :error

echo [2/5] Migrations match the models...
"%VPY%" manage.py makemigrations --check --dry-run
if errorlevel 1 goto :error

echo [3/5] All UI strings are translated to Ukrainian...
"%VPY%" manage.py makelocales --check
if errorlevel 1 goto :error

echo [4/5] Compiling translations...
"%VPY%" manage.py compilelocales
if errorlevel 1 goto :error

echo [5/5] Tests (a couple of minutes)...
"%VPY%" manage.py test --noinput
if errorlevel 1 goto :error

echo.
echo ==========================================
echo   ALL GREEN - safe to deploy
echo ==========================================
echo.
pause
exit /b 0

:error
echo.
echo [X] Check failed - see the message above.
echo     Better not to deploy until it is fixed.
echo.
pause
exit /b 1
