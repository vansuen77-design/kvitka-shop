"""Что происходит с товарами, когда удаляют характеристику.

Правило простое: справочник удалить можно всегда, но товары, которые на
него ссылались, снимаются с публикации. Они пропадают из каталога, из
поиска и из выгрузок, но остаются в базе с фотографиями и ценами —
вернуть их можно галкой «Показывать на сайте» в списке товаров.

Так сделано осознанно: удаление бренда не должно необратимо стирать
ассортимент из-за одного неверного клика.
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
    """Товары, привязанные к этому значению справочника."""
    related = getattr(obj, "products", None)
    if related is None:
        return Product.objects.none()
    queryset = related.all()
    if isinstance(obj, Category):
        # у раздела считаем и товары его подразделов
        queryset = Product.objects.filter(
            category__in=[obj.pk] + list(obj.children.values_list("pk", flat=True))
        )
    return queryset


def describe(obj) -> dict | None:
    """Текст предупреждения для страницы подтверждения удаления."""
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
    """Снимает товары с публикации. Возвращает, сколько сняли."""
    queryset = affected_products(obj).filter(is_active=True)
    articles = list(queryset.values_list("pk", flat=True))
    if not articles:
        return 0
    Product.objects.filter(pk__in=articles).update(is_active=False)
    return len(articles)


def is_reference(obj) -> bool:
    """Справочник ли это — то есть надо ли снимать товары с публикации."""
    from catalog.facets import BY_MODEL

    return type(obj) in BY_MODEL or isinstance(obj, (Category, Status))
