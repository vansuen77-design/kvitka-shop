"""adopt_content guards: different structure and empty catalog — refusal."""

import shutil
import sqlite3
import tempfile
from pathlib import Path

from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, override_settings


def make_db(path, migrations, products):
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE django_migrations (id INTEGER PRIMARY KEY, app TEXT, name TEXT)")
        conn.executemany("INSERT INTO django_migrations (app, name) VALUES (?, ?)", migrations)
        conn.execute("CREATE TABLE catalog_product (id INTEGER PRIMARY KEY, article TEXT)")
        conn.executemany("INSERT INTO catalog_product (article) VALUES (?)", [(a,) for a in products])


class AdoptContentGuardsTests(SimpleTestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.live = self.dir / "db.sqlite3"
        self.incoming = self.dir / "in.sqlite3"

    def adopt(self):
        with override_settings(DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3",
                                                      "NAME": self.live}}):
            call_command("adopt_content", str(self.incoming))

    def test_refuses_on_different_migrations(self):
        make_db(self.live, [("catalog", "0001_initial"), ("catalog", "0002_more")], ["A"])
        make_db(self.incoming, [("catalog", "0001_initial")], ["A"])
        with self.assertRaisesMessage(CommandError, "different structure"):
            self.adopt()

    def test_refuses_empty_catalog(self):
        make_db(self.live, [("catalog", "0001_initial")], ["A"])
        make_db(self.incoming, [("catalog", "0001_initial")], [])
        with self.assertRaisesMessage(CommandError, "zero products"):
            self.adopt()

    def test_refuses_missing_incoming(self):
        make_db(self.live, [("catalog", "0001_initial")], ["A"])
        with self.assertRaisesMessage(CommandError, "Incoming database not found"):
            self.adopt()
