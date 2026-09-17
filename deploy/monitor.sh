#!/bin/bash
# Watchdog: every few minutes checks whether the site answers and writes
# to Telegram when it goes down or comes back up.
#
# A message is sent only when the state CHANGES. Otherwise an overnight
# outage would produce a hundred identical messages and you would stop
# reading them - which is exactly what the watchdog is here to prevent.
#
# Two endpoints are checked:
#   * the public address - as the customer sees it (through Cloudflare);
#   * 127.0.0.1:8000     - Django itself on the server.
# The difference tells you where to look: if local is alive but public
# is not - the tunnel is down, not the site.
#
# The token comes from the same .env as order notifications.
# Nothing extra to configure.
#
# Install:
#   scp deploy/monitor.sh kvitka@SERVER:/home/kvitka/kvitka/deploy/
#   chmod +x /home/kvitka/kvitka/deploy/monitor.sh
#   sudo cp deploy/kvitka-monitor.* /etc/systemd/system/
#   sudo systemctl daemon-reload
#   sudo systemctl enable --now kvitka-monitor.timer

set -uo pipefail

PROJECT="/home/kvitka/kvitka"
STATE="/home/kvitka/.kvitka-monitor-state"
ENV_FILE="$PROJECT/.env"

# --- settings from .env --------------------------------------------------
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

# --- check with a retry --------------------------------------------------
# a single failed request means nothing yet: networks blink.
CODE=$(check_public)
if [ "$CODE" != "200" ]; then
    sleep 20
    CODE=$(check_public)
fi

PREVIOUS=$(cat "$STATE" 2>/dev/null || echo "ok")

if [ "$CODE" = "200" ]; then
    if [ "$PREVIOUS" != "ok" ]; then
        notify "🟢 <b>Site is back up</b>
$SITE answers normally."
    fi
    echo "ok" > "$STATE"
    exit 0
fi

# --- site is down: find out where exactly it broke -----------------------
LOCAL=$(check_local)
if [ "$LOCAL" = "200" ]; then
    WHERE="Django on the server is alive, the <b>Cloudflare tunnel</b> is not passing traffic.
Check: systemctl status kvitka-tunnel"
else
    WHERE="<b>Django</b> itself does not answer (local code: ${LOCAL:-no response}).
Check: systemctl status kvitka"
fi

if [ "$PREVIOUS" = "ok" ]; then
    notify "🔴 <b>Site is down</b>
$SITE - code: ${CODE:-no response}

$WHERE"
fi
echo "fail" > "$STATE"
