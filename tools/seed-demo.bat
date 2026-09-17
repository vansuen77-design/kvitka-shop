@echo off
chcp 65001 >nul
title KVITKA - demo catalog
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
echo   DEMO CATALOG
echo ==========================================
echo.
echo   Creates statuses, categories, filter attributes, footer pages
echo   and 15 bouquets with placeholder images.
echo   Existing records are not touched: safe to run again.
echo.
choice /c YN /m "Seed"
if errorlevel 2 goto :cancel

echo.
"%VPY%" manage.py migrate --noinput
if errorlevel 1 goto :error
"%VPY%" manage.py compilelocales
if errorlevel 1 goto :error
"%VPY%" manage.py seed_facets
if errorlevel 1 goto :error
"%VPY%" manage.py seed_pages
if errorlevel 1 goto :error
"%VPY%" manage.py seed_catalog
if errorlevel 1 goto :error

echo.
echo Done. Run start.bat and open the catalog.
echo Replace placeholder images with your photos in the admin: Products - photos.
echo.
pause
exit /b 0

:cancel
echo Cancelled.
pause
exit /b 0

:error
echo.
echo [X] Failed - see the message above.
echo.
pause
exit /b 1
