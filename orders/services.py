"""Checkout: one function called by both the page and the tests.

Moved out of the view so that the business logic (copying lines,
language, linking to the account) does not depend on where the order
came from.
"""

from __future__ import annotations

from django.db import transaction
from django.utils.translation import get_language

from orders.models import Order, OrderLine


@transaction.atomic
def create_order(form, totals, user=None) -> Order:
    """Save an order from a validated form and the cart lines.

    Lines copy the article, name and price at the time of the order: the
    product may later be renamed or deleted, and the order must stay readable.
    """
    order: Order = form.save(commit=False)
    order.status = Order.Status.NEW
    # remember the customer's language — the "order accepted" e-mail is
    # sent in the background, when the request language is no longer active
    order.language = (get_language() or "")[:5]
    # orders are placed without an account too; logged in — link it so
    # that it shows up in "my orders"
    if user is not None and user.is_authenticated:
        order.user = user
    order.save()

    OrderLine.objects.bulk_create([
        OrderLine(
            order=order,
            product=line.product,
            article=line.product.article,
            # the same name the customer saw in the catalog
            product_name=line.product.title,
            quantity=line.quantity,
            unit_price=line.unit_price,
        )
        for line in totals.lines
    ])
    order.recalculate()
    return order
