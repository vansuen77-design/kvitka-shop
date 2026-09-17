"""Catalog models.

Inheritance hierarchy:
    models.Model
      └── TimeStampedModel (core)
            └── NamedModel (core)
                  ├── Category, Status, filter reference models
                  └── Product

Products are sold by the piece: a bouquet is one item, one price per
product, stock is a single number. Variants of one bouquet (11 / 25 / 51
roses) are separate products linked by the family field: each has its own
article, price and stock, and the product page shows a size switcher.

Code by ISHOD, 2026. All rights to the source code belong to the author.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import models
from django.utils.translation import get_language, gettext as _
from django.urls import reverse

from catalog.managers import CategoryQuerySet, ProductManager
from core.models import ActivatableQuerySet, NamedModel, TimeStampedModel
from core.utils import transliterate


class Category(NamedModel):
    """Catalog category. Supports one level of nesting."""

    parent = models.ForeignKey(
        "self",
        verbose_name="родительский раздел",
        on_delete=models.CASCADE,
        related_name="children",
        null=True,
        blank=True,
        help_text="Пусто — раздел верхнего уровня, он попадёт в меню сайта.",
    )
    description = models.TextField("описание раздела", blank=True)

    objects = CategoryQuerySet.as_manager()

    class Meta(NamedModel.Meta):
        verbose_name = "раздел каталога"
        verbose_name_plural = "разделы каталога"

    def __str__(self) -> str:
        if self.parent_id:
            return f"{self.parent.name} · {self.name}"
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("catalog:category", args=[self.slug])

    @property
    def is_root(self) -> bool:
        return self.parent_id is None


class Status(NamedModel):
    """Product status: "In stock", "On order", "New", "Discontinued".

    The list is edited in the admin — custom ones can be added.
    """

    color = models.CharField(
        "цвет плашки", max_length=7, default="#4A6B45",
        help_text="HEX, например #4A6B45. Этим цветом красится плашка на карточке.",
    )
    is_orderable = models.BooleanField(
        "можно добавить в корзину", default=True,
        help_text="Снимите галку для статусов вроде «Снят с продажи».",
    )
    note = models.CharField(
        "пояснение", max_length=120, blank=True,
        help_text="Показывается мелким шрифтом рядом со статусом.",
    )

    class Meta(NamedModel.Meta):
        verbose_name = "статус товара"
        verbose_name_plural = "статусы товаров"


class AttributeModel(NamedModel):
    """Common base for the reference models the catalog is filtered by.

    They are all alike: name, order, shown or not. The owner adds values
    in the admin, the filter in the catalog appears by itself.
    """

    class Meta(NamedModel.Meta):
        abstract = True


class Kind(AttributeModel):
    """Product type: bouquet, box arrangement, basket, potted plant."""

    class Meta(AttributeModel.Meta):
        verbose_name = "тип товара"
        verbose_name_plural = "типы товаров"


class Flower(AttributeModel):
    """Flower: rose, tulip, peony, chrysanthemum.

    Multi-valued: a mixed bouquet has several flowers.
    """

    class Meta(AttributeModel.Meta):
        verbose_name = "цветок"
        verbose_name_plural = "цветы"


class Occasion(AttributeModel):
    """Occasion: birthday, wedding, 8 March. A bouquet may have several."""

    class Meta(AttributeModel.Meta):
        verbose_name = "повод"
        verbose_name_plural = "поводы"


class Color(AttributeModel):
    """Main colour of the bouquet: red, pink, white, mix."""

    class Meta(AttributeModel.Meta):
        verbose_name = "цвет"
        verbose_name_plural = "цвета"


class Size(AttributeModel):
    """Bouquet size: small (S), medium (M), large (L).

    Values are ordered by position, not alphabetically: "Large" must not
    come before "Small" in the filter panel.
    """

    class Meta(AttributeModel.Meta):
        verbose_name = "размер"
        verbose_name_plural = "размеры"
        ordering = ("position", "name")


class FacetGroup(TimeStampedModel):
    """A group in the catalog filter panel.

    The values themselves live in the reference models above; this table
    decides which groups to show the customer, under what label and in
    what order. Rows are created by the seed_facets command — one per model.
    """

    code = models.CharField(
        "ключ", max_length=32, unique=True,
        help_text="Служебный, менять не нужно: по нему группа связана "
                  "со справочником.",
    )
    name = models.CharField("подпись в панели", max_length=80)
    name_uk = models.CharField(
        "подпись по-украински", max_length=80, blank=True,
        help_text="Если не заполнить, останется русская подпись.",
    )
    position = models.PositiveSmallIntegerField("порядок", default=100)
    is_active = models.BooleanField(
        "показывать в подборе", default=True,
        help_text="Снимите галку — группа пропадёт из панели слева, "
                  "но останется в карточке товара.",
    )
    has_search = models.BooleanField(
        "поле поиска внутри группы", default=False,
        help_text="Нужно, когда значений много.",
    )

    objects = ActivatableQuerySet.as_manager()

    class Meta:
        ordering = ("position", "name")
        verbose_name = "группа подбора"
        verbose_name_plural = "панель подбора"

    def __str__(self) -> str:
        return self.name

    @property
    def title(self) -> str:
        """Group label in the visitor's language — same as for reference models."""
        if get_language() == "uk" and self.name_uk:
            return self.name_uk
        return self.name


