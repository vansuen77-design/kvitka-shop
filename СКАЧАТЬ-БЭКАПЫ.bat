@echo off
chcp 65001 >nul
title KVITKA - скачать резервные копии
cd /d "%~dp0"
setlocal

rem Впишите адрес своего сервера (см. deploy\УСТАНОВКА.md)
set "SERVER=kvitka@АДРЕС-СЕРВЕРА"
rem Кладём рядом с самим проектом, а не в %USERPROFILE%\Desktop:
rem когда рабочий стол перенесён в OneDrive, это разные папки,
rem и вторая на экране не видна.
set "DEST=%~dp0..\kvitka-резервные-копии\с-сервера"

echo.
echo ==========================================
echo   РЕЗЕРВНЫЕ КОПИИ С СЕРВЕРА
echo ==========================================
echo.
echo   Куда: %DEST%
echo.
echo   На сервере копии хранятся 14 дней и лежат на том же диске,
echo   что и сайт. Этот файл забирает их к вам - чтобы поломка
echo   сервера не унесла заодно и все копии.
echo.

where scp >nul 2>&1
if errorlevel 1 (
    echo [X] Не нашёл scp. Нужен OpenSSH - он встроен в Windows 10 и 11.
    pause
    exit /b 1
)

if not exist "%DEST%" mkdir "%DEST%"

echo [1/3] Делаю на сервере свежую копию...
ssh %SERVER% "sudo systemctl start kvitka-backup || bash ~/kvitka/deploy/backup.sh"
if errorlevel 1 goto :error

echo [2/3] Ищу последние копии...
set "DBF="
set "MEDIAF="
for /f "delims=" %%i in ('ssh %SERVER% "ls -1t ~/backups/db_*.gz | head -1"') do set "DBF=%%i"
for /f "delims=" %%i in ('ssh %SERVER% "ls -1t ~/backups/media_*.tar.gz | head -1"') do set "MEDIAF=%%i"
if not defined DBF (
    echo [X] На сервере не нашлось ни одной копии базы.
    echo     Посмотрите, что там лежит:  ssh %SERVER% "ls -la ~/backups"
    goto :error
)
echo    база:  %DBF%
echo    фото:  %MEDIAF%

echo [3/3] Скачиваю...
rem Качаем во временную папку с латинским именем и только потом
rem переносим: scp на Windows спотыкается о кириллицу в пути,
rem а закрывающая косая перед кавычкой ломает разбор аргумента.
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
echo   Готово. Файлы здесь:
echo   %DEST%
echo ==========================================
echo.
echo   Со временем папка разрастётся - старые копии удаляйте руками,
echo   держать больше нескольких штук смысла нет.
echo.
explorer "%DEST%"
pause
exit /b 0

:error
echo.
echo [X] Не получилось - смотрите сообщение выше.
pause
exit /b 1
