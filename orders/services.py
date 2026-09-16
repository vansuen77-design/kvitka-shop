"""Оформление заказа: одна функция, которую зовут и страница, и тесты.

Вынесено из представления, чтобы бизнес-логика (копирование строк,
язык, привязка к кабинету) не зависела от того, откуда пришёл заказ.
"""

from __future__ import annotations

from django.db import transaction
from django.utils.translation import get_language

from orders.models import Order, OrderLine


@transaction.atomic
def create_order(form, totals, user=None) -> Order:
    """Сохранить заказ из проверенной формы и строк корзины.

    Строки копируют артикул, название и цену на момент заказа
    (инвариант 5): товар потом могут переименовать или удалить,
    а заказ должен остаться читаемым.
    """
    order: Order = form.save(commit=False)
    order.status = Order.Status.NEW
    # запомним язык покупателя — письмо «заказ принят» уходит в фоне,
    # когда активного языка запроса уже нет
    order.language = (get_language() or "")[:5]
    # заказ оформляют и без кабинета; вошёл — привяжем, чтобы он
    # попал в «мои заказы»
    if user is not None and user.is_authenticated:
        order.user = user
    order.save()

    OrderLine.objects.bulk_create([
        OrderLine(
            order=order,
            product=line.product,
            article=line.product.article,
            # то же название, что покупатель видел в каталоге
            product_name=line.product.title,
            quantity=line.quantity,
            unit_price=line.unit_price,
        )
        for line in totals.lines
    ])
    order.recalculate()
    return order
