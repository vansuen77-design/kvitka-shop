"""Корзина — то, что покупатель набрал, но ещё не оформил.

Живёт в сессии. Структура хранения:

    {"<id товара>": количество штук}

Товар продаётся поштучно, поэтому позиция — это просто количество.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from django.conf import settings

from catalog.models import Product
from core.utils import format_money


@dataclass
class CartLine:
    """Одна позиция корзины."""

    product: Product
    quantity: int

    @property
    def product_id(self) -> int:
        return self.product.pk

    @property
    def unit_price(self) -> Decimal:
        return self.product.price

    @property
    def amount(self) -> Decimal:
        return self.product.amount_for(self.quantity)

    def as_dict(self) -> dict:
        return {
            "product": self.product_id,
            "article": self.product.article,
            "name": self.product.title,
            "quantity": self.quantity,
            "amount": float(self.amount),
            "amount_label": f"{format_money(self.amount)} ₴",
        }


@dataclass
class CartTotals:
    positions: int = 0
    quantity: int = 0
    amount: Decimal = Decimal("0")
    lines: list[CartLine] = field(default_factory=list)

    # --- бесплатная доставка ---------------------------------------------
    # Порог и тариф читаются из settings.SHOP при каждом обращении, а не
    # запоминаются при импорте: тесты меняют порог через override_settings,
    # и полоса прогресса обязана это увидеть (грабля 23).
    @property
    def free_delivery_from(self) -> Decimal:
        return Decimal(settings.SHOP["FREE_DELIVERY_FROM"])

    @property
    def free_delivery_reached(self) -> bool:
        return bool(self.lines) and self.amount >= self.free_delivery_from

    @property
    def free_delivery_gap(self) -> Decimal:
        return max(self.free_delivery_from - self.amount, Decimal("0"))

    @property
    def free_delivery_progress(self) -> int:
        threshold = self.free_delivery_from
        if threshold <= 0:
            return 100
        return min(int(self.amount / threshold * 100), 100)

    @property
    def courier_cost(self) -> Decimal:
        """Сколько будет стоить курьер при текущей сумме."""
        from orders.models import Order

        return Order.delivery_cost_for(Order.Delivery.COURIER, self.amount)

    def as_dict(self) -> dict:
        return {
            "positions": self.positions,
            "quantity": self.quantity,
            "amount": float(self.amount),
            "amount_label": f"{format_money(self.amount)} ₴",
            "free_delivery_reached": self.free_delivery_reached,
            "free_delivery_progress": self.free_delivery_progress,
            "free_delivery_gap_label": f"{format_money(self.free_delivery_gap)} ₴",
            "courier_cost": float(self.courier_cost),
            "courier_cost_label": f"{format_money(self.courier_cost)} ₴",
        }


class Cart:
    """Обёртка над сессией. Views и шаблоны работают только с ней."""

    session_key = settings.CART_SESSION_KEY

    def __init__(self, request) -> None:
        self.session = request.session
        self._data: dict = self.session.setdefault(self.session_key, {})
        self._totals: CartTotals | None = None

    # --- запись ----------------------------------------------------------
    def _save(self) -> None:
        self.session[self.session_key] = self._data
        self.session.modified = True
        self._totals = None

    def add(self, product, quantity: int) -> int:
        """Добавляет количество к позиции и возвращает итог по ней.

        Принимаем именно товар, а не его номер: сумма «было плюс стало»
        тоже обязана уложиться в остаток, а знает об этом только он.
        """
        current = int(self._data.get(str(product.pk), 0))
        total = product.normalize_quantity(current + int(quantity))
        self.set_quantity(product.pk, total)
        return total

    def set_quantity(self, product_id: int, quantity: int) -> None:
        quantity = max(int(quantity), 0)
        if quantity:
            self._data[str(product_id)] = quantity
        else:
            self._data.pop(str(product_id), None)
        self._save()

    def remove(self, product_id: int) -> None:
        self._data.pop(str(product_id), None)
        self._save()

    def clear(self) -> None:
        self._data = {}
        self._save()

    # --- чтение ----------------------------------------------------------
    def _build(self) -> CartTotals:
        totals = CartTotals()
        if not self._data:
            return totals

        product_ids = [int(key) for key in self._data if key.isdigit()]
        products = {
            product.pk: product
            for product in Product.objects.filter(pk__in=product_ids, is_active=True)
            .select_related("category", "status", "size")
            .prefetch_related("images")
        }

        for key, raw_quantity in self._data.items():
            product = products.get(int(key)) if key.isdigit() else None
            if product is None:
                continue
            # чиним на лету старые корзины и позиции, у которых за это
            # время уменьшился остаток
            quantity = product.normalize_quantity(raw_quantity)
            if quantity <= 0:
                continue
            line = CartLine(product=product, quantity=quantity)
            totals.lines.append(line)
            totals.quantity += line.quantity
            totals.amount += line.amount

        totals.positions = len(totals.lines)
        return totals

    @property
    def totals(self) -> CartTotals:
        if self._totals is None:
            self._totals = self._build()
        return self._totals

    def __iter__(self):
        return iter(self.totals.lines)

    def __len__(self) -> int:
        return self.totals.positions

    def __bool__(self) -> bool:
        return bool(self._data)

    def as_dict(self) -> dict:
        totals = self.totals
        return {**totals.as_dict(), "lines": [line.as_dict() for line in totals.lines]}
