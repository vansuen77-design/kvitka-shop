"""Данные для сводки на главной странице админки."""

from decimal import Decimal

from django import template
from django.db.models import Count, Q, Sum

from catalog.models import Category, Kind, Product
from orders.models import Order

register = template.Library()

STATUS_PILL = {
    Order.Status.NEW: "pill--new",
    Order.Status.CONFIRMED: "pill--work",
    Order.Status.DELIVERING: "pill--work",
    Order.Status.DONE: "pill--ok",
    Order.Status.CANCELLED: "",
}


@register.simple_tag
def kvitka_stats() -> dict:
    """Четыре плитки над карточками разделов."""
    requests = Order.objects.aggregate(
        total=Count("id"),
        new=Count("id", filter=Q(status=Order.Status.NEW)),
        open_amount=Sum(
            "total_amount",
            filter=Q(status__in=[Order.Status.NEW, Order.Status.CONFIRMED,
                                 Order.Status.DELIVERING]),
        ),
    )
    products = Product.objects.aggregate(
        total=Count("id"),
        visible=Count("id", filter=Q(is_active=True)),
    )
    empty = Product.objects.filter(stock_quantity=0).count()
    return {
        "requests_total": requests["total"] or 0,
        "requests_new": requests["new"] or 0,
        "open_amount": requests["open_amount"] or Decimal("0"),
        "products_total": products["total"] or 0,
        "products_visible": products["visible"] or 0,
        "products_empty": empty,
        "categories": Category.objects.count(),
        "kinds": Kind.objects.count(),
    }


@register.simple_tag
def recent_orders(limit: int = 6):
    """Последние заказы — чтобы не искать их по разделам."""
    return list(Order.objects.all()[:limit])


@register.filter
def status_pill(status: str) -> str:
    return STATUS_PILL.get(status, "")
