"""Модели каталога.

Иерархия наследования:
    models.Model
      └── TimeStampedModel (core)
            └── NamedModel (core)
                  ├── Category, Status, справочники подбора
                  └── Product

Товар продаётся поштучно: букет — одна штука, цена одна на товар,
остаток — одно число. Варианты одного букета (11 / 25 / 51 роза) — это
отдельные товары, связанные полем family: у каждого свой артикул,
цена и остаток, а на странице между ними стоит переключатель размера.

Автор кода: ISHOD, 2026. Все права на исходный код принадлежат автору.
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
    """Раздел каталога. Поддерживает один уровень вложенности."""

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
    """Статус товара: «В наличии», «Под заказ», «Новинка», «Снят с продажи».

    Список редактируется в админке — можно завести свои.
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
    """Общая база для справочников, по которым фильтруется каталог.

    Все они устроены одинаково: название, порядок, показывать или нет.
    Владелец заводит значения в админке, фильтр в каталоге появляется сам.
    """

    class Meta(NamedModel.Meta):
        abstract = True


class Kind(AttributeModel):
    """Тип товара: Букет, Композиция в коробке, Корзина, Растение в горшке."""

    class Meta(AttributeModel.Meta):
        verbose_name = "тип товара"
        verbose_name_plural = "типы товаров"


class Flower(AttributeModel):
    """Цветок: Роза, Тюльпан, Пион, Хризантема.

    Множественный справочник: в сборном букете цветов несколько.
    """

    class Meta(AttributeModel.Meta):
        verbose_name = "цветок"
        verbose_name_plural = "цветы"


class Occasion(AttributeModel):
    """Повод: День рождения, Свадьба, 8 Марта. У букета их может быть несколько."""

    class Meta(AttributeModel.Meta):
        verbose_name = "повод"
        verbose_name_plural = "поводы"


class Color(AttributeModel):
    """Основной цвет букета: Красный, Розовый, Белый, Микс."""

    class Meta(AttributeModel.Meta):
        verbose_name = "цвет"
        verbose_name_plural = "цвета"


class Size(AttributeModel):
    """Размер букета: Малый (S), Средний (M), Большой (L).

    Порядок значений — по полю position, не по алфавиту: «Большой»
    в подборе не должен стоять раньше «Малого» (грабля 24).
    """

    class Meta(AttributeModel.Meta):
        verbose_name = "размер"
        verbose_name_plural = "размеры"
        ordering = ("position", "name")


