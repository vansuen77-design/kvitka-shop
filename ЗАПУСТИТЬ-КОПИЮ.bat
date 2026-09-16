@echo off
chcp 65001 >nul
title KVITKA - КОПИЯ для правок (порт 8001)
cd /d "%~dp0"

echo.
echo ==========================================
echo   КВІТКА - КОПИЯ ДЛЯ ПРАВОК
echo ==========================================
echo.
echo   Это НЕ боевой сайт. Здесь можно ломать что угодно:
echo   боевой сайт на сервере это не трогает.
echo.
echo   Копия:       http://127.0.0.1:8001/
echo   Боевой сайт: https://kvitka.example/  (на сервере)
echo.

rem --- Python: свой .venv, а если его нет - берём из боевой папки --------
set "VPY=.venv\Scripts\python.exe"
if not exist "%VPY%" (
    echo [X] Не нашёл Python.
    echo     Окружение потерялось. Создать заново:
    echo         python -m venv .venv
    echo         .venv\Scripts\python.exe -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

echo [0/3] Проверяю зависимости...
"%VPY%" -c "import django, PIL, waitress, whitenoise" 2>nul
if errorlevel 1 (
    echo       Чего-то не хватает, доставляю...
    "%VPY%" -m pip install -q -r requirements.txt
    if errorlevel 1 goto :error
)

echo [1/3] Собираю переводы...
"%VPY%" manage.py compilelocales
if errorlevel 1 goto :error

echo [2/3] Проверяю и применяю миграции...
rem Миграции создаёт разработчик и кладёт в код. Здесь только проверка:
rem если она ругается, значит код и миграции разъехались - пишите разработчику.
"%VPY%" manage.py makemigrations --check --dry-run
if errorlevel 1 goto :error
"%VPY%" manage.py migrate --noinput
if errorlevel 1 goto :error
"%VPY%" manage.py seed_facets
if errorlevel 1 goto :error

echo [3/3] Запускаю копию...
echo.
echo   Каталог:  http://127.0.0.1:8001/
echo   Админка:  http://127.0.0.1:8001/admin/
echo.
echo   Остановить - закройте это окно.
echo.

start "" http://127.0.0.1:8001/
"%VPY%" manage.py runserver 127.0.0.1:8001

goto :end

:error
echo.
echo [X] Что-то пошло не так - смотрите сообщение выше.
echo.
pause
exit /b 1

:end
echo.
echo Копия остановлена.
pause
