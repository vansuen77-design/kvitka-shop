"""Test factories: create records with sensible defaults.

No shop constants here: prices, thresholds and names are set in the tests
themselves or read from settings.SHOP.
"""

from __future__ import annotations

import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model

from catalog.models import (
    Category, Color, Flower, Kind, Occasion, Product, ProductImage, Size, Status,
)

_counter = itertools.count(1)


def next_id() -> int:
    return next(_counter)


def make_category(name="Розділ", parent=None, **extra) -> Category:
    return Category.objects.create(name=name, name_uk=extra.pop("name_uk", name),
                                   parent=parent, **extra)


def make_status(name="В наличии", slug="", orderable=True, **extra) -> Status:
    return Status.objects.create(name=name, name_uk=extra.pop("name_uk", name),
                                 slug=slug, is_orderable=orderable, **extra)


def make_value(model, name, slug="", position=100, name_uk=None):
    return model.objects.create(name=name, name_uk=name_uk if name_uk is not None else name,
                                slug=slug, position=position)


def make_product(name="Букет", price="500", stock=10, category=None, status=None,
                 flowers=(), occasions=(), **extra) -> Product:
    number = next_id()
    if extra.get("old_price") is not None:
        extra["old_price"] = Decimal(str(extra["old_price"]))
    product = Product.objects.create(
        article=extra.pop("article", f"T-{number}"),
        name=name,
        name_uk=extra.pop("name_uk", f"{name} uk"),
        category=category,
        status=status,
        price=Decimal(str(price)),
        stock_quantity=stock,
        **extra,
    )
    if flowers:
        product.flowers.set(flowers)
    if occasions:
        product.occasions.set(occasions)
    return product


def make_photo(product: Product) -> ProductImage:
    """A photo record without a file on disk — has_photo only needs the path."""
    return ProductImage.objects.create(product=product, image="products/test.png", position=1)


def make_user(email="buyer@example.com", password="secret-pass-123", name="Тест"):
    User = get_user_model()
    return User.objects.create_user(username=email, email=email, password=password,
                                    first_name=name)


__all__ = ["make_category", "make_status", "make_value", "make_product", "make_photo",
           "make_user", "Color", "Flower", "Kind", "Occasion", "Size"]
