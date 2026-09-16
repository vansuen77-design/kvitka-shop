"""Согласованный снимок базы через VACUUM INTO (а не копированием файла).

Живую SQLite копировать нельзя: сайт в этот момент в неё пишет, и копия
выходит битой. VACUUM INTO делает цельный снимок средствами самой SQLite.
"""

import sqlite3
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Снимок базы: manage.py snapshot_db db.incoming.sqlite3"

    def add_arguments(self, parser):
        parser.add_argument("target", help="куда положить снимок")

    def handle(self, *args, target, **options):
        source = Path(settings.DATABASES["default"]["NAME"])
        target = Path(target).resolve()
        if target == source.resolve():
            raise CommandError("Снимок нельзя писать поверх самой базы")
        if target.exists():
            target.unlink()
        with sqlite3.connect(source) as conn:
            conn.execute("VACUUM INTO ?", (str(target),))
        self.stdout.write(self.style.SUCCESS(
            f"Снимок: {target.name} ({target.stat().st_size // 1024} КБ)"
        ))
