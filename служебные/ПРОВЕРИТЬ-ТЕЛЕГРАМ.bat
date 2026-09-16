@echo off
chcp 65001 >nul
title KVITKA - проверка Telegram
rem Батник лежит в подпапке, а проект уровнем выше — поэтому «..».
rem Без этой строки Python и manage.py искались бы здесь и не нашлись.
cd /d "%~dp0.."
set "VPY=.venv\Scripts\python.exe"
if not exist "%VPY%" (
    echo [X] Не нашёл Python копии. Сначала запустите ЗАПУСТИТЬ-КОПИЮ.bat
    pause
    exit /b 1
)
echo.
echo ==========================================
echo   ПРОВЕРКА УВЕДОМЛЕНИЙ В TELEGRAM
echo ==========================================
echo.
echo   Токен и ваш id берутся из файла .env в этой папке.
echo.
"%VPY%" manage.py telegram_test
echo.
echo   Если сообщение не пришло - убедитесь, что вы написали
echo   своему боту /start. Боту нельзя писать первым тому,
echo   кто с ним ни разу не заговорил.
echo.
pause
