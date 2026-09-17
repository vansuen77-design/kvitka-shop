@echo off
chcp 65001 >nul
title KVITKA - deploy to server
cd /d "%~dp0"
setlocal

rem Put your server address here (see deploy\INSTALL.md)
set "SERVER=kvitka@SERVER-ADDRESS"
set "REMOTE=/home/kvitka/kvitka"

echo.
echo ==========================================
echo   DEPLOY TO SERVER
echo ==========================================
echo.
echo   From: %~dp0
echo   To:   %SERVER%:%REMOTE%
echo.

where scp >nul 2>&1
if errorlevel 1 goto :nossh
where tar >nul 2>&1
if errorlevel 1 goto :notar

rem ------------------------------------------------------------------
rem  Code is always sent. Content is optional: code changes happen
rem  daily, replacing the catalog is a rare and visible operation.
rem ------------------------------------------------------------------
echo   Products, attributes, pages and photos on the server
echo   will be REPLACED with what is in this folder now.
echo.
echo   Customer orders and admin login are kept:
echo   they always stay on the server.
echo.
rem When the catalog is maintained in the server admin, answering Y wipes
rem everything changed there. Show when the local copy was last pulled
rem from the server: if long ago, Y is almost certainly a mistake.
rem Read BEFORE the block: inside parentheses cmd expands %LASTPULL%
rem at parse time, before the assignment, and it would be empty.
set "LASTPULL="
if exist "var\last-pull.txt" set /p LASTPULL=<"var\last-pull.txt"
if defined LASTPULL (
    echo   Local copy last pulled from the server: %LASTPULL%
) else (
    echo   The local copy has NEVER been pulled from the server.
)
echo.
echo   If you changed anything in the server admin after that -
echo   answer N, otherwise those changes will be lost.
echo.
choice /c YN /m "Send content together with the code"
if errorlevel 2 (set "WITHDATA=") else (set "WITHDATA=1")
echo.

rem --- code ---------------------------------------------------------
echo [1/5] Packing and sending the code...
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

echo [2/5] Dependencies, migrations, translations, static files...
ssh %SERVER% "cd ~/kvitka && .venv/bin/pip install -q -r requirements.txt && .venv/bin/python manage.py migrate --noinput && .venv/bin/python manage.py compilelocales && .venv/bin/python manage.py collectstatic --noinput"
if errorlevel 1 goto :error

if not defined WITHDATA (
    echo [3/5] Content is not sent.
    echo [4/5] Skipped.
    goto :restart
)

rem --- database -----------------------------------------------------
echo [3/5] Preparing and sending the database...

rem First apply migrations to the LOCAL database. Otherwise this happens:
rem new migrations went out with the code, the server applied them, but the
rem local database does not know about them - and adopt_content rightly
rem refuses to replace the database with an older structure.
".venv\Scripts\python.exe" manage.py migrate --noinput
if errorlevel 1 goto :error
rem A live SQLite file must not be copied: the copy would be corrupted.
rem snapshot_db makes a consistent snapshot via VACUUM INTO.
".venv\Scripts\python.exe" manage.py snapshot_db _send.sqlite3
if errorlevel 1 goto :error
scp -q "_send.sqlite3" "%SERVER%:%REMOTE%/db.incoming.sqlite3"
if errorlevel 1 goto :error
del "_send.sqlite3"

rem --- photos -------------------------------------------------------
echo [4/5] Sending photos and adopting the content...
if exist "%TEMP%\kvitka-media.tar.gz" del "%TEMP%\kvitka-media.tar.gz"
tar -czf "%TEMP%\kvitka-media.tar.gz" media
if errorlevel 1 goto :error
scp -q "%TEMP%\kvitka-media.tar.gz" "%SERVER%:/tmp/kvitka-media.tar.gz"
if errorlevel 1 goto :error
del "%TEMP%\kvitka-media.tar.gz"

rem The database is swapped while the site is stopped: SQLite does not
rem forgive replacing the file under a running process. Downtime is seconds.
ssh %SERVER% "sudo systemctl stop kvitka; cd ~/kvitka && { chmod -R u+rwX media >/dev/null 2>&1 || true; } && tar -xzf /tmp/kvitka-media.tar.gz --delay-directory-restore --overwrite --no-same-permissions --no-same-owner && { chmod -R u+rwX media >/dev/null 2>&1 || true; } && rm -f /tmp/kvitka-media.tar.gz && .venv/bin/python manage.py adopt_content db.incoming.sqlite3; rc=$?; sudo systemctl start kvitka; exit $rc"
if errorlevel 1 goto :error

:restart
echo [5/5] Restarting the site...
ssh %SERVER% "sudo systemctl restart kvitka"
if errorlevel 1 goto :error

echo.
echo Done: https://kvitka.example/
echo.
echo If something looks wrong:
echo    ssh %SERVER% "journalctl -u kvitka -n 40"
echo.
pause
exit /b 0

:nossh
echo [X] scp not found. It is part of OpenSSH, built into Windows 10 and 11:
echo     Settings - Apps - Optional features - Add a feature - "OpenSSH Client".
echo.
pause
exit /b 1

:notar
echo [X] tar not found. It is built into Windows 10 version 1803 and newer.
echo     Update the system.
echo.
pause
exit /b 1

:error
echo.
echo [X] Failed - see the message above.
echo     The site on the server keeps running the previous version.
echo     The previous database is kept there as db.before-DATE.sqlite3
echo.
pause
exit /b 1
