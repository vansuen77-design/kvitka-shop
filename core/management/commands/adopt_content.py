"""Adopts a database from the working copy while keeping customer orders.

Why. Products, attributes, pages and photos are easier to maintain in the
local copy on your computer: everything is at hand and mistakes are cheap.
Orders, however, appear only on the live site — they cannot be brought
from the copy, otherwise the orders that arrived during the day would be lost.

How. The incoming database becomes the main one, but before the swap we
move several tables from the current one into it:

    orders_order, orders_orderline      — the orders and their lines
    auth_user                           — so access is not lost if the
                                          password was changed on the server
    accounts_profile                    — customer profiles
    django_session                      — so you are not logged out

Favourites (accounts_favorite) are moved separately: they reference
products, and products in the incoming database are different records.
So they are matched by article rather than by record id; a product that no
longer exists in the new catalog simply drops out of the favourites.

The admin action log (django_admin_log) is not moved: it references
records that may not exist in the new database.

Run (the site must be stopped meanwhile):

    manage.py adopt_content db.incoming.sqlite3
"""

from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

PRESERVE = ["orders_order", "orders_orderline", "auth_user",
            "accounts_profile", "django_session"]
CLEAR = ["django_admin_log"]


def table_exists(con: sqlite3.Connection, name: str, schema: str = "main") -> bool:
    row = con.execute(
        f"SELECT 1 FROM {schema}.sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return row is not None


def migrations_of(path: Path) -> set:
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return set(con.execute("SELECT app, name FROM django_migrations"))
    finally:
        con.close()


class Command(BaseCommand):
    help = "Adopts a database from the local copy, keeping orders and accounts"

    @staticmethod
    def move_favorites(con) -> dict:
        """Moves favourites, remapping product references by article.

        Record ids differ between the two databases, so product_id cannot be
        copied as is: the heart would land on someone else's product.
        """
        table = "accounts_favorite"
        if not table_exists(con, table) or not table_exists(con, table, "live"):
            return {}
        # article -> record id in the incoming catalog
        target = {
            article: pk for pk, article
            in con.execute("SELECT id, article FROM main.catalog_product")
        }
        rows = con.execute(
            "SELECT f.user_id, p.article, f.created_at, f.updated_at "
            "FROM live.accounts_favorite f "
            "JOIN live.catalog_product p ON p.id = f.product_id"
        ).fetchall()
        con.execute(f"DELETE FROM main.{table}")
        kept = 0
        for user_id, article, created_at, updated_at in rows:
            product_id = target.get(article)
            if product_id is None:
                continue      # no such product in the new catalog
            con.execute(
                f"INSERT INTO main.{table} "
                "(user_id, product_id, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (user_id, product_id, created_at, updated_at),
            )
            kept += 1
        return {table: kept}

    def add_arguments(self, parser):
        parser.add_argument("incoming", help="path to the incoming database")
        parser.add_argument(
            "--keep-incoming", action="store_true",
            help="do not delete the incoming file after adoption",
        )

    def handle(self, *args, **options):
        live = Path(settings.DATABASES["default"]["NAME"])
        incoming = Path(options["incoming"]).resolve()

        if not incoming.exists():
            raise CommandError(f"Incoming database not found: {incoming}")
        if not live.exists():
            raise CommandError(f"Current database not found: {live}")

        # 1. Both databases must have the same structure, otherwise moving
        #    tables runs into mismatched columns.
        here, there = migrations_of(live), migrations_of(incoming)
        if here != there:
            missing = sorted(f"{a}.{n}" for a, n in here - there)
            extra = sorted(f"{a}.{n}" for a, n in there - here)
            lines = ["Databases have different structure, adoption cancelled."]
            if missing:
                lines.append("  Missing in the incoming one: " + ", ".join(missing))
                lines.append("  Run the local copy — it applies the migrations.")
            if extra:
                lines.append("  Extra in the incoming one: " + ", ".join(extra))
                lines.append("  Deploy the code first, then the data.")
            raise CommandError("\n".join(lines))

        # 2. An empty incoming database is almost certainly a mistake,
        #    not an intention to wipe the catalog.
        con = sqlite3.connect(incoming)
        try:
            products = con.execute("SELECT COUNT(*) FROM catalog_product").fetchone()[0]
        finally:
            con.close()
        if not products:
            raise CommandError(
                "The incoming database has zero products — looks like an empty one. "
                "Adoption cancelled, the catalog on the server is untouched."
            )

        # 3. Move orders and accounts from the current database into the incoming one.
        con = sqlite3.connect(incoming)
        moved = {}
        try:
            con.execute("PRAGMA foreign_keys = OFF")
            con.execute("ATTACH DATABASE ? AS live", (str(live),))
            for table in PRESERVE:
                if not table_exists(con, table) or not table_exists(con, table, "live"):
                    continue
                con.execute(f"DELETE FROM main.{table}")
                con.execute(f"INSERT INTO main.{table} SELECT * FROM live.{table}")
                moved[table] = con.execute(
                    f"SELECT COUNT(*) FROM main.{table}").fetchone()[0]
            for table in CLEAR:
                if table_exists(con, table):
                    con.execute(f"DELETE FROM main.{table}")
            moved.update(self.move_favorites(con))
            con.commit()
            con.execute("DETACH DATABASE live")
        finally:
            con.close()

        # 4. The current database is not deleted but set aside with a date:
        #    if something goes wrong, restoring it is one command.
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        saved = live.with_name(f"db.before-{stamp}.sqlite3")
        shutil.copy2(live, saved)
        shutil.copy2(incoming, live)
        if not options["keep_incoming"]:
            incoming.unlink()

        self.stdout.write(f"  Products adopted: {products}")
        for table, count in moved.items():
            self.stdout.write(f"  Kept {table}: {count}")
        self.stdout.write(f"  Previous database set aside: {saved.name}")
        self.stdout.write(self.style.SUCCESS("Content adopted."))
