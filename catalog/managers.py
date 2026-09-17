"""Catalog managers and QuerySets — all query logic lives here so that
views stay thin."""

from django.db import models
from django.db.models import Exists, F, OuterRef, Q

from core.models import ActivatableQuerySet

# Relations the catalog loads in one go. FKs go to select_related,
# multi-valued reference models and photos to prefetch. A new reference
# model from catalog/facets.py must be added here, otherwise the tile hits
# the database for every product separately.
RELATED = ("category", "status", "kind", "color", "size")
PREFETCH = ("images", "flowers", "occasions")


class CategoryQuerySet(ActivatableQuerySet):
    """Catalog category lookups."""

    def nonempty(self) -> "CategoryQuerySet":
        """Only categories that have something to show.

        An empty category in the menu is a promise the storefront does not
        keep: the visitor opens it and sees a bare page. Such categories
        used to be hidden with a checkbox in the admin, not forgetting to
        turn it back on when stock arrived. Now the category disappears
        and comes back by itself.

        Products are counted both in the category itself and in its
        children: "Bouquets" has no products of its own, they sit in
        "Roses", and without the second check the parent would vanish too.

        Exists instead of a join with distinct: a join multiplies rows by
        the number of products, and distinct in SQLite does not play well
        with ordering by a field that is not in the selection.

        The import inside the method is deliberate: models.py imports this
        file, and a back reference at the top would create an import cycle.
        """
        from catalog.models import Product

        here = Product.objects.filter(is_active=True, category=OuterRef("pk"))
        inside = Product.objects.filter(is_active=True, category__parent=OuterRef("pk"))
        return self.filter(Exists(here) | Exists(inside))


class ProductQuerySet(ActivatableQuerySet):
    """Product lookups. Every method returns a new QuerySet, so they can
    be chained."""

    def published(self) -> "ProductQuerySet":
        return self.active()

    def with_relations(self) -> "ProductQuerySet":
        return self.select_related(*RELATED).prefetch_related(*PREFETCH)

    # --- filters ---------------------------------------------------------
    def in_category(self, slug: str) -> "ProductQuerySet":
        return self.filter(Q(category__slug=slug) | Q(category__parent__slug=slug))

    def in_stock(self) -> "ProductQuerySet":
        return self.filter(stock_quantity__gt=0)

    def with_discount(self) -> "ProductQuerySet":
        """Only discounted products — for the "Sale" button in the header.

        Same criterion that shows the struck-out price on the tile
        (Product.has_discount): the old price is set and higher than the
        current one. It must not be computed differently here — "Sale" and
        the "−5 %" badge would diverge, and a customer would find a product
        without a discount among the sale items.
        """
        return self.filter(old_price__isnull=False, old_price__gt=F("price"))

    def with_status(self, slugs) -> "ProductQuerySet":
        return self.filter(status__slug__in=list(slugs))

    def with_attribute(self, lookup: str, slugs, multiple: bool = False):
        """Filter by any reference model.

        Deliberately no separate method per attribute: they all filter the
        same way — by value slug. Which ones exist is described in
        catalog/facets.py.
        """
        queryset = self.filter(**{lookup: list(slugs)})
        return queryset.distinct() if multiple else queryset

    def availability(self, values) -> "ProductQuerySet":
        """"In stock" / "Out of stock" — determined by the stock quantity."""
        values = set(values)
        if values == {"in"}:
            return self.filter(stock_quantity__gt=0)
        if values == {"out"}:
            return self.filter(stock_quantity=0)
        return self

    def price_between(self, low=None, high=None) -> "ProductQuerySet":
        qs = self
        if low is not None:
            qs = qs.filter(price__gte=low)
        if high is not None:
            qs = qs.filter(price__lte=high)
        return qs

    def search(self, term: str) -> "ProductQuerySet":
        term = (term or "").strip()
        if not term:
            return self
        # LIKE in SQLite is case-insensitive for ASCII only: "роза" and
        # "Роза" are different strings. So we search as typed, capitalised
        # and all lower-case — across the Russian and Ukrainian name,
        # article, composition and flower.
        variants = {term, term.lower(), term.capitalize()}
        query = Q()
        for word in variants:
            query |= (
                Q(name__contains=word)
                | Q(name_uk__contains=word)
                | Q(article__icontains=word)
                | Q(composition__contains=word)
                | Q(composition_uk__contains=word)
                | Q(flowers__name__contains=word)
                | Q(flowers__name_uk__contains=word)
            )
        return self.filter(query).distinct()


class ProductManager(models.Manager.from_queryset(ProductQuerySet)):
    """Default manager: returns a set ready for display."""

    def catalog(self) -> ProductQuerySet:
        return self.get_queryset().published().with_relations()
