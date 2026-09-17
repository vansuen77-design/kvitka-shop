@echo off
chcp 65001 >nul
title KVITKA - deploy diagnostics
rem This script lives in a subfolder, the project is one level up - hence "..".
rem Without this line Python and manage.py would be looked up here and not found.
cd /d "%~dp0.."
set "SERVER=kvitka@SERVER-ADDRESS"

echo [1] Packing the archive...
if exist "%TEMP%\t.tgz" del "%TEMP%\t.tgz"
tar -czf "%TEMP%\t.tgz" --exclude=__pycache__ catalog config core orders pages templates static locale manage.py requirements.txt
echo    tar exit code: %errorlevel%

echo [2] Sending the archive to the server...
scp -q "%TEMP%\t.tgz" "%SERVER%:/tmp/t.tgz"
echo    scp exit code: %errorlevel%

echo.
echo ===== WHO AM I ON THE SERVER =====
ssh %SERVER% "id; echo ---; ls -ld ~/kvitka ~/kvitka/static ~/kvitka/static/css ~/kvitka/core/management/commands; echo ---; lsattr -d ~/kvitka/static/css 2>&1 | head -2; echo ---; tar --version | head -1; echo ---; df -h ~/kvitka | tail -1"

echo.
echo ===== DUPLICATES IN THE ARCHIVE =====
ssh %SERVER% "tar -tzf /tmp/t.tgz | sort | uniq -d | head -20; echo END-OF-DUPLICATES"

echo.
echo ===== HOW FILES ARE STORED IN THE ARCHIVE =====
ssh %SERVER% "tar -tvzf /tmp/t.tgz | grep -E 'static/css/base.css|static/js/catalog.js|catalog/models.py' "

echo.
echo ===== EXTRACT INTO AN EMPTY FOLDER =====
ssh %SERVER% "rm -rf /tmp/probe; mkdir -p /tmp/probe; tar -xzf /tmp/t.tgz -C /tmp/probe && echo RESULT-EMPTY-OK || echo RESULT-EMPTY-ERROR"

echo.
echo ===== EXTRACT OVER A COPY OF THE SITE =====
ssh %SERVER% "rm -rf /tmp/probe2; mkdir -p /tmp/probe2; cd ~/kvitka && tar -cf - --exclude=.venv --exclude=media --exclude=staticfiles . | tar -xf - -C /tmp/probe2; tar -xzf /tmp/t.tgz -C /tmp/probe2 && echo RESULT-OVERLAY-OK || echo RESULT-OVERLAY-ERROR"

echo.
echo ===== DONE. The live site was not touched. =====
pause
