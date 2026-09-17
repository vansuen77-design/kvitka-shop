@echo off
chcp 65001 >nul
title KVITKA - local copy for editing (port 8001)
cd /d "%~dp0"

echo.
echo ==========================================
echo   KVITKA - LOCAL COPY FOR EDITING
echo ==========================================
echo.
echo   This is NOT the live site. Break anything you like here:
echo   the live site on the server is not affected.
echo.
echo   Local copy: http://127.0.0.1:8001/
echo   Live site:  https://kvitka.example/  (on the server)
echo.

rem --- Python: the project's own .venv -----------------------------------
set "VPY=.venv\Scripts\python.exe"
if not exist "%VPY%" (
    echo [X] Python not found.
    echo     The virtual environment is missing. Recreate it:
    echo         python -m venv .venv
    echo         .venv\Scripts\python.exe -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

echo [0/3] Checking dependencies...
"%VPY%" -c "import django, PIL, waitress, whitenoise" 2>nul
if errorlevel 1 (
    echo       Something is missing, installing...
    "%VPY%" -m pip install -q -r requirements.txt
    if errorlevel 1 goto :error
)

echo [1/3] Compiling translations...
"%VPY%" manage.py compilelocales
if errorlevel 1 goto :error

echo [2/3] Checking and applying migrations...
rem Migrations are created by the developer and shipped with the code.
rem Here we only check: if this fails, code and migrations have diverged.
"%VPY%" manage.py makemigrations --check --dry-run
if errorlevel 1 goto :error
"%VPY%" manage.py migrate --noinput
if errorlevel 1 goto :error
"%VPY%" manage.py seed_facets
if errorlevel 1 goto :error

echo [3/3] Starting the local copy...
echo.
echo   Catalog: http://127.0.0.1:8001/
echo   Admin:   http://127.0.0.1:8001/admin/
echo.
echo   To stop - close this window.
echo.

start "" http://127.0.0.1:8001/
"%VPY%" manage.py runserver 127.0.0.1:8001

goto :end

:error
echo.
echo [X] Something went wrong - see the message above.
echo.
pause
exit /b 1

:end
echo.
echo Local copy stopped.
pause
