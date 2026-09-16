"""Базовые абстрактные модели — общий фундамент для всех приложений.

Здесь живут только абстракции: наследники находятся в catalog и orders.
"""

from django.db import models
from django.utils.translation import get_language

from core.utils import transliterate


class TimeStampedQuerySet(models.QuerySet):
    """QuerySet с общими для всех моделей выборками."""

    def recent(self, limit: int = 10) -> "TimeStampedQuerySet":
        return self.order_by("-created_at")[:limit]


class ActivatableQuerySet(TimeStampedQuerySet):
    """QuerySet для моделей с флагом активности."""

    def active(self) -> "ActivatableQuerySet":
        return self.filter(is_active=True)

    def hidden(self) -> "ActivatableQuerySet":
        return self.filter(is_active=False)


class TimeStampedModel(models.Model):
    """Хранит время создания и последнего изменения записи."""

    created_at = models.DateTimeField("создана", auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField("изменена", auto_now=True)

    objects = TimeStampedQuerySet.as_manager()

    class Meta:
        abstract = True
        ordering = ("-created_at",)


class NamedModel(TimeStampedModel):
    """Справочник: название, ЧПУ-адрес, признак активности, порядок вывода."""

    name = models.CharField("название", max_length=160)
    name_uk = models.CharField(
        "название по-украински", max_length=160, blank=True,
        help_text="Если не заполнить, на украинской версии сайта "
                  "покажется русское название.",
    )
    slug = models.SlugField("адрес", max_length=180, unique=True, blank=True)
    is_active = models.BooleanField("показывать", default=True, db_index=True)
    position = models.PositiveSmallIntegerField("порядок", default=100)

    objects = ActivatableQuerySet.as_manager()

    class Meta:
        abstract = True
        ordering = ("position", "name")

    def __str__(self) -> str:
        return self.name

    @property
    def title(self) -> str:
        """Название на языке посетителя.

        В шаблонах и представлениях выводим именно его, а не name:
        на украинской версии сайта берём name_uk, а если перевода нет —
        честно показываем русское название, но страницу не ломаем.
        """
        if get_language() == "uk" and self.name_uk:
            return self.name_uk
        return self.name

    def build_slug(self) -> str:
        """Как построить адрес. Наследники могут переопределить."""
        return transliterate(self.name) or "item"

    def save(self, *args, **kwargs):
        if not self.slug:
            base = self.build_slug()
            candidate, counter = base, 2
            model = type(self)
            while model.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = f"{base}-{counter}"
                counter += 1
            self.slug = candidate
        super().save(*args, **kwargs)
