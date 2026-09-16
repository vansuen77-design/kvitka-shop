"""Реестр справочников подбора.

Одно место, из которого работает всё сразу:

* панель подбора в каталоге (какие группы, в каком порядке, с поиском ли);
* фильтрация товаров по адресной строке;
* подписи в плитке каталога (in_tile);
* таблица «Характеристики» на странице товара;
* колонки прайса и список справочников в админке.

Добавили сюда строку — новая характеристика появилась везде.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.utils.translation import gettext_noop

from catalog.models import Color, FacetGroup, Flower, Kind, Occasion, Size


@dataclass(frozen=True)
class FacetSpec:
    """Описание одного справочника."""

    code: str            # ключ в адресной строке: ?flower=roza
    field: str           # поле товара
    model: type          # модель справочника
    label: str           # подпись — русский ключ перевода
    multiple: bool = False   # можно выбрать несколько значений у товара
    searchable: bool = False  # поле поиска внутри группы фильтра
    in_filter: bool = True    # показывать в подборе по умолчанию
    in_tile: bool = False     # показывать значение в плитке каталога
    position: int = 100

    @property
    def lookup(self) -> str:
        """Как отфильтровать товары по адресам значений."""
        return f"{self.field}__slug__in"


FACETS: list[FacetSpec] = [
    FacetSpec("type", "kind", Kind, gettext_noop("Тип"), position=10),
    FacetSpec("flower", "flowers", Flower, gettext_noop("Цветы"),
              multiple=True, in_tile=True, position=20),
    FacetSpec("occasion", "occasions", Occasion, gettext_noop("Повод"),
              multiple=True, in_tile=True, position=30),
    FacetSpec("color", "color", Color, gettext_noop("Цвет"), position=40),
    FacetSpec("size", "size", Size, gettext_noop("Размер"), in_tile=True,
              position=50),
]

BY_CODE: dict[str, FacetSpec] = {spec.code: spec for spec in FACETS}
BY_MODEL: dict[type, FacetSpec] = {spec.model: spec for spec in FACETS}


def visible_specs() -> list[FacetSpec]:
    """Справочники, включённые в панель подбора — в порядке из админки."""
    groups = {group.code: group for group in FacetGroup.objects.active()}
    chosen = [(groups[spec.code], spec) for spec in FACETS if spec.code in groups]
    chosen.sort(key=lambda pair: (pair[0].position, pair[0].name))
    return [spec for _, spec in chosen]


def tile_specs() -> list[FacetSpec]:
    """Справочники, значения которых подписываются в плитке (до трёх)."""
    return [spec for spec in FACETS if spec.in_tile][:3]


def group_titles() -> dict[str, "FacetGroup"]:
    """Настройки групп из админки: подпись, поиск, порядок."""
    return {group.code: group for group in FacetGroup.objects.all()}