class Product(NamedModel):
    """A product: bouquet, arrangement or plant."""

    article = models.CharField("артикул", max_length=32, unique=True)
    category = models.ForeignKey(
        Category, verbose_name="раздел", on_delete=models.SET_NULL,
        related_name="products", null=True, blank=True,
    )
    status = models.ForeignKey(
        Status, verbose_name="статус", on_delete=models.SET_NULL,
        related_name="products", null=True, blank=True,
    )

    summary = models.CharField(
        "краткое описание", max_length=300, blank=True,
        help_text="Одна-две строки. Видно в карточке товара под названием.",
    )
    summary_uk = models.CharField("краткое описание по-украински", max_length=300, blank=True)
    description = models.TextField(
        "полное описание", blank=True,
        help_text="Показывается на странице товара отдельным блоком.",
    )
    description_uk = models.TextField(
        "полное описание по-украински", blank=True,
        help_text="Если не заполнить, на украинской версии сайта "
                  "покажется русское описание.",
    )

    # --- filtering: the catalog filters work on these fields --------------
    kind = models.ForeignKey(
        Kind, verbose_name="тип товара", on_delete=models.SET_NULL,
        related_name="products", null=True, blank=True,
    )
    flowers = models.ManyToManyField(
        Flower, verbose_name="цветы", related_name="products", blank=True,
        help_text="Можно выбрать несколько: в сборном букете цветов много.",
    )
    occasions = models.ManyToManyField(
        Occasion, verbose_name="поводы", related_name="products", blank=True,
        help_text="По каким поводам предлагать этот букет.",
    )
    color = models.ForeignKey(
        Color, verbose_name="цвет", on_delete=models.SET_NULL,
        related_name="products", null=True, blank=True,
    )
    size = models.ForeignKey(
        Size, verbose_name="размер", on_delete=models.SET_NULL,
        related_name="products", null=True, blank=True,
    )

    # --- variants of one bouquet ------------------------------------------
    # "Red roses" come as 11, 25 and 51 stems. These are three products with
    # their own article, price and stock, and the shared family links them
    # into one size switcher on the product page.
    family = models.CharField(
        "семейство вариантов", max_length=64, blank=True, db_index=True,
        help_text="Одинаковое слово у букетов, которые отличаются только "
                  "размером: на странице появится переключатель. "
                  "Например «rozy-krasnye». Пусто — вариантов нет.",
    )

    # --- composition and dimensions: text and numbers, not reference models
    # Composition is free text on purpose: nobody filters by "25 Freedom
    # roses 60 cm, eucalyptus", but people do read it.
    composition = models.TextField(
        "состав", blank=True,
        help_text="Что внутри: «25 роз, эвкалипт, крафт-упаковка».",
    )
    composition_uk = models.TextField("состав по-украински", blank=True)
    stems = models.PositiveIntegerField(
        "цветков в букете", default=0,
        help_text="0 — не показывать. Для растения в горшке не нужно.",
    )
    height_cm = models.PositiveIntegerField(
        "высота, см", default=0, help_text="0 — не показывать.",
    )

    # --- stock and price --------------------------------------------------
    stock_quantity = models.PositiveIntegerField(
        "остаток, штук", default=0, db_index=True,
        help_text="Сколько букетов можно собрать сегодня.",
    )
    price = models.DecimalField(
        "цена", max_digits=9, decimal_places=2, default=Decimal("0"),
        help_text="Розничная цена за один букет.",
    )
    old_price = models.DecimalField(
        "старая цена", max_digits=9, decimal_places=2, null=True, blank=True,
        help_text="Заполните, если хотите показать зачёркнутую цену.",
    )

    objects = ProductManager()

    class Meta(NamedModel.Meta):
        verbose_name = "товар"
        verbose_name_plural = "товары"
        ordering = ("position", "-created_at")

    def __str__(self) -> str:
        return f"{self.article} · {self.name}"

    def build_slug(self) -> str:
        return transliterate(f"{self.article}-{self.name}")

    def get_absolute_url(self) -> str:
        return reverse("catalog:product", args=[self.slug])

    # --- price ----------------------------------------------------------
    def amount_for(self, quantity: int) -> Decimal:
        return (self.price * max(int(quantity or 0), 0)).quantize(Decimal("0.01"))

    @property
    def has_discount(self) -> bool:
        """The old price is set and is higher than the current one.

        "Higher" specifically: if the owner mistakenly enters a price lower
        than the current one, we will not show a "discount" upwards.
        """
        return bool(self.old_price and self.old_price > self.price)

    @property
    def discount_percent(self) -> int:
        """Discount in whole percent. Zero — nothing to show.

        Zero is also returned when there is a difference but under half a
        percent: a "−0%" badge looks like a bug, the struck-out price is enough.
        """
        if not self.has_discount:
            return 0
        return int(round((self.old_price - self.price) / self.old_price * 100))

    # --- quantity ---------------------------------------------------------
    @property
    def max_quantity(self) -> int:
        """How many can actually be taken — the whole stock."""
        return self.stock_quantity

    @property
    def minimum_quantity(self) -> int:
        return 1

    def normalize_quantity(self, quantity) -> int:
        """Turns any entered number into one that can be ordered.

        The single place where this is decided: product tile, cart, no-JS
        form — all call this method so the rules never diverge.

        Zero means "remove the line" and stays zero — otherwise there would
        be no way to clear a line. Above stock — clamped to stock.
        """
        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            return 0
        if quantity <= 0:
            return 0
        return min(quantity, self.max_quantity)

    @property
    def is_in_stock(self) -> bool:
        return self.stock_quantity > 0

    @property
    def is_orderable(self) -> bool:
        if self.status_id and not self.status.is_orderable:
            return False
        return self.is_in_stock

    @property
    def stock_label(self) -> str:
        if self.status_id and not self.status.is_orderable:
            return self.status.title
        if not self.stock_quantity:
            return _("Нет в наличии")
        return self.status.title if self.status_id else _("В наличии")

    @property
    def stock_state(self) -> str:
        if not self.stock_quantity:
            return "out"
        return "low" if self.stock_quantity < 5 else "ok"

    @property
    def status_color(self) -> str:
        return self.status.color if self.status_id else "#6B625B"

    # --- variants -------------------------------------------------------
    def variants(self):
        """Products of the same family, including this one — for the switcher.

        Ordered by size from the reference model, then by stem count: so 11
        roses always come before 51, however they were entered.
        """
        if not self.family:
            return Product.objects.none()
        return (
            Product.objects.published()
            .filter(family=self.family)
            .select_related("size")
            .order_by("size__position", "stems", "price")
        )

    @property
    def variant_label(self) -> str:
        """Switcher button label: "25 pcs" or the size name."""
        if self.stems:
            return f"{self.stems} {_('шт')}"
        if self.size_id:
            return self.size.title
        return self.article

    # --- photos ---------------------------------------------------------
    @property
    def cover(self):
        images = list(self.images.all())
        return images[0] if images else None

    @property
    def has_photo(self) -> bool:
        cover = self.cover
        return bool(cover and cover.image)

    def attribute_value(self, spec) -> str:
        """Value of one reference model for this product — as a string."""
        value = getattr(self, spec.field, None)
        if value is None:
            return ""
        if spec.multiple:
            return ", ".join(item.title for item in value.all())
        return value.title

    def tile_values(self) -> list[str]:
        """Short labels under the name in the catalog tile.

        Taken from reference models marked in_tile — flower, occasion,
        size. Empty ones are skipped.
        """
        from catalog.facets import tile_specs

        values = []
        for spec in tile_specs():
            value = getattr(self, spec.field, None)
            if value is None:
                continue
            if spec.multiple:
                # a mixed bouquet may have five flowers — two are enough
                # in the tile, the rest is on the product page
                names = [item.title for item in value.all()][:2]
                values.append(", ".join(names))
            else:
                values.append(value.title)
        return [value for value in values if value]

    @property
    def title(self) -> str:
        """Product name — always Ukrainian.

        Reference names follow the page language, product names do not:
        the shop is Ukrainian, and a bouquet must be called the same
        everywhere — in the catalog, in the order, on the courier's note,
        in a conversation with the customer. The Russian name stays in the
        database for the admin.

        No translation — show the Russian one: an empty tile is worse.
        """
        return self.name_uk or self.name

    @property
    def description_text(self) -> str:
        """Description in the visitor's language — like title on reference models."""
        if get_language() == "uk" and self.description_uk:
            return self.description_uk
        return self.description

    @property
    def summary_text(self) -> str:
        if get_language() == "uk" and self.summary_uk:
            return self.summary_uk
        return self.summary

    @property
    def composition_text(self) -> str:
        if get_language() == "uk" and self.composition_uk:
            return self.composition_uk
        return self.composition

    def specification_rows(self) -> list[tuple[str, str]]:
        """The "Specifications" table.

        The first part is built from the filter reference models — exactly
        the same ones that are in the panel on the left. The second part is
        numbers, which cannot be reference models.
        """
        from catalog.facets import FACETS

        pieces, centimetres = _("шт"), _("см")
        rows = [(_(spec.label), self.attribute_value(spec)) for spec in FACETS]
        rows += [
            (_("Цветков в букете"), f"{self.stems} {pieces}" if self.stems else ""),
            (_("Высота"), f"{self.height_cm} {centimetres}" if self.height_cm else ""),
            (_("Состав"), self.composition_text),
        ]
        return [(label, value) for label, value in rows if value]


class ProductImage(TimeStampedModel):
    """Product photo. The first by order becomes the cover."""

    product = models.ForeignKey(
        Product, verbose_name="товар", on_delete=models.CASCADE,
        related_name="images",
    )
    image = models.ImageField("файл", upload_to="products/")
    alt = models.CharField("подпись", max_length=160, blank=True)
    position = models.PositiveSmallIntegerField(
        "порядок", default=100,
        help_text="Чем меньше число, тем раньше фото. Первое — обложка.",
    )

    class Meta:
        verbose_name = "фотография"
        verbose_name_plural = "фотографии"
        ordering = ("position", "id")

    def __str__(self) -> str:
        return f"{self.product.article} · фото {self.position}"
