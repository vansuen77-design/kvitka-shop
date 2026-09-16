#!/bin/bash
# Резервная копия базы и фотографий.
#
# База копируется командой sqlite3 .backup, а не обычным cp: сайт в это
# время работает, и копия «на лету» может получиться битой. Эта команда
# делает согласованный снимок.
#
# Ставится таймером systemd (см. kvitka-backup.timer) — раз в сутки ночью.
# Хранятся последние 14 копий.

set -euo pipefail

PROJECT="/home/kvitka/kvitka"
DEST="/home/kvitka/backups"
KEEP=14
STAMP=$(date +%Y-%m-%d_%H-%M)

mkdir -p "$DEST"

sqlite3 "$PROJECT/db.sqlite3" ".backup '$DEST/db_$STAMP.sqlite3'"
gzip -f "$DEST/db_$STAMP.sqlite3"

tar -czf "$DEST/media_$STAMP.tar.gz" -C "$PROJECT" media

# чистим старые: оставляем последние $KEEP каждого вида
for prefix in db media; do
    ls -1t "$DEST/${prefix}_"* 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm --
done

echo "Готово: $DEST/db_$STAMP.sqlite3.gz и media_$STAMP.tar.gz"
