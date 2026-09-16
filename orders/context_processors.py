"""Корзина и настройки магазина доступны в любом шаблоне."""

from django.conf import settings
from django.utils.translation import get_language

from orders.cart import Cart


def shop_settings() -> dict:
    """Настройки магазина с поправкой на язык страницы.

    Имя флориста и город — это обычные слова, а не подписи интерфейса,
    поэтому в файле переводов им не место. Держим украинские варианты
    рядом с русскими в SHOP: ключ с суффиксом _UK подменяет основной,
    когда посетитель смотрит украинскую версию.
    """
    values = dict(settings.SHOP)
    if get_language() == "uk":
        for key, value in settings.SHOP.items():
            if key.endswith("_UK") and value:
                values[key[:-3]] = value
    return values


def cart_summary(request) -> dict:
    """Корзина и настройки магазина — в каждый шаблон.

    Сессии может не быть: страницы ошибок иногда рендерятся раньше, чем
    отработал SessionMiddleware. Раньше это роняло страницу 404 — вместо
    «страницы нет» посетитель видел «сломалось на нашей стороне».
    Поэтому без сессии просто показываем пустую корзину.
    """
    if not hasattr(request, "session"):
        return {"cart_totals": None, "shop": shop_settings()}
    cart = Cart(request)
    return {
        "cart_totals": cart.totals,
        "shop": shop_settings(),
    }
