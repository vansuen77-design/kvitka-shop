"""Consistent database snapshot via VACUUM INTO (not by copying the file).

A live SQLite file must not be copied: the site is writing to it and the
copy comes out corrupted. VACUUM INTO makes a whole snapshot by SQLite's
own means.
"""

import sqlite3
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Database snapshot: manage.py snapshot_db db.incoming.sqlite3"

    def add_arguments(self, parser):
        parser.add_argument("target", help="where to write the snapshot")

    def handle(self, *args, target, **options):
        source = Path(settings.DATABASES["default"]["NAME"])
        target = Path(target).resolve()
        if target == source.resolve():
            raise CommandError("The snapshot cannot overwrite the database itself")
        if target.exists():
            target.unlink()
        with sqlite3.connect(source) as conn:
            conn.execute("VACUUM INTO ?", (str(target),))
        self.stdout.write(self.style.SUCCESS(
            f"Snapshot: {target.name} ({target.stat().st_size // 1024} KB)"
        ))
