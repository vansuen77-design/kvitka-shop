@echo off
chcp 65001 >nul
title KVITKA - create administrator
rem This script lives in a subfolder, the project is one level up - hence "..".
rem Without this line Python and manage.py would be looked up here and not found.
cd /d "%~dp0.."

set "VPY=.venv\Scripts\python.exe"
if not exist "%VPY%" (
    echo [X] Run start.bat first - it creates the environment.
    pause
    exit /b 1
)

"%VPY%" -c "import django,os;os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings');django.setup();from django.contrib.auth import get_user_model;raise SystemExit(1 if get_user_model().objects.filter(is_superuser=True,is_active=True).exists() else 0)" 2>nul
if errorlevel 1 (
    echo [X] The administrator already exists - the project has exactly one.
    echo     Forgot the password? Change it with:
    echo     "%VPY%" manage.py changepassword USERNAME
    echo.
    pause
    exit /b 0
)

echo Creating the account for the admin panel.
echo The password is typed blind - characters are not shown, that is normal.
echo.
"%VPY%" manage.py createsuperuser
echo.
pause
