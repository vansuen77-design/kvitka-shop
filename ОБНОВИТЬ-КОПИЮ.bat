@echo off
chcp 65001 >nul
title KVITKA - обновить копию с сервера
cd /d "%~dp0"
setlocal

rem Впишите адрес своего сервера (см. deploy\УСТАНОВКА.md)
set "SERVER=kvitka@АДРЕС-СЕРВЕРА"

echo.
echo ==========================================
echo   ОБНОВИТЬ КОПИЮ С СЕРВЕРА
echo ==========================================
echo.
echo   Заберу с сервера свежую базу и фотографии,
echo   чтобы вы правили на актуальных товарах и заказах.
echo.
echo   КОД не трогаю: он тут и есть главный, а на сервере
echo   лежит его копия. Иначе ваши правки затёрлись бы.
echo.

where scp >nul 2>&1
if errorlevel 1 (
    echo [X] Не нашёл scp. Это часть OpenSSH, он есть в Windows 10 и 11:
    echo     Параметры - Приложения - Дополнительные компоненты -
    echo     Добавить компонент - "Клиент OpenSSH".
    echo.
    pause
    exit /b 1
)

pause

echo.
echo [1/3] Прошу сервер сделать снимок базы...
rem Живую базу копировать нельзя: сайт в этот момент в неё пишет,
rem и копия может выйти битой. Команда .backup делает согласованный снимок.
ssh %SERVER% "sqlite3 ~/kvitka/db.sqlite3 '.backup /tmp/kvitka-copy.sqlite3'"
if errorlevel 1 goto :error

echo [2/3] Забираю базу...
scp -q "%SERVER%:/tmp/kvitka-copy.sqlite3" "db.sqlite3"
if errorlevel 1 goto :error
ssh %SERVER% "rm -f /tmp/kvitka-copy.sqlite3"

echo [3/3] Забираю фотографии...
if not exist "media" mkdir "media"
rem Без обратного слэша в конце: "media\" — это не путь с разделителем,
rem а экранированная кавычка, и scp получает мусор вида media"
scp -q -r "%SERVER%:/home/kvitka/kvitka/media/*" "media"
if errorlevel 1 goto :error


rem Отметка времени: её показывает ОТПРАВИТЬ-НА-СЕРВЕР перед тем,
rem как затирать серверную базу. Без неё легко забыть, что каталог
rem на сервере успел уйти вперёд.
if not exist "var" mkdir "var"
echo %DATE% %TIME%> "var\last-pull.txt"

echo.
echo Готово. Запускайте ЗАПУСТИТЬ-КОПИЮ.bat
echo.
pause
exit /b 0

:error
echo.
echo [X] Не получилось - смотрите сообщение выше.
echo     Если упало на шаге 1 - ничего не изменилось.
echo     Если на шаге 3 - база уже обновлена, не хватает только фото.
echo.
pause
exit /b 1
