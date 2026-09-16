"""Информационные страницы: «Доставка», «Оплата», «О магазине» и прочее.

Текст правится в админке, ссылки в подвале собираются из этой же таблицы —
добавили страницу, она сама появилась в нужной колонке.
"""

from django.db import models
from django.urls import reverse
from django.utils.translation import get_language

from core.models import NamedModel


class InfoPage(NamedModel):
    """Одна страница с текстом."""

    class Group(models.TextChoices):
        BUYER = "buyer", "Покупателю"
        PARTNER = "partner", "Компаниям"
        HIDDEN = "hidden", "Не показывать в подвале"

    group = models.CharField(
        "колонка в подвале", max_length=16,
        choices=Group.choices, default=Group.BUYER, db_index=True,
    )
    lead = models.CharField(
        "подзаголовок", max_length=300, blank=True,
        help_text="Одна строка под заголовком. Необязательно.",
    )
    lead_uk = models.CharField(
        "подзаголовок по-украински", max_length=300, blank=True,
        help_text="Если не заполнить, на украинской версии покажется русский.",
    )
    body = models.TextField(
        "текст",
        help_text="Обычный текст. Пустая строка разделяет абзацы, "
                  "строка, начинающаяся с «— », становится пунктом списка, "
                  "строка вида «## Заголовок» — подзаголовком.",
    )
    body_uk = models.TextField(
        "текст по-украински", blank=True,
        help_text="Разметка та же. Если не заполнить, на украинской версии "
                  "покажется русский текст.",
    )
    external_url = models.CharField(
        "внешняя ссылка", max_length=300, blank=True,
        help_text="Если заполнить, пункт в подвале ведёт сюда, "
                  "а не на страницу с текстом. Например, /price/xlsx/",
    )

    class Meta(NamedModel.Meta):
        verbose_name = "страница"
        verbose_name_plural = "страницы сайта"

    @property
    def lead_text(self) -> str:
        """Подзаголовок на языке посетителя."""
        if get_language() == "uk" and self.lead_uk:
            return self.lead_uk
        return self.lead

    @property
    def body_text(self) -> str:
        """Текст страницы на языке посетителя.

        Перевода нет - показываем русский: пустая страница хуже
        непереведённой.
        """
        if get_language() == "uk" and self.body_uk:
            return self.body_uk
        return self.body

    def get_absolute_url(self) -> str:
        if self.external_url:
            return self.external_url
        return reverse("pages:detail", kwargs={"slug": self.slug})

    def blocks(self) -> list[dict]:
        """Разбирает текст на абзацы, списки и подзаголовки."""
        result: list[dict] = []
        bullets: list[str] = []

        def flush() -> None:
            if bullets:
                result.append({"kind": "list", "items": list(bullets)})
                bullets.clear()

        for raw in self.body_text.splitlines():
            line = raw.strip()
            if not line:
                flush()
                continue
            if line.startswith("## "):
                flush()
                result.append({"kind": "title", "text": line[3:].strip()})
            elif line.startswith("— ") or line.startswith("- "):
                bullets.append(line[2:].strip())
            else:
                flush()
                result.append({"kind": "text", "text": line})
        flush()
        return result
