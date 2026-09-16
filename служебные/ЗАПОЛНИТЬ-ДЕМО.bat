@echo off
chcp 65001 >nul
title KVITKA - демонстрационный каталог
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
echo   ДЕМОНСТРАЦИОННЫЙ КАТАЛОГ
echo ==========================================
echo.
echo   Заводит статусы, разделы, справочники подбора, страницы
echo   подвала и 15 букетов с картинками-заглушками.
echo   То, что уже есть в базе, не трогает: можно запускать повторно.
echo.
choice /c YN /m "Заполнять"
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
echo Готово. Запустите ЗАПУСТИТЬ-КОПИЮ.bat и откройте каталог.
echo Картинки-заглушки замените своими фото в админке: Товары - фотографии.
echo.
pause
exit /b 0

:cancel
echo Отменено.
pause
exit /b 0

:error
echo.
echo [X] Не получилось - смотрите сообщение выше.
echo.
pause
exit /b 1
