"""Заказы.

Оплаты на сайте нет: покупатель собирает корзину, указывает, куда и когда
привезти букет, а флорист перезванивает и подтверждает. Всё, что он ввёл,
попадает сюда и видно в админке.

Автор кода: ISHOD, 2026. Все права на исходный код принадлежат автору.
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_noop

from catalog.models import Product
from core.models import TimeStampedModel


class OrderQuerySet(models.QuerySet):
    def new(self) -> "OrderQuerySet":
        return self.filter(status=Order.Status.NEW)

    def open(self) -> "OrderQuerySet":
        return self.filter(status__in=[Order.Status.NEW, Order.Status.CONFIRMED,
                                       Order.Status.DELIVERING])


class Order(TimeStampedModel):
    """Заказ с доставкой. Флорист связывается с покупателем сам."""

    class Status(models.TextChoices):
        NEW = "new", "Новый"
        CONFIRMED = "confirmed", "Подтверждён"
        DELIVERING = "delivering", "Доставляется"
        DONE = "done", "Выполнен"
        CANCELLED = "cancelled", "Отменён"

    # Подписи ниже показываются покупателю, поэтому помечены для перевода:
    # gettext_noop только даёт makelocales найти строку, а переводит форма
    class Delivery(models.TextChoices):
        COURIER = "courier", gettext_noop("Курьером по городу")
        PICKUP = "pickup", gettext_noop("Самовывоз из магазина")

    class Payment(models.TextChoices):
        CASH = "cash", gettext_noop("Наличными при получении")
        CARD = "card", gettext_noop("Переводом на карту")

    class TimeSlot(models.TextChoices):
        MORNING = "09-12", "09:00–12:00"
        NOON = "12-15", "12:00–15:00"
        AFTERNOON = "15-18", "15:00–18:00"
        EVENING = "18-21", "18:00–21:00"

    # Заказ можно оформить и без кабинета — поэтому null. Если человек
    # вошёл, ставим ссылку: по ней он видит свою историю заказов.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="кабинет покупателя",
        on_delete=models.SET_NULL, related_name="orders",
        null=True, blank=True,
    )
    name = models.CharField("имя", max_length=120)
    phone = models.CharField("телефон", max_length=40)
    email = models.EmailField("почта", blank=True)

    # --- доставка ---------------------------------------------------------
    delivery = models.CharField(
        "доставка", max_length=16, choices=Delivery.choices,
        default=Delivery.COURIER,
    )
    address = models.CharField("адрес доставки", max_length=300, blank=True)
    delivery_date = models.DateField("дата доставки", null=True, blank=True)
    delivery_time = models.CharField(
        "время", max_length=8, choices=TimeSlot.choices, blank=True,
    )
    recipient_name = models.CharField(
        "получатель", max_length=120, blank=True,
        help_text="Если букет — подарок и получает его другой человек.",
    )
    recipient_phone = models.CharField("телефон получателя", max_length=40, blank=True)
    card_text = models.CharField(
        "текст открытки", max_length=300, blank=True,
        help_text="Что написать на открытке к букету.",
    )
    payment = models.CharField(
        "оплата", max_length=16, choices=Payment.choices, default=Payment.CASH,
    )
    comment = models.TextField("комментарий покупателя", blank=True)
    # Язык, на котором покупатель оформлял заказ: письмо «заказ принят»
    # уходит в фоне, когда активного языка запроса уже нет
    language = models.CharField("язык сайта", max_length=5, blank=True)

    status = models.CharField(
        "статус", max_length=16, choices=Status.choices,
        default=Status.NEW, db_index=True,
    )
    manager_note = models.TextField("заметка флориста", blank=True)

    # --- суммы на момент заказа -------------------------------------------
    total_quantity = models.PositiveIntegerField("всего штук", default=0)
    goods_amount = models.DecimalField(
        "товары на сумму", max_digits=11, decimal_places=2, default=Decimal("0"),
    )
    delivery_cost = models.DecimalField(
        "доставка", max_digits=9, decimal_places=2, default=Decimal("0"),
    )
    total_amount = models.DecimalField(
        "итого", max_digits=11, decimal_places=2, default=Decimal("0"),
    )

    objects = OrderQuerySet.as_manager()

    class Meta:
        verbose_name = "заказ"
        verbose_name_plural = "заказы"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.number} · {self.name}"

    @property
    def number(self) -> str:
        return f"№{self.pk:05d}" if self.pk else "№—"

    @property
    def is_open(self) -> bool:
        return self.status in (self.Status.NEW, self.Status.CONFIRMED,
                               self.Status.DELIVERING)

    @property
    def is_pickup(self) -> bool:
        return self.delivery == self.Delivery.PICKUP

    @property
    def is_free_delivery(self) -> bool:
        return not self.is_pickup and self.delivery_cost == 0

    @staticmethod
    def delivery_cost_for(delivery: str, goods_amount) -> Decimal:
        """Стоимость доставки по правилам магазина.

        Самовывоз бесплатен. Курьер — по тарифу из настроек, а от порога
        FREE_DELIVERY_FROM бесплатно. Пороги читаются из settings.SHOP,
        чтобы тесты и полоса прогресса в корзине считали одно и то же.
        """
        if delivery == Order.Delivery.PICKUP:
            return Decimal("0")
        threshold = Decimal(settings.SHOP["FREE_DELIVERY_FROM"])
        if Decimal(goods_amount) >= threshold:
            return Decimal("0")
        return Decimal(settings.SHOP["DELIVERY_COST"])

    def recalculate(self) -> None:
        lines = list(self.lines.all())
        self.total_quantity = sum(line.quantity for line in lines)
        self.goods_amount = sum(
            (line.amount for line in lines), Decimal("0")
        ).quantize(Decimal("0.01"))
        self.delivery_cost = self.delivery_cost_for(self.delivery, self.goods_amount)
        self.total_amount = (self.goods_amount + self.delivery_cost).quantize(Decimal("0.01"))
        self.save(update_fields=["total_quantity", "goods_amount", "delivery_cost",
                                 "total_amount", "updated_at"])


class OrderLine(TimeStampedModel):
    """Строка заказа. Название и цена сохраняются на момент заказа —
    чтобы через месяц было видно, о чём договаривались."""

    order = models.ForeignKey(
        Order, verbose_name="заказ", on_delete=models.CASCADE,
        related_name="lines",
    )
    product = models.ForeignKey(
        Product, verbose_name="товар", on_delete=models.SET_NULL,
        related_name="order_lines", null=True, blank=True,
    )
    article = models.CharField("артикул", max_length=32)
    product_name = models.CharField("название", max_length=200)
    quantity = models.PositiveIntegerField("количество, штук")
    unit_price = models.DecimalField("цена за штуку", max_digits=9, decimal_places=2)

    class Meta:
        verbose_name = "строка заказа"
        verbose_name_plural = "строки заказа"
        ordering = ("id",)

    def __str__(self) -> str:
        return f"{self.article} × {self.quantity} шт"

    @property
    def amount(self) -> Decimal:
        return (self.unit_price * self.quantity).quantize(Decimal("0.01"))
