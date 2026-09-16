"""Ставит и снимает скидку сразу на весь каталог.

Как это устроено в проекте. У товара две цены: price — по которой
продаём, old_price — перечёркнутая рядом. Скидка на сайте не хранится
отдельным числом: она видна ровно тогда, когда old_price больше price,
а процент считается из них двоих.

Поэтому «поставить −5%» означает: нынешнюю цену записать как старую,
а продажную опустить на 5 процентов.

    manage.py set_discount --percent 5      поставить −5 % на всё
    manage.py set_discount --revert         снять: вернуть старые цены
    manage.py set_discount --percent 5 --dry-run    только показать

Снятие возвращает цены обратно ровно потому, что старая цена не
выдумана, а была настоящей ценой до скидки.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog.models import Product


class Command(BaseCommand):
    help = "Ставит скидку на весь каталог или снимает её"

    def add_arguments(self, parser):
        parser.add_argument("--percent", type=int, default=0,
                            help="размер скидки в процентах, например 5")
        parser.add_argument("--revert", action="store_true",
                            help="снять скидку: вернуть старые цены")
        parser.add_argument("--dry-run", action="store_true",
                            help="показать, что получится, и ничего не менять")

    def handle(self, *args, **options):
        percent, revert = options["percent"], options["revert"]
        if revert and percent:
            raise CommandError("Выберите что-то одно: --percent или --revert.")
        if not revert and not 1 <= percent <= 90:
            raise CommandError("Укажите --percent от 1 до 90 или --revert.")

        dry = options["dry_run"]
        changed = 0
        with transaction.atomic():
            for product in Product.objects.all():
                new = self.revert_price(product) if revert \
                    else self.discount_price(product, percent)
                if new is None:
                    continue
                changed += 1
                if changed <= 10:
                    self.stdout.write(
                        f"  {product.article}: {product.price} → {new[0]}"
                        + (f" (было {new[1]})" if new[1] else " (скидка снята)")
                    )
                if not dry:
                    product.price, product.old_price = new
                    product.save(update_fields=["price", "old_price", "updated_at"])
            if dry:
                transaction.set_rollback(True)

        if changed > 10:
            self.stdout.write(f"  … и ещё {changed - 10}")
        word = "показано" if dry else "изменено"
        self.stdout.write(self.style.SUCCESS(f"Товаров {word}: {changed}."))

    @staticmethod
    def discount_price(product, percent: int):
        """Нынешняя цена становится старой, продажная падает на percent."""
        base = product.price or Decimal("0")
        if base <= 0:
            return None                      # цены нет — скидывать не с чего
        new = (base * (100 - percent) / 100).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP)
        if new <= 0 or new == base:
            return None                      # копеечный товар: скидка съела бы всё
        return new, base

    @staticmethod
    def revert_price(product):
        """Возвращает цену, которая была до скидки."""
        if not product.old_price or product.old_price <= product.price:
            return None                      # скидки на этом товаре не было
        return product.old_price, None
