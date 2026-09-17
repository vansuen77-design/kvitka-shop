"""What happens to products when an attribute value is deleted.

The rule is simple: a reference value can always be deleted, but the
products that referenced it are unpublished. They vanish from the catalog,
search and exports, but stay in the database with photos and prices —
they can be brought back with the "Show on site" checkbox in the product list.

This is deliberate: deleting a reference value must not irreversibly wipe
out part of the range because of one wrong click.
"""

from __future__ import annotations

from catalog.models import Category, Product, Status

PLURALS = ("товар", "товара", "товаров")


def plural(count: int, forms=PLURALS) -> str:
    if count % 10 == 1 and count % 100 != 11:
        return forms[0]
    if 2 <= count % 10 <= 4 and not 12 <= count % 100 <= 14:
        return forms[1]
    return forms[2]


def affected_products(obj):
    """Products linked to this reference value."""
    related = getattr(obj, "products", None)
    if related is None:
        return Product.objects.none()
    queryset = related.all()
    if isinstance(obj, Category):
        # for a category, products of its subcategories count too
        queryset = Product.objects.filter(
            category__in=[obj.pk] + list(obj.children.values_list("pk", flat=True))
        )
    return queryset


def describe(obj) -> dict | None:
    """Warning text for the delete confirmation page."""
    queryset = affected_products(obj)
    total = queryset.count()
    if not total:
        return None
    published = queryset.filter(is_active=True).count()
    articles = list(queryset.values_list("article", flat=True)[:12])
    return {
        "total": total,
        "published": published,
        "articles": articles,
        "more": max(total - len(articles), 0),
        "title": f"К значению «{obj}» привязано {total} {plural(total)}",
    }


def unpublish_products(obj) -> int:
    """Unpublishes the products. Returns how many were unpublished."""
    queryset = affected_products(obj).filter(is_active=True)
    articles = list(queryset.values_list("pk", flat=True))
    if not articles:
        return 0
    Product.objects.filter(pk__in=articles).update(is_active=False)
    return len(articles)


def is_reference(obj) -> bool:
    """Is this a reference value — i.e. should products be unpublished."""
    from catalog.facets import BY_MODEL

    return type(obj) in BY_MODEL or isinstance(obj, (Category, Status))
