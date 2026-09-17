#!/bin/bash
# Сторож: раз в несколько минут проверяет, отвечает ли сайт, и пишет
# в Telegram, когда он упал или снова поднялся.
#
# Сообщение уходит только в момент СМЕНЫ состояния. Иначе при падении
# на ночь вы бы получили сотню одинаковых сообщений и перестали бы
# их читать — а это ровно то, ради чего сторож и ставится.
#
# Проверяются две точки:
#   * публичный адрес — как его видит покупатель (через Cloudflare);
#   * 127.0.0.1:8000  — сам Django на сервере.
# Разница между ними сразу говорит, где искать: если локально всё живо,
# а снаружи нет — упал туннель, а не сайт.
#
# Токен берётся из того же .env, что и уведомления о заказах.
# Отдельно ничего настраивать не нужно.
#
# Установка:
#   scp deploy/monitor.sh kvitka@СЕРВЕР:/home/kvitka/kvitka/deploy/
#   chmod +x /home/kvitka/kvitka/deploy/monitor.sh
#   sudo cp deploy/kvitka-monitor.* /etc/systemd/system/
#   sudo systemctl daemon-reload
#   sudo systemctl enable --now kvitka-monitor.timer

set -uo pipefail

PROJECT="/home/kvitka/kvitka"
STATE="/home/kvitka/.kvitka-monitor-state"
ENV_FILE="$PROJECT/.env"

# --- настройки из .env ---------------------------------------------------
value_of() {
    grep -m1 "^$1=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- | tr -d '"'"'"' \r'
}

TOKEN=$(value_of TELEGRAM_BOT_TOKEN)
CHAT=$(value_of TELEGRAM_CHAT_ID)
SITE=$(value_of SITE_URL)
if [ -z "$SITE" ]; then
    HOST=$(value_of ALLOWED_HOSTS | cut -d, -f1)
    SITE="https://${HOST:-kvitka.example}"
fi

notify() {
    [ -n "$TOKEN" ] && [ -n "$CHAT" ] || return 0
    curl -sS --max-time 15 -o /dev/null \
        -d "chat_id=$CHAT" -d "parse_mode=HTML" --data-urlencode "text=$1" \
        "https://api.telegram.org/bot$TOKEN/sendMessage" || true
}

check_public() {
    curl -sS -o /dev/null --max-time 20 -w "%{http_code}" "$SITE/" 2>/dev/null
}
check_local() {
    curl -sS -o /dev/null --max-time 10 -w "%{http_code}" \
        -H "Host: ${SITE#https://}" http://127.0.0.1:8000/ 2>/dev/null
}

# --- проверка с повтором -------------------------------------------------
# один неудачный запрос ещё ничего не значит: сеть моргает.
CODE=$(check_public)
if [ "$CODE" != "200" ]; then
    sleep 20
    CODE=$(check_public)
fi

PREVIOUS=$(cat "$STATE" 2>/dev/null || echo "ok")

if [ "$CODE" = "200" ]; then
    if [ "$PREVIOUS" != "ok" ]; then
        notify "🟢 <b>Сайт снова работает</b>
$SITE отвечает нормально."
    fi
    echo "ok" > "$STATE"
    exit 0
fi

# --- сайт не отвечает: выясняем, где именно порвалось --------------------
LOCAL=$(check_local)
if [ "$LOCAL" = "200" ]; then
    WHERE="Django на сервере жив, наружу не пускает <b>туннель Cloudflare</b>.
Смотреть: systemctl status kvitka-tunnel"
else
    WHERE="Не отвечает и сам <b>Django</b> (локально код: ${LOCAL:-нет ответа}).
Смотреть: systemctl status kvitka"
fi

if [ "$PREVIOUS" = "ok" ]; then
    notify "🔴 <b>Сайт не отвечает</b>
$SITE — код: ${CODE:-нет ответа}

$WHERE"
fi
echo "fail" > "$STATE"
