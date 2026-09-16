@echo off
chcp 65001 >nul
title KVITKA - проверка перед отправкой
rem Батник лежит в подпапке, а проект уровнем выше — поэтому «..».
cd /d "%~dp0.."

set "VPY=.venv\Scripts\python.exe"
if not exist "%VPY%" (
    echo [X] Сначала запустите ЗАПУСТИТЬ-КОПИЮ.bat - он создаст окружение.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo   ПРОВЕРКА ПЕРЕД ОТПРАВКОЙ НА СЕРВЕР
echo ==========================================
echo.

echo [1/5] Проверка настроек (manage.py check)...
"%VPY%" manage.py check
if errorlevel 1 goto :error

echo [2/5] Миграции совпадают с моделями...
"%VPY%" manage.py makemigrations --check --dry-run
if errorlevel 1 goto :error

echo [3/5] Все надписи переведены на украинский...
"%VPY%" manage.py makelocales --check
if errorlevel 1 goto :error

echo [4/5] Сборка переводов...
"%VPY%" manage.py compilelocales
if errorlevel 1 goto :error

echo [5/5] Тесты (пара минут)...
"%VPY%" manage.py test --noinput
if errorlevel 1 goto :error

echo.
echo ==========================================
echo   ВСЁ ЗЕЛЁНОЕ - можно отправлять на сервер
echo ==========================================
echo.
pause
exit /b 0

:error
echo.
echo [X] Проверка не прошла - смотрите сообщение выше.
echo     Пока не исправлено, на сервер лучше не отправлять.
echo.
pause
exit /b 1
