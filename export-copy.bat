@echo off
chcp 65001 >nul
title KVITKA - export a clean copy of the project
cd /d "%~dp0"

set "DST=%USERPROFILE%\Desktop\kvitka-shop-export"

echo.
echo ==========================================
echo   CLEAN COPY OF THE PROJECT
echo ==========================================
echo.
echo   From: %~dp0
echo   To:   %DST%
echo.
echo   Not included in the copy:
echo      .env               - secrets
echo      db.sqlite3         - database with customer orders
echo      media\             - product photos
echo      var\, .venv\       - working environment
echo.

if exist "%DST%" (
    echo   The folder already exists. Its contents will be updated.
    echo.
)

choice /c YN /m "Export"
if errorlevel 2 goto :cancel

echo.
echo Copying...
robocopy "%~dp0." "%DST%" /E /NFL /NDL /NJH /NJS /NP ^
  /XD .venv venv __pycache__ media var .git node_modules staticfiles .work ^
  /XF db.sqlite3 *.sqlite3 *.sqlite3.old .env *.pyc

rem robocopy returns 0-7 on success, 8 and above is a real error
if %ERRORLEVEL% GEQ 8 goto :error

echo.
echo Done. Folder: %DST%
echo.
pause
exit /b 0

:cancel
echo.
echo Cancelled.
echo.
pause
exit /b 0

:error
echo.
echo [X] Copy failed - see the message above.
echo.
pause
exit /b 1
