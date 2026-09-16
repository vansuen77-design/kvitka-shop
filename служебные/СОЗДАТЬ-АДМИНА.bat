@echo off
chcp 65001 >nul
title KVITKA - создание администратора
rem Батник лежит в подпапке, а проект уровнем выше — поэтому «..».
rem Без этой строки Python и manage.py искались бы здесь и не нашлись.
cd /d "%~dp0.."

set "VPY=.venv\Scripts\python.exe"
if not exist "%VPY%" (
    echo [X] Сначала запустите ЗАПУСТИТЬ.bat - он создаст окружение.
    pause
    exit /b 1
)

"%VPY%" -c "import django,os;os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings');django.setup();from django.contrib.auth import get_user_model;raise SystemExit(1 if get_user_model().objects.filter(is_superuser=True,is_active=True).exists() else 0)" 2>nul
if errorlevel 1 (
    echo [X] Администратор уже создан - он в проекте только один.
    echo     Забыли пароль? Смените его командой:
    echo     "%VPY%" manage.py changepassword ИМЯ
    echo.
    pause
    exit /b 0
)

echo Создание учётной записи для входа в админку.
echo Пароль вводится вслепую - символы не отображаются, это нормально.
echo.
"%VPY%" manage.py createsuperuser
echo.
pause
