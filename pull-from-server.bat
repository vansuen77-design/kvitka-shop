@echo off
chcp 65001 >nul
title KVITKA - pull database and photos from the server
cd /d "%~dp0"
setlocal

rem Put your server address here (see deploy\INSTALL.md)
set "SERVER=kvitka@SERVER-ADDRESS"

echo.
echo ==========================================
echo   PULL FROM SERVER
echo ==========================================
echo.
echo   Fetches the fresh database and photos from the server
echo   so you edit against the current products and orders.
echo.
echo   The CODE is not touched: this folder is the source of truth,
echo   the server only holds a copy of it.
echo.

where scp >nul 2>&1
if errorlevel 1 (
    echo [X] scp not found. It is part of OpenSSH, built into Windows 10 and 11:
    echo     Settings - Apps - Optional features - Add a feature - "OpenSSH Client".
    echo.
    pause
    exit /b 1
)

pause

echo.
echo [1/3] Asking the server for a database snapshot...
rem A live SQLite file must not be copied while the site writes to it:
rem the copy may come out corrupted. ".backup" makes a consistent snapshot.
ssh %SERVER% "sqlite3 ~/kvitka/db.sqlite3 '.backup /tmp/kvitka-copy.sqlite3'"
if errorlevel 1 goto :error

echo [2/3] Downloading the database...
scp -q "%SERVER%:/tmp/kvitka-copy.sqlite3" "db.sqlite3"
if errorlevel 1 goto :error
ssh %SERVER% "rm -f /tmp/kvitka-copy.sqlite3"

echo [3/3] Downloading photos...
if not exist "media" mkdir "media"
rem No trailing backslash: "media\" is not a path separator but an escaped
rem quote, and scp would receive garbage like media"
scp -q -r "%SERVER%:/home/kvitka/kvitka/media/*" "media"
if errorlevel 1 goto :error


rem Timestamp: deploy-to-server.bat shows it before overwriting the
rem server database. Without it, it is easy to forget that the catalog
rem on the server has moved on.
if not exist "var" mkdir "var"
echo %DATE% %TIME%> "var\last-pull.txt"

echo.
echo Done. Now run start.bat
echo.
pause
exit /b 0

:error
echo.
echo [X] Failed - see the message above.
echo     If it failed at step 1 - nothing has changed.
echo     If at step 3 - the database is already updated, only photos are missing.
echo.
pause
exit /b 1
