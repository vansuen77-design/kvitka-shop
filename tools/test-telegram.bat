@echo off
chcp 65001 >nul
title KVITKA - Telegram check
rem This script lives in a subfolder, the project is one level up - hence "..".
rem Without this line Python and manage.py would be looked up here and not found.
cd /d "%~dp0.."
set "VPY=.venv\Scripts\python.exe"
if not exist "%VPY%" (
    echo [X] Python not found. Run start.bat first.
    pause
    exit /b 1
)
echo.
echo ==========================================
echo   TELEGRAM NOTIFICATION CHECK
echo ==========================================
echo.
echo   The bot token and your chat id are read from .env in this folder.
echo.
"%VPY%" manage.py telegram_test
echo.
echo   If the message did not arrive - make sure you have sent /start
echo   to your bot. A bot cannot message someone who never talked to it.
echo.
pause
