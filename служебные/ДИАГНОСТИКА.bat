@echo off
chcp 65001 >nul
title KVITKA - диагностика переноса
rem Батник лежит в подпапке, а проект уровнем выше — поэтому «..».
rem Без этой строки Python и manage.py искались бы здесь и не нашлись.
cd /d "%~dp0.."
set "SERVER=kvitka@185.101.38.39"

echo [1] Собираю архив...
if exist "%TEMP%\t.tgz" del "%TEMP%\t.tgz"
tar -czf "%TEMP%\t.tgz" --exclude=__pycache__ catalog config core orders pages templates static locale manage.py requirements.txt
echo    код возврата tar: %errorlevel%

echo [2] Отправляю архив на сервер...
scp -q "%TEMP%\t.tgz" "%SERVER%:/tmp/t.tgz"
echo    код возврата scp: %errorlevel%

echo.
echo ===== КТО Я НА СЕРВЕРЕ =====
ssh %SERVER% "id; echo ---; ls -ld ~/kvitka ~/kvitka/static ~/kvitka/static/css ~/kvitka/core/management/commands; echo ---; lsattr -d ~/kvitka/static/css 2>&1 | head -2; echo ---; tar --version | head -1; echo ---; df -h ~/kvitka | tail -1"

echo.
echo ===== ДУБЛИКАТЫ В АРХИВЕ =====
ssh %SERVER% "tar -tzf /tmp/t.tgz | sort | uniq -d | head -20; echo КОНЕЦ-СПИСКА-ДУБЛИКАТОВ"

echo.
echo ===== КАК ЛЕЖИТ ФАЙЛ В АРХИВЕ =====
ssh %SERVER% "tar -tvzf /tmp/t.tgz | grep -E 'static/css/base.css|static/js/catalog.js|catalog/models.py' "

echo.
echo ===== РАСПАКОВКА В ПУСТУЮ ПАПКУ =====
ssh %SERVER% "rm -rf /tmp/probe; mkdir -p /tmp/probe; tar -xzf /tmp/t.tgz -C /tmp/probe && echo РЕЗУЛЬТАТ-ПУСТАЯ-OK || echo РЕЗУЛЬТАТ-ПУСТАЯ-ОШИБКА"

echo.
echo ===== РАСПАКОВКА ПОВЕРХ КОПИИ САЙТА =====
ssh %SERVER% "rm -rf /tmp/probe2; mkdir -p /tmp/probe2; cd ~/kvitka && tar -cf - --exclude=.venv --exclude=media --exclude=staticfiles . | tar -xf - -C /tmp/probe2; tar -xzf /tmp/t.tgz -C /tmp/probe2 && echo РЕЗУЛЬТАТ-ПОВЕРХ-OK || echo РЕЗУЛЬТАТ-ПОВЕРХ-ОШИБКА"

echo.
echo ===== ГОТОВО. Сайт не трогали. =====
pause
