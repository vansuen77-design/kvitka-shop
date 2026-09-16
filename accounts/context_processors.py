"""Что нужно каждой странице от кабинета.

Одним запросом достаём отмеченные товары — иначе каждая карточка в сетке
ходила бы в базу за своим сердечком (двенадцать запросов на страницу).
Гостю не достаём ничего.
"""

from __future__ import annotations

from accounts.models import Favorite


def cabinet(request) -> dict:
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {"favorite_ids": frozenset(), "favorites_count": 0}
    ids = frozenset(
        Favorite.objects.filter(user=user).values_list("product_id", flat=True)
    )
    return {"favorite_ids": ids, "favorites_count": len(ids)}
