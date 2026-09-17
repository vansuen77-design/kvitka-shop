"""Applies or removes a discount on the whole catalog at once.

How it works in this project. A product has two prices: price — what we
sell at, old_price — struck out next to it. The discount is not stored as
a separate number: it is visible exactly when old_price is greater than
price, and the percentage is computed from the two.

So "apply −5%" means: write the current price as the old one and lower
the selling price by 5 percent.

    manage.py set_discount --percent 5      apply −5 % to everything
    manage.py set_discount --revert         remove: restore old prices
    manage.py set_discount --percent 5 --dry-run    only show

Removal restores the prices precisely because the old price is not made
up — it was the real price before the discount.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog.models import Product


class Command(BaseCommand):
    help = "Applies a discount to the whole catalog or removes it"

    def add_arguments(self, parser):
        parser.add_argument("--percent", type=int, default=0,
                            help="discount size in percent, e.g. 5")
        parser.add_argument("--revert", action="store_true",
                            help="remove the discount: restore old prices")
        parser.add_argument("--dry-run", action="store_true",
                            help="show what would happen and change nothing")

    def handle(self, *args, **options):
        percent, revert = options["percent"], options["revert"]
        if revert and percent:
            raise CommandError("Pick one: --percent or --revert.")
        if not revert and not 1 <= percent <= 90:
            raise CommandError("Give --percent from 1 to 90 or --revert.")

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
                        + (f" (was {new[1]})" if new[1] else " (discount removed)")
                    )
                if not dry:
                    product.price, product.old_price = new
                    product.save(update_fields=["price", "old_price", "updated_at"])
            if dry:
                transaction.set_rollback(True)

        if changed > 10:
            self.stdout.write(f"  … and {changed - 10} more")
        word = "shown" if dry else "changed"
        self.stdout.write(self.style.SUCCESS(f"Products {word}: {changed}."))

    @staticmethod
    def discount_price(product, percent: int):
        """The current price becomes the old one, the selling price drops by percent."""
        base = product.price or Decimal("0")
        if base <= 0:
            return None                      # no price — nothing to discount
        new = (base * (100 - percent) / 100).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP)
        if new <= 0 or new == base:
            return None                      # penny product: the discount would eat it all
        return new, base

    @staticmethod
    def revert_price(product):
        """Restores the price that was there before the discount."""
        if not product.old_price or product.old_price <= product.price:
            return None                      # this product had no discount
        return product.old_price, None
