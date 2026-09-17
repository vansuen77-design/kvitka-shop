#!/bin/bash
# Backup of the database and photos.
#
# The database is copied with sqlite3 .backup, not plain cp: the site is
# running meanwhile, and a copy "on the fly" may come out corrupted. This
# command makes a consistent snapshot.
#
# Scheduled by a systemd timer (see kvitka-backup.timer) - once a night.
# The last 14 copies are kept.

set -euo pipefail

PROJECT="/home/kvitka/kvitka"
DEST="/home/kvitka/backups"
KEEP=14
STAMP=$(date +%Y-%m-%d_%H-%M)

mkdir -p "$DEST"

sqlite3 "$PROJECT/db.sqlite3" ".backup '$DEST/db_$STAMP.sqlite3'"
gzip -f "$DEST/db_$STAMP.sqlite3"

tar -czf "$DEST/media_$STAMP.tar.gz" -C "$PROJECT" media

# prune old ones: keep the last $KEEP of each kind
for prefix in db media; do
    ls -1t "$DEST/${prefix}_"* 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm --
done

echo "Done: $DEST/db_$STAMP.sqlite3.gz and media_$STAMP.tar.gz"
