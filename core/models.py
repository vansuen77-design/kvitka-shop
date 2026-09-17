"""Base abstract models — the common foundation for all apps.

Only abstractions live here: subclasses are in catalog and orders.
"""

from django.db import models
from django.utils.translation import get_language

from core.utils import transliterate


class TimeStampedQuerySet(models.QuerySet):
    """QuerySet with lookups shared by all models."""

    def recent(self, limit: int = 10) -> "TimeStampedQuerySet":
        return self.order_by("-created_at")[:limit]


class ActivatableQuerySet(TimeStampedQuerySet):
    """QuerySet for models with an active flag."""

    def active(self) -> "ActivatableQuerySet":
        return self.filter(is_active=True)

    def hidden(self) -> "ActivatableQuerySet":
        return self.filter(is_active=False)


class TimeStampedModel(models.Model):
    """Stores creation and last-modification time of a record."""

    created_at = models.DateTimeField("создана", auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField("изменена", auto_now=True)

    objects = TimeStampedQuerySet.as_manager()

    class Meta:
        abstract = True
        ordering = ("-created_at",)


class NamedModel(TimeStampedModel):
    """Reference entry: name, slug, active flag, display order."""

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
        """Name in the visitor's language.

        Templates and views output this, not name: on the Ukrainian version
        name_uk is used, and if there is no translation the Russian name is
        shown honestly without breaking the page.
        """
        if get_language() == "uk" and self.name_uk:
            return self.name_uk
        return self.name

    def build_slug(self) -> str:
        """How to build the slug. Subclasses may override."""
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