class FacetGroup(TimeStampedModel):
    """Группа в панели подбора каталога.

    Сами значения живут в справочниках выше, а эта таблица решает, какие
    группы показывать покупателю, под какой подписью и в каком порядке.
    Строки заводит команда seed_facets — по одной на справочник.
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
        """Подпись группы на языке посетителя — как у справочников."""
        if get_language() == "uk" and self.name_uk:
            return self.name_uk
        return self.name


class Product(NamedModel):
    """Товарная позиция: букет, композиция или растение."""

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

    # --- подбор: по этим полям работают фильтры в каталоге ---------------
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

    # --- варианты одного букета -------------------------------------------
    # «Розы красные» бывают на 11, 25 и 51 штуку. Это три товара со своим
    # артикулом, ценой и остатком, а одинаковая family связывает их в один
    # переключатель размера на странице товара.
    family = models.CharField(
        "семейство вариантов", max_length=64, blank=True, db_index=True,
        help_text="Одинаковое слово у букетов, которые отличаются только "
                  "размером: на странице появится переключатель. "
                  "Например «rozy-krasnye». Пусто — вариантов нет.",
    )

    # --- состав и размеры: текст и числа, не справочники -------------------
    # Состав — свободный текст намеренно: «25 роз Freedom 60 см, эвкалипт»
    # никто не станет фильтровать, а вот читать его будут.
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

    # --- остаток и цена ---------------------------------------------------
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

    # --- цена -----------------------------------------------------------
    def amount_for(self, quantity: int) -> Decimal:
        return (self.price * max(int(quantity or 0), 0)).quantize(Decimal("0.01"))

    @property
    def has_discount(self) -> bool:
        """Старая цена заполнена и она выше текущей.

        Проверяем именно «выше»: если владелец по ошибке впишет цену
        ниже нынешней, показывать «скидку» вверх мы не станем.
        """
        return bool(self.old_price and self.old_price > self.price)

    @property
    def discount_percent(self) -> int:
        """Скидка в процентах, целыми. Ноль — показывать нечего.

        Ноль возвращается и когда разница есть, но меньше половины
        процента: плашка «−0%» выглядит как ошибка, лучше обойтись
        зачёркнутой ценой.
        """
        if not self.has_discount:
            return 0
        return int(round((self.old_price - self.price) / self.old_price * 100))

    # --- количество -------------------------------------------------------
    @property
    def max_quantity(self) -> int:
        """Сколько штук реально можно взять — весь остаток."""
        return self.stock_quantity

    @property
    def minimum_quantity(self) -> int:
        return 1

    def normalize_quantity(self, quantity) -> int:
        """Приводит любое введённое число к тому, что можно заказать.

        Единственное место, где это решается: карточка, корзина, форма
        без JavaScript — все зовут этот метод, чтобы правила не разъезжались.

        Ноль означает «убрать позицию» и остаётся нулём — иначе очистить
        строку было бы нечем. Больше остатка — обрезаем до остатка.
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

    # --- варианты -------------------------------------------------------
    def variants(self):
        """Товары того же семейства, включая этот, — для переключателя.

        Порядок по размеру из справочника, внутри — по числу цветков:
        так 11 роз всегда стоят раньше 51, как бы их ни завели.
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
        """Подпись кнопки в переключателе: «25 шт» или название размера."""
        if self.stems:
            return f"{self.stems} {_('шт')}"
        if self.size_id:
            return self.size.title
        return self.article

    # --- фото -----------------------------------------------------------
    @property
    def cover(self):
        images = list(self.images.all())
        return images[0] if images else None

    @property
    def has_photo(self) -> bool:
        cover = self.cover
        return bool(cover and cover.image)

    def attribute_value(self, spec) -> str:
        """Значение одного справочника у этого товара — строкой."""
        value = getattr(self, spec.field, None)
        if value is None:
            return ""
        if spec.multiple:
            return ", ".join(item.title for item in value.all())
        return value.title

    def tile_values(self) -> list[str]:
        """Короткие подписи под названием в плитке каталога.

        Берутся из справочников с пометкой in_tile — цветок, повод,
        размер. Пустые пропускаются.
        """
        from catalog.facets import tile_specs

        values = []
        for spec in tile_specs():
            value = getattr(self, spec.field, None)
            if value is None:
                continue
            if spec.multiple:
                # у сборного букета цветов может быть пять — в плитке
                # хватит двух, остальное видно на странице товара
                names = [item.title for item in value.all()][:2]
                values.append(", ".join(names))
            else:
                values.append(value.title)
        return [value for value in values if value]

    @property
    def title(self) -> str:
        """Название товара — всегда украинское.

        У справочников название следует за языком страницы, у товаров —
        нет: магазин украинский, и букет должен называться одинаково
        везде — в каталоге, в заказе, в открытке курьера, в разговоре
        с покупателем. Русское название остаётся в базе для админки.

        Перевода нет — показываем русское: пустая карточка хуже.
        """
        return self.name_uk or self.name

    @property
    def description_text(self) -> str:
        """Описание на языке посетителя — как title у справочников."""
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
        """Таблица «Характеристики».

        Первая часть строится из справочников подбора — ровно из тех же,
        что стоят в панели слева. Вторая — числа, справочниками они
        быть не могут.
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
    """Фотография товара. Первая по порядку становится обложкой."""

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
