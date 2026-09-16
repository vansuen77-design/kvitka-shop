"""Фильтры каталога.

Каждый фильтр — отдельный класс: знает, как достать значение из GET,
как применить его к выборке и как показать себя «чипом» над сеткой.
Добавить новый фильтр = добавить класс в список ProductFilterSet.filters.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal, InvalidOperation

from django.db.models import (
    Case, ExpressionWrapper, F, FloatField, IntegerField, Q, Value, When,
)
from django.db.models.functions import Cast
from django.utils.translation import gettext as _, gettext_noop


class Filter(ABC):
    """Базовый фильтр."""

    def __init__(self, param: str, label: str) -> None:
        self.param = param
        self.label = label

    @abstractmethod
    def parse(self, params):
        """Достаёт значение из QueryDict. None — фильтр не задан."""

    @abstractmethod
    def apply(self, queryset, value):
        """Применяет значение к выборке."""

    def chips(self, value) -> list[dict]:
        return [{"param": self.param, "label": f"{self.label}: {value}"}]


class MultiChoiceFilter(Filter):
    """Несколько значений: ?flower=roza&flower=pion или ?flower=roza,pion"""

    def __init__(self, param, label, queryset_method, titles=None):
        super().__init__(param, label)
        self.queryset_method = queryset_method
        self.titles = titles or {}

    def parse(self, params):
        if hasattr(params, "getlist"):
            raw_values = params.getlist(self.param)
        else:
            raw_values = [params.get(self.param, "")]
        values: list[str] = []
        for raw in raw_values:
            values.extend(item.strip() for item in str(raw).split(",") if item.strip())
        return values or None

    def apply(self, queryset, value):
        return getattr(queryset, self.queryset_method)(value)

    def chips(self, value) -> list[dict]:
        names = [self.titles.get(item, item) for item in value]
        return [{"param": self.param, "label": f"{self.label}: {', '.join(names)}"}]


class AttributeFilter(MultiChoiceFilter):
    """Фильтр по справочнику подбора — один класс на все характеристики."""

    def __init__(self, spec, label=None, titles=None):
        super().__init__(spec.code, label or _(spec.label), "", titles)
        self.spec = spec

    def apply(self, queryset, value):
        return queryset.with_attribute(self.spec.lookup, value, self.spec.multiple)


class CategoryFilter(Filter):
    titles: dict = {}

    def parse(self, params):
        return params.get(self.param) or None

    def apply(self, queryset, value):
        return queryset.in_category(value)

    def chips(self, value) -> list[dict]:
        return [{"param": self.param, "label": self.titles.get(value, value)}]


class SearchFilter(Filter):
    def parse(self, params):
        return (params.get(self.param) or "").strip() or None

    def apply(self, queryset, value):
        return queryset.search(value)

    def chips(self, value) -> list[dict]:
        return [{"param": self.param, "label": _("Поиск: «%(text)s»") % {"text": value}}]


class PriceRangeFilter(Filter):
    """?price_min=64&price_max=210"""

    def __init__(self, param="price", label=None):
        label = label or _("Цена")
        super().__init__(param, label)
        self.min_param = f"{param}_min"
        self.max_param = f"{param}_max"

    @staticmethod
    def _decimal(raw):
        try:
            return Decimal(raw) if raw not in (None, "") else None
        except (InvalidOperation, TypeError):
            return None

    def parse(self, params):
        low = self._decimal(params.get(self.min_param))
        high = self._decimal(params.get(self.max_param))
        if low is None and high is None:
            return None
        return (low, high)

    def apply(self, queryset, value):
        low, high = value
        return queryset.price_between(low, high)

    def chips(self, value) -> list[dict]:
        low, high = value
        if low is not None and high is not None:
            text = f"{low:.0f}–{high:.0f} ₴"
        elif low is not None:
            text = _("от %(sum)s ₴") % {"sum": f"{low:.0f}"}
        else:
            text = _("до %(sum)s ₴") % {"sum": f"{high:.0f}"}
        return [{
            "param": self.min_param,
            "label": f"{self.label}: {text}",
            "extra": self.max_param,
        }]


class FlagFilter(Filter):
    """Логический переключатель: ?in_stock=1"""

    def __init__(self, param, label, queryset_method):
        super().__init__(param, label)
        self.queryset_method = queryset_method

    def parse(self, params):
        return True if params.get(self.param) in ("1", "true", "on", "yes") else None

    def apply(self, queryset, value):
        return getattr(queryset, self.queryset_method)()

    def chips(self, value) -> list[dict]:
        return [{"param": self.param, "label": self.label}]


class Sorting:
    """Сортировка списка."""

    # подписи здесь по-русски: это одновременно и ключи перевода,
    # переводятся при выводе в label/as_choices. gettext_noop только
    # помечает строку для makelocales, сам перевод — при выводе.
    OPTIONS = {
        "popular": (gettext_noop("сначала популярные"), ("position", "-created_at")),
        "cheap": (gettext_noop("сначала дешевле"), ("price",)),
        "expensive": (gettext_noop("сначала дороже"), ("-price",)),
        "new": (gettext_noop("сначала новые"), ("-is_new", "-created_at")),
        "sale": (gettext_noop("сначала со скидкой"), ("-discount", "price")),
    }
    DEFAULT = "popular"

    # «Новинка» — это статус из справочника, а не отдельная галка.
    # Ищем и по адресу, и по названию: если статус когда-нибудь заведут
    # заново руками, адрес получится другой, а название останется.
    NEW_STATUS_SLUG = "novinka"
    NEW_STATUS_NAME = "Новинка"

    def __init__(self, key: str | None) -> None:
        self.key = key if key in self.OPTIONS else self.DEFAULT

    @property
    def label(self) -> str:
        return _(self.OPTIONS[self.key][0])

    @property
    def order_by(self) -> tuple[str, ...]:
        """Поля для order_by. Дата добавления идёт последней всегда:
        при равенстве основного признака порядок должен быть
        предсказуемым, иначе SQLite выдаёт строки как ей удобно."""
        fields = self.OPTIONS[self.key][1]
        if "-created_at" not in fields:
            fields += ("-created_at",)
        return fields

    def prepare(self, queryset):
        """Досыпает в выборку то, чего нет в самой модели.

        «Сначала новые» по одной дате создания бесполезны: весь каталог
        заливается пачкой и отличается миллисекундами. Поэтому наверх
        поднимаем то, что магазин сам пометил статусом «Новинка»,
        а уже внутри — по дате добавления.

        «Сначала со скидкой» считает процент: в модели он свойство
        Python, а сортировать надо на стороне базы.
        """
        if self.key == "new":
            return queryset.annotate(is_new=Case(
                When(
                    Q(status__slug=self.NEW_STATUS_SLUG)
                    | Q(status__name__iexact=self.NEW_STATUS_NAME),
                    then=Value(1),
                ),
                default=Value(0),
                output_field=IntegerField(),
            ))

        if self.key == "sale":
            # Считаем долю скидки, а не разницу в гривнах: иначе наверх
            # уедут дорогие товары, у которых «минус 80 ₴» это те же
            # пять процентов, что у дешёвых «минус 3 ₴».
            #
            # Товары без старой цены получают ноль и честно оказываются
            # в конце — скрывать их нельзя, это обычная сортировка,
            # а не фильтр «только со скидкой».
            # Считаем во float, а не в Decimal. Деление двух Decimal
            # SQLite отдаёт так, что Django возвращает NULL, и сортировка
            # молча вырождается в сортировку по цене — проверено на живой
            # выборке. Явное приведение к float это убирает.
            money = lambda field: Cast(F(field), FloatField())
            ratio = ExpressionWrapper(
                (money("old_price") - money("price")) / money("old_price"),
                output_field=FloatField(),
            )
            return queryset.annotate(discount=Case(
                When(
                    Q(old_price__isnull=False) & Q(old_price__gt=F("price")),
                    then=ratio,
                ),
                default=Value(0.0),
                output_field=FloatField(),
            ))

        return queryset

    def as_choices(self) -> list[dict]:
        return [
            {"key": key, "label": _(label), "selected": key == self.key}
            for key, (label, order) in self.OPTIONS.items()
        ]


class ProductFilterSet:
    """Собирает выборку каталога из параметров запроса."""

    def __init__(self, params, queryset, category_titles=None,
                 status_titles=None, titles=None):
        self.params = params
        self.base_queryset = queryset
        titles = titles or {}

        category_filter = CategoryFilter("category", _("Раздел"))
        category_filter.titles = category_titles or {}

        # фильтры по справочникам собираются из реестра: добавили строку
        # в catalog/facets.py — фильтр появился сам
        from catalog.facets import FACETS, group_titles

        groups = group_titles()
        self.filters: list[Filter] = [
            category_filter,
            SearchFilter("q", _("Поиск")),
            MultiChoiceFilter("status", _("Статус"), "with_status", status_titles),
        ]
        for spec in FACETS:
            group = groups.get(spec.code)
            self.filters.append(AttributeFilter(
                spec,
                label=group.title if group else _(spec.label),
                titles=titles.get(spec.code),
            ))
        self.filters += [
            MultiChoiceFilter("stock", _("Наличие"), "availability",
                              {"in": _("В наличии"), "out": _("Нет в наличии")}),
            # ?discount=1 — сюда ведёт кнопка «Акции» в шапке. Отдельной
            # галки в панели подбора нет специально: фильтр снимается
            # чипом над сеткой, как и все остальные.
            FlagFilter("discount", _("Только со скидкой"), "with_discount"),
            PriceRangeFilter(),
        ]
        self.sorting = Sorting(params.get("sort"))
        self._applied: list[tuple[Filter, object]] = []

    @property
    def queryset(self):
        queryset = self.base_queryset
        self._applied = []
        for item in self.filters:
            value = item.parse(self.params)
            if value is None:
                continue
            queryset = item.apply(queryset, value)
            self._applied.append((item, value))
        queryset = self.sorting.prepare(queryset)
        return queryset.order_by(*self.sorting.order_by)

    @property
    def chips(self) -> list[dict]:
        result: list[dict] = []
        for item, value in self._applied:
            result.extend(item.chips(value))
        return result

    @property
    def is_filtered(self) -> bool:
        return bool(self._applied)
