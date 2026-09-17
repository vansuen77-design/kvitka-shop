"""snapshot_db: the snapshot reads as a database and never overwrites itself."""

import shutil
import sqlite3
import tempfile
from pathlib import Path

from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, override_settings


class SnapshotDbTests(SimpleTestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.live = self.dir / "db.sqlite3"
        with sqlite3.connect(self.live) as conn:
            conn.execute("CREATE TABLE t (x INTEGER)")
            conn.execute("INSERT INTO t VALUES (7)")

    def settings(self):
        return override_settings(DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3",
                                                        "NAME": self.live}})

    def test_snapshot_is_readable_copy(self):
        target = self.dir / "copy.sqlite3"
        with self.settings():
            call_command("snapshot_db", str(target))
        with sqlite3.connect(target) as conn:
            self.assertEqual(conn.execute("SELECT x FROM t").fetchone(), (7,))

    def test_refuses_to_overwrite_itself(self):
        with self.settings(), self.assertRaisesMessage(CommandError, "cannot overwrite the database itself"):
            call_command("snapshot_db", str(self.live))
