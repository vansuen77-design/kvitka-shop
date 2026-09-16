@echo off
chcp 65001 >nul
title KVITKA - отправить на сервер
cd /d "%~dp0"
setlocal

set "SERVER=kvitka@185.101.38.39"
set "REMOTE=/home/kvitka/kvitka"

echo.
echo ==========================================
echo   ОТПРАВКА НА СЕРВЕР
echo ==========================================
echo.
echo   Отсюда: %~dp0
echo   Туда:   %SERVER%:%REMOTE%
echo.

where scp >nul 2>&1
if errorlevel 1 goto :nossh
where tar >nul 2>&1
if errorlevel 1 goto :notar

rem ------------------------------------------------------------------
rem  Код уходит всегда. Содержимое - по вопросу: правки кода бывают
rem  каждый день, а замена каталога это редкая и заметная операция.
rem ------------------------------------------------------------------
echo   Товары, характеристики, страницы и фотографии на сервере
echo   будут ЗАМЕНЕНЫ на то, что сейчас в этой папке.
echo.
echo   Заявки покупателей и вход в админку сохранятся:
echo   они остаются серверные.
echo.
rem Когда каталог ведут в админке сервера, ответ Y затирает всё, что
rem там наменяли. Показываем, когда копию последний раз обновляли
rem с сервера: если давно - почти наверняка Y будет ошибкой.
rem Читаем ДО блока: внутри скобок cmd подставляет %LASTPULL% ещё на
rem разборе, до присваивания, и переменная вышла бы пустой. Та же
rem ловушка, что с ^ внутри for.
set "LASTPULL="
if exist "var\last-pull.txt" set /p LASTPULL=<"var\last-pull.txt"
if defined LASTPULL (
    echo   Копия обновлялась с сервера: %LASTPULL%
) else (
    echo   Копию с сервера НИ РАЗУ не обновляли.
)
echo.
echo   Если после этого вы что-то меняли в админке сервера -
echo   отвечайте N, иначе те правки пропадут.
echo.
choice /c YN /m "Переносить содержимое вместе с кодом"
if errorlevel 2 (set "WITHDATA=") else (set "WITHDATA=1")
echo.

rem --- код ----------------------------------------------------------
echo [1/5] Собираю и отправляю код...
if exist "%TEMP%\kvitka-code.tar.gz" del "%TEMP%\kvitka-code.tar.gz"
tar -czf "%TEMP%\kvitka-code.tar.gz" --exclude=__pycache__ ^
    catalog config core orders pages accounts templates static locale deploy ^
    manage.py requirements.txt
if errorlevel 1 goto :error
scp -q "%TEMP%\kvitka-code.tar.gz" "%SERVER%:/tmp/kvitka-code.tar.gz"
if errorlevel 1 goto :error
ssh %SERVER% "cd ~/kvitka && { chmod -R u+rwX . >/dev/null 2>&1 || true; } && tar -xzf /tmp/kvitka-code.tar.gz --delay-directory-restore --overwrite --no-same-permissions --no-same-owner; rc=$?; chmod -R u+rwX . >/dev/null 2>&1 || true; rm -f /tmp/kvitka-code.tar.gz; exit $rc"
if errorlevel 1 goto :error
del "%TEMP%\kvitka-code.tar.gz"

echo [2/5] Зависимости, миграции, переводы, статика...
ssh %SERVER% "cd ~/kvitka && .venv/bin/pip install -q -r requirements.txt && .venv/bin/python manage.py migrate --noinput && .venv/bin/python manage.py compilelocales && .venv/bin/python manage.py collectstatic --noinput"
if errorlevel 1 goto :error

if not defined WITHDATA (
    echo [3/5] Содержимое не переносим.
    echo [4/5] Пропускаю.
    goto :restart
)

rem --- база ---------------------------------------------------------
echo [3/5] Готовлю и отправляю базу...

rem Сначала догоняем миграции в СВОЕЙ базе. Без этого бывает так:
rem новые миграции уехали с кодом, сервер их применил, а локальная база
rem про них не знает - и adopt_content справедливо отказывается менять
rem базу на структуру постарше. Раньше это лечилось запуском копии
rem вручную; теперь батник делает это сам.
".venv\Scripts\python.exe" manage.py migrate --noinput
if errorlevel 1 goto :error
rem Живую базу копировать нельзя: копия выйдет битой. Команда snapshot_db
rem делает согласованный снимок через VACUUM INTO.
".venv\Scripts\python.exe" manage.py snapshot_db _send.sqlite3
if errorlevel 1 goto :error
scp -q "_send.sqlite3" "%SERVER%:%REMOTE%/db.incoming.sqlite3"
if errorlevel 1 goto :error
del "_send.sqlite3"

rem --- фотографии ---------------------------------------------------
echo [4/5] Отправляю фотографии и принимаю содержимое...
if exist "%TEMP%\kvitka-media.tar.gz" del "%TEMP%\kvitka-media.tar.gz"
tar -czf "%TEMP%\kvitka-media.tar.gz" media
if errorlevel 1 goto :error
scp -q "%TEMP%\kvitka-media.tar.gz" "%SERVER%:/tmp/kvitka-media.tar.gz"
if errorlevel 1 goto :error
del "%TEMP%\kvitka-media.tar.gz"

rem Базу подменяем при остановленном сайте: менять файл под работающим
rem процессом SQLite не прощает. Простой - пара секунд.
ssh %SERVER% "sudo systemctl stop kvitka; cd ~/kvitka && { chmod -R u+rwX media >/dev/null 2>&1 || true; } && tar -xzf /tmp/kvitka-media.tar.gz --delay-directory-restore --overwrite --no-same-permissions --no-same-owner && { chmod -R u+rwX media >/dev/null 2>&1 || true; } && rm -f /tmp/kvitka-media.tar.gz && .venv/bin/python manage.py adopt_content db.incoming.sqlite3; rc=$?; sudo systemctl start kvitka; exit $rc"
if errorlevel 1 goto :error

:restart
echo [5/5] Перезапускаю сайт...
ssh %SERVER% "sudo systemctl restart kvitka"
if errorlevel 1 goto :error

echo.
echo Готово: https://kvitka.example/
echo.
echo Если что-то не так:
echo    ssh %SERVER% "journalctl -u kvitka -n 40"
echo.
pause
exit /b 0

:nossh
echo [X] Не нашёл scp. Это часть OpenSSH, он есть в Windows 10 и 11:
echo     Параметры - Приложения - Дополнительные компоненты -
echo     Добавить компонент - "Клиент OpenSSH".
echo.
pause
exit /b 1

:notar
echo [X] Не нашёл tar. Он встроен в Windows 10 версии 1803 и новее.
echo     Обновите систему или напишите мне - сделаю обход.
echo.
pause
exit /b 1

:error
echo.
echo [X] Не получилось - смотрите сообщение выше.
echo     Сайт на сервере работает на прежней версии.
echo     Прежняя база лежит там же: db.before-ДАТА.sqlite3
echo.
pause
exit /b 1
