@echo off
chcp 65001 >nul
title KVITKA - download backups
cd /d "%~dp0"
setlocal

rem Put your server address here (see deploy\INSTALL.md)
set "SERVER=kvitka@SERVER-ADDRESS"
rem Stored next to the project, not in %USERPROFILE%\Desktop: when the
rem desktop is redirected to OneDrive these are different folders, and the
rem second one is not visible on screen.
set "DEST=%~dp0..\kvitka-backups\from-server"

echo.
echo ==========================================
echo   BACKUPS FROM THE SERVER
echo ==========================================
echo.
echo   To: %DEST%
echo.
echo   On the server, backups are kept for 14 days on the same disk as
echo   the site. This script copies them to you - so a server failure
echo   does not take all the backups with it.
echo.

where scp >nul 2>&1
if errorlevel 1 (
    echo [X] scp not found. OpenSSH is required - it is built into Windows 10 and 11.
    pause
    exit /b 1
)

if not exist "%DEST%" mkdir "%DEST%"

echo [1/3] Making a fresh backup on the server...
ssh %SERVER% "sudo systemctl start kvitka-backup || bash ~/kvitka/deploy/backup.sh"
if errorlevel 1 goto :error

echo [2/3] Looking for the latest backups...
set "DBF="
set "MEDIAF="
for /f "delims=" %%i in ('ssh %SERVER% "ls -1t ~/backups/db_*.gz | head -1"') do set "DBF=%%i"
for /f "delims=" %%i in ('ssh %SERVER% "ls -1t ~/backups/media_*.tar.gz | head -1"') do set "MEDIAF=%%i"
if not defined DBF (
    echo [X] No database backup found on the server.
    echo     Check what is there:  ssh %SERVER% "ls -la ~/backups"
    goto :error
)
echo    database: %DBF%
echo    photos:   %MEDIAF%

echo [3/3] Downloading...
rem Download into a temporary folder with an ASCII name first and move
rem afterwards: scp on Windows trips over non-ASCII paths, and a trailing
rem backslash before a quote breaks argument parsing.
set "TMPDIR=%TEMP%\kvitka-backup"
if exist "%TMPDIR%" rd /s /q "%TMPDIR%"
mkdir "%TMPDIR%"
scp -q "%SERVER%:%DBF%" "%TMPDIR%"
if errorlevel 1 goto :error
if defined MEDIAF scp -q "%SERVER%:%MEDIAF%" "%TMPDIR%"
move /y "%TMPDIR%\*" "%DEST%" >nul
rd /s /q "%TMPDIR%"

echo.
echo ==========================================
echo   Done. Files are here:
echo   %DEST%
echo ==========================================
echo.
echo   The folder grows over time - delete old backups by hand,
echo   keeping more than a few makes no sense.
echo.
explorer "%DEST%"
pause
exit /b 0

:error
echo.
echo [X] Failed - see the message above.
pause
exit /b 1
