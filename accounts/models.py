"""Кабинет покупателя: анкета и избранное.

Своей модели пользователя мы не заводим — берём стандартную Django,
а телефон и адрес доставки держим рядом в анкете.
Так остаются целыми админка, смена пароля и восстановление доступа,
которые Django уже умеет.

Вход по почте: username мы заполняем той же почтой, а сверяет
их accounts/backends.py.

Автор кода: ISHOD, 2026. Все права на исходный код принадлежат автору.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_noop

from catalog.models import Product
from core.models import TimeStampedModel


class Profile(TimeStampedModel):
    """Данные покупателя, которые подставляются в заказ."""

    # подписи показываются покупателю — помечены для makelocales
    class Contact(models.TextChoices):
        PHONE = "phone", gettext_noop("Звонок")
        TELEGRAM = "telegram", "Telegram"
        VIBER = "viber", "Viber"
        EMAIL = "email", gettext_noop("Почта")

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, verbose_name="пользователь",
        on_delete=models.CASCADE, related_name="profile",
    )
    phone = models.CharField("телефон", max_length=40, blank=True)
    address = models.CharField("адрес доставки", max_length=300, blank=True)
    preferred_contact = models.CharField(
        "удобная связь", max_length=16,
        choices=Contact.choices, default=Contact.PHONE,
    )

    class Meta:
        verbose_name = "анкета покупателя"
        verbose_name_plural = "анкеты покупателей"

    def __str__(self) -> str:
        return f"анкета {self.user.get_username()}"

    @property
    def display_name(self) -> str:
        return self.user.first_name or self.user.get_username()

    def as_order_initial(self) -> dict:
        """Чем заполнить форму заказа, когда человек уже вошёл."""
        return {
            "name": self.user.first_name,
            "phone": self.phone,
            "email": self.user.email,
            "address": self.address,
        }


class Favorite(TimeStampedModel):
    """Товар, отмеченный сердечком."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="покупатель",
        on_delete=models.CASCADE, related_name="favorites",
    )
    product = models.ForeignKey(
        Product, verbose_name="товар",
        on_delete=models.CASCADE, related_name="favorited_by",
    )

    class Meta:
        verbose_name = "избранный товар"
        verbose_name_plural = "избранные товары"
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("user", "product"), name="unique_favorite_per_user"
            )
        ]

    def __str__(self) -> str:
        return f"{self.user.get_username()} · {self.product.article}"
