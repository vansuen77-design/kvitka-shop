@echo off
chcp 65001 >nul
title KVITKA - собрать копию для GitHub
cd /d "%~dp0"

set "DST=%USERPROFILE%\OneDrive\Desktop\kvitka-shop-github"

echo.
echo ==========================================
echo   КОПИЯ ДЛЯ GITHUB
echo ==========================================
echo.
echo   Откуда: %~dp0
echo   Куда:   %DST%
echo.
echo   Не попадёт в копию:
echo      .env               - секреты
echo      db.sqlite3         - база с заказами покупателей
echo      media\             - фотографии товаров
echo      var\, .venv\       - рабочее окружение
echo.

if exist "%DST%" (
    echo   Папка уже существует. Содержимое будет обновлено.
    echo.
)

choice /c YN /m "Собирать"
if errorlevel 2 goto :cancel

echo.
echo Копирую...
robocopy "%~dp0." "%DST%" /E /NFL /NDL /NJH /NJS /NP ^
  /XD .venv venv __pycache__ media var .git node_modules staticfiles .work ^
  /XF db.sqlite3 *.sqlite3 *.sqlite3.old .env .seeded .seeded-men .schema-v2 .schema-v3 .schema-v4 .schema-v5 *.pyc _banner-varianty.html _hero-test.html _promo-test.html

rem robocopy возвращает 0-7 при успехе, 8 и выше - настоящая ошибка
if %ERRORLEVEL% GEQ 8 goto :error

echo.
echo Готово. Папка: %DST%
echo.
echo Дальше скажите об этом в чате - я положу туда README,
echo тесты и заменю личные данные на демонстрационные.
echo.
pause
exit /b 0

:cancel
echo.
echo Отменено.
echo.
pause
exit /b 0

:error
echo.
echo [X] Не получилось скопировать - смотрите сообщение выше.
echo.
pause
exit /b 1
