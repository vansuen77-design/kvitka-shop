"""Registry of filter reference models.

One place that drives everything at once:

* the filter panel in the catalog (which groups, in what order, with search or not);
* filtering products by the query string;
* labels in the catalog tile (in_tile);
* the "Specifications" table on the product page;
* price-list columns and the list of reference models in the admin.

Add a line here — a new attribute appears everywhere.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.utils.translation import gettext_noop

from catalog.models import Color, FacetGroup, Flower, Kind, Occasion, Size


@dataclass(frozen=True)
class FacetSpec:
    """Description of one reference model."""

    code: str            # query-string key: ?flower=roza
    field: str           # product field
    model: type          # reference model
    label: str           # label — Russian translation key
    multiple: bool = False   # a product may have several values
    searchable: bool = False  # search box inside the filter group
    in_filter: bool = True    # shown in the filter panel by default
    in_tile: bool = False     # value shown in the catalog tile
    position: int = 100

    @property
    def lookup(self) -> str:
        """How to filter products by value slugs."""
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
    """Reference models enabled in the filter panel — in the admin order."""
    groups = {group.code: group for group in FacetGroup.objects.active()}
    chosen = [(groups[spec.code], spec) for spec in FACETS if spec.code in groups]
    chosen.sort(key=lambda pair: (pair[0].position, pair[0].name))
    return [spec for _, spec in chosen]


def tile_specs() -> list[FacetSpec]:
    """Reference models whose values are shown in the tile (up to three)."""
    return [spec for spec in FACETS if spec.in_tile][:3]


def group_titles() -> dict[str, "FacetGroup"]:
    """Group settings from the admin: label, search, order."""
    return {group.code: group for group in FacetGroup.objects.all()}
