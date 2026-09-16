"""Принимает базу из рабочей копии, сохраняя заказы покупателей.

Зачем. Товары, характеристики, страницы и фотографии удобнее вести
в копии на своём компьютере: там всё под рукой и не страшно ошибиться.
А заказы появляются только на боевом сайте — их с копии перенести
нельзя, иначе заказы, пришедшие за день, пропадут.

Как. Присланная база становится основной, но перед подменой мы
переносим в неё несколько таблиц из текущей:

    orders_order, orders_orderline        — сами заказы и их состав
    auth_user                           — чтобы не потерять доступ,
                                          если пароль меняли на сервере
    accounts_profile                    — анкеты покупателей
    django_session                      — чтобы вас не разлогинило

Избранное (accounts_favorite) переносится отдельно: оно ссылается на
товары, а товары в присланной базе — другие записи. Поэтому сверяем
не по номеру записи, а по артикулу; товар, которого в новом каталоге
не осталось, из избранного просто выпадает.

История действий в админке (django_admin_log) не переносится: она
ссылается на записи, которых в новой базе может не быть.

Запуск (сайт при этом должен быть остановлен):

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
    help = "Принимает базу из копии, сохраняя заказы и учётные записи"

    @staticmethod
    def move_favorites(con) -> dict:
        """Переносит избранное, пересчитывая ссылки на товары по артикулу.

        Номера записей в двух базах свои у каждой, поэтому копировать
        product_id как есть нельзя: сердечко уехало бы на чужой товар.
        """
        table = "accounts_favorite"
        if not table_exists(con, table) or not table_exists(con, table, "live"):
            return {}
        # артикул -> номер записи в присланном каталоге
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
                continue      # такого товара в новом каталоге нет
            con.execute(
                f"INSERT INTO main.{table} "
                "(user_id, product_id, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (user_id, product_id, created_at, updated_at),
            )
            kept += 1
        return {table: kept}

    def add_arguments(self, parser):
        parser.add_argument("incoming", help="путь к присланной базе")
        parser.add_argument(
            "--keep-incoming", action="store_true",
            help="не удалять присланный файл после переноса",
        )

    def handle(self, *args, **options):
        live = Path(settings.DATABASES["default"]["NAME"])
        incoming = Path(options["incoming"]).resolve()

        if not incoming.exists():
            raise CommandError(f"Не нашёл присланную базу: {incoming}")
        if not live.exists():
            raise CommandError(f"Не нашёл текущую базу: {live}")

        # 1. Обе базы должны быть на одной структуре, иначе перенос
        #    таблиц уткнётся в несовпадение колонок.
        here, there = migrations_of(live), migrations_of(incoming)
        if here != there:
            missing = sorted(f"{a}.{n}" for a, n in here - there)
            extra = sorted(f"{a}.{n}" for a, n in there - here)
            lines = ["Базы на разной структуре, перенос отменён."]
            if missing:
                lines.append("  В присланной нет: " + ", ".join(missing))
                lines.append("  Запустите копию — она применит миграции.")
            if extra:
                lines.append("  В присланной лишние: " + ", ".join(extra))
                lines.append("  Сначала отправьте код, потом данные.")
            raise CommandError("\n".join(lines))

        # 2. Пустая присланная база — почти наверняка ошибка,
        #    а не намерение стереть каталог.
        con = sqlite3.connect(incoming)
        try:
            products = con.execute("SELECT COUNT(*) FROM catalog_product").fetchone()[0]
        finally:
            con.close()
        if not products:
            raise CommandError(
                "В присланной базе ноль товаров — похоже, прислали пустую. "
                "Перенос отменён, каталог на сервере не тронут."
            )

        # 3. Переносим заказы и учётки из текущей базы в присланную.
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

        # 4. Текущую базу не удаляем, а откладываем с датой:
        #    если что-то пойдёт не так, вернуть её — одна команда.
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        saved = live.with_name(f"db.before-{stamp}.sqlite3")
        shutil.copy2(live, saved)
        shutil.copy2(incoming, live)
        if not options["keep_incoming"]:
            incoming.unlink()

        self.stdout.write(f"  Товаров принято: {products}")
        for table, count in moved.items():
            self.stdout.write(f"  Сохранено {table}: {count}")
        self.stdout.write(f"  Прежняя база отложена: {saved.name}")
        self.stdout.write(self.style.SUCCESS("Содержимое перенесено."))
