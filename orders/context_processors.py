"""The cart and shop settings are available in every template."""

from django.conf import settings
from django.utils.translation import get_language

from orders.cart import Cart


def shop_settings() -> dict:
    """Shop settings adjusted for the page language.

    The florist's name and the city are ordinary words, not UI labels, so
    they do not belong in the translation file. Ukrainian variants are kept
    next to the Russian ones in SHOP: a key with the _UK suffix replaces
    the main one when the visitor views the Ukrainian version.
    """
    values = dict(settings.SHOP)
    if get_language() == "uk":
        for key, value in settings.SHOP.items():
            if key.endswith("_UK") and value:
                values[key[:-3]] = value
    return values


def cart_summary(request) -> dict:
    """The cart and shop settings — into every template.

    There may be no session: error pages are sometimes rendered before
    SessionMiddleware has run. This used to crash the 404 page — instead of
    "page not found" the visitor saw "something broke on our side".
    So without a session an empty cart is simply shown.
    """
    if not hasattr(request, "session"):
        return {"cart_totals": None, "shop": shop_settings()}
    cart = Cart(request)
    return {
        "cart_totals": cart.totals,
        "shop": shop_settings(),
    }
