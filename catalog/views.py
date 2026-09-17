"""Catalog views — all class-based."""

from __future__ import annotations

from django.conf import settings
from django.db.models import (
    Case, Count, Exists, IntegerField, OuterRef, Q, Value, When,
)
from django.http import Http404
from django.utils.translation import gettext as _
from django.views.generic import DetailView, ListView

from catalog.facets import FACETS, group_titles, visible_specs
from catalog.filters import ProductFilterSet
from catalog.models import Category, Product, ProductImage, Status
from core.mixins import AjaxTemplateMixin, PageTitleMixin


class CatalogFacetsMixin:
    """Prepares the filter panel: value groups with product counts.

    Counted within the current category and ignoring already selected
    checkboxes — otherwise the numbers would collapse to zero after the
    very first click.
    """

    def selected_values(self, param: str) -> list[str]:
        """Parameter values from the URL: ?flower=roza,pion and ?flower=roza&flower=pion."""
        values: list[str] = []
        for raw in self.request.GET.getlist(param):
            values.extend(item.strip() for item in raw.split(",") if item.strip())
        return values

    def facet_base(self):
        queryset = Product.objects.published()
        slug = self.kwargs.get("category_slug") or self.request.GET.get("category")
        return queryset.in_category(slug) if slug else queryset

    def get_facets(self) -> dict:
        if hasattr(self, "_facets"):
            return self._facets
        base = self.facet_base()
        groups = []
        titles: dict[str, dict[str, str]] = {}

        settings_by_code = group_titles()
        for spec in visible_specs():
            values = (
                spec.model.objects.active()
                .annotate(total=Count("products", filter=Q(products__in=base),
                                      distinct=True))
                .order_by("position", "name")
            )
            titles[spec.code] = {value.slug: value.title for value in values}
            group = settings_by_code.get(spec.code)
            # the catalog is heterogeneous (plants have no occasion, boxes
            # have no size), so a group with no products at all and nothing
            # selected is not shown — an empty list of checkboxes looks
            # broken. Individual empty values are hidden by the template,
            # keeping only the selected ones
            chosen = set(self.selected_values(spec.code))
            if not any(value.total for value in values) and not chosen:
                continue
            groups.append({
                "param": spec.code,
                "label": group.title if group else _(spec.label),
                "searchable": group.has_search if group else spec.searchable,
                "values": [
                    {"slug": value.slug, "name": value.title, "total": value.total,
                     "empty": not value.total}
                    for value in values
                ],
            })

        # reference models switched off in the panel are still needed for
        # the "chip" labels above the grid — otherwise a selected filter
        # would show its slug
        for spec in FACETS:
            titles.setdefault(spec.code, {
                value.slug: value.title for value in spec.model.objects.all()
            })

        in_stock = base.filter(stock_quantity__gt=0).count()
        total = base.count()
        if total:
            groups.append({
                "param": "stock",
                "label": _("Наличие"),
                "searchable": False,
                "values": [
                    {"slug": "in", "name": _("В наличии"), "total": in_stock},
                    {"slug": "out", "name": _("Нет в наличии"), "total": total - in_stock},
                ],
            })

        # nonempty(): a category without products is hidden from the menu
        # and filters — it leads to an empty page and looks like an
        # unfinished shop
        categories = (
            Category.objects.active().nonempty().select_related("parent")
            .order_by("position", "name")
        )
        children: dict[int, list] = {}
        for category in categories:
            if category.parent_id:
                children.setdefault(category.parent_id, []).append(category)

        self._facets = {
            "root_categories": [c for c in categories if c.parent_id is None],
            "child_categories": children,
            "facet_groups": groups,
            "facet_titles": titles,
        }
        return self._facets


class CatalogView(PageTitleMixin, AjaxTemplateMixin, CatalogFacetsMixin, ListView):
    """Product list with filters. On a fetch request returns only the grid."""

    model = Product
    template_name = "catalog/product_list.html"
    ajax_template_name = "includes/product_grid.html"
    context_object_name = "products"
    paginate_by = settings.CATALOG_PAGE_SIZE
    page_title = "Каталог"

    def get_params(self):
        params = self.request.GET.copy()
        slug = self.kwargs.get("category_slug")
        if slug:
            params["category"] = slug
        return params

    def get_queryset(self):
        self.filterset = ProductFilterSet(
            params=self.get_params(),
            queryset=Product.objects.catalog(),
            category_titles={c.slug: c.title for c in Category.objects.active()},
            status_titles={s.slug: s.title for s in Status.objects.active()},
            titles=self.get_facets()["facet_titles"],
        )
        return self.filterset.queryset

    def get_current_category(self):
        """Category from the /katalog/<slug>/ URL or from the ?category= filter.

        A non-existent category in the URL is a 404, not "the whole
        catalog": otherwise any typo in a link would give search engines a
        duplicate of the home page. A stale ?category= from the form is
        simply ignored — it is a filter, not an address.
        """
        slug = self.kwargs.get("category_slug")
        if slug:
            category = Category.objects.filter(slug=slug, is_active=True).first()
            if category is None:
                raise Http404
            return category
        slug = self.request.GET.get("category")
        if not slug:
            return None
        return Category.objects.filter(slug=slug, is_active=True).first()

    def get_page_title(self) -> str:
        """Page title. Accounts for both the category and the "Sale" button.

        Arrived via "Sale" — say so, otherwise the page is called "Whole
        catalog" while showing a third of the products. Inside a category
        the category name is appended: "Sale · Bouquets".
        """
        category = self.get_current_category()
        sale = bool(self.request.GET.get("discount"))
        if category and sale:
            return f"{_('Акции')} · {category.title}"
        if category:
            return category.title
        if sale:
            return _("Акции")
        return _("Весь каталог")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category = self.get_current_category()
        context.update(self.get_facets())
        context.update({
            "filterset": self.filterset,
            "chips": self.filterset.chips,
            "sorting": self.filterset.sorting,
            "current_category": category,
            "selected": {
                group["param"]: self.selected_values(group["param"])
                for group in context["facet_groups"]
            },
            "total_count": context["paginator"].count if context.get("paginator")
            else len(context["products"]),
            "breadcrumbs": self.build_breadcrumbs(category),
            "banner_products": self.banner_products(),
        })
        return context

    # how many products the new-arrivals banner shows
    BANNER_COUNT = 3
    # in the whole catalog one new item per category; more than four cards
    # do not fit in a row — they become thumbnail-sized
    BANNER_ROOTS = 4

    # "New" is a status from the reference model. Looked up both by slug and
    # by name: if the status is re-created in the admin the slug changes
    # while the name stays. Sorting does the same.
    NEW_STATUS_SLUG = "novinka"
    NEW_STATUS_NAME = "Новинка"

    def banner_products(self):
        """New arrivals for the banner above the catalog.

        Inside a category — the three latest products of that category. In
        the whole catalog it is different: one new item from each top-level
        category, so the home page shows bouquets, arrangements and plants
        rather than three rose bouquets uploaded in a row.

        A category is taken together with its children: "Bouquets" has no
        products of its own, they all sit in "Roses" and "Tulips", and
        without this its card would be empty.

        Order within a category: products with the "New" status first, then
        by date added. The status is optional: without it we simply take
        what was added last.

        Photo presence is checked via Exists, not via a JOIN with filter():
        a JOIN would multiply the product by its number of photos, and we
        would need distinct(), which does not play well with ordering in SQLite.
        """
        has_photo = Exists(ProductImage.objects.filter(product=OuterRef("pk")))
        # facet_base already knows the current category — both from a
        # /katalog/bukety/ URL and from ?category= in the filters
        newest = (
            self.facet_base()
            .filter(has_photo)
            .annotate(is_new=Case(
                When(
                    Q(status__slug=self.NEW_STATUS_SLUG)
                    | Q(status__name__iexact=self.NEW_STATUS_NAME),
                    then=Value(1),
                ),
                default=Value(0),
                output_field=IntegerField(),
            ))
            .order_by("-is_new", "-created_at")
            .prefetch_related("images")
        )

        if self.get_current_category():
            return list(newest[:self.BANNER_COUNT])

        # whole catalog: one product from each root category. One query per
        # category rather than a single one: "first row within a group" in
        # SQLite needs window functions, which would have to be explained
        # to whoever reads this after us.
        roots = (
            Category.objects.active().nonempty().filter(parent__isnull=True)
            .order_by("position", "name")[:self.BANNER_ROOTS]
        )
        picked = []
        for root in roots:
            item = newest.in_category(root.slug).first()
            if item is not None:
                picked.append(item)
        # no categories or all empty — behave as inside a category
        return picked or list(newest[:self.BANNER_COUNT])

    @staticmethod
    def build_breadcrumbs(category) -> list[dict]:
        crumbs = [{"title": _("Каталог"), "url": "/"}]
        if category and category.parent:
            crumbs.append({
                "title": category.parent.title,
                "url": category.parent.get_absolute_url(),
            })
        if category:
            crumbs.append({"title": category.title, "url": None})
        return crumbs

    def render_to_response(self, context, **response_kwargs):
        if self.is_ajax():
            return self.render_fragment(context)
        return self.mark_vary(super().render_to_response(context, **response_kwargs))


class ProductDetailView(PageTitleMixin, DetailView):
    """Product page: photos, specifications, size switcher."""

    model = Product
    template_name = "catalog/product_detail.html"
    context_object_name = "product"

    def get_queryset(self):
        return Product.objects.catalog()

    def get_page_title(self) -> str:
        return self.object.title

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = self.object
        crumbs = [{"title": _("Каталог"), "url": "/"}]
        if product.category_id:
            crumbs.append({"title": product.category.title,
                           "url": product.category.get_absolute_url()})
        crumbs.append({"title": product.title, "url": None})

        # size switcher: products of the same family, including this one.
        # A single product in the family — nothing to switch to, hidden
        variants = list(product.variants())
        if len(variants) < 2:
            variants = []

        # "From the same category" — without family siblings: they are
        # already in the switcher right above the price
        related = (
            Product.objects.catalog()
            .filter(category=product.category)
            .exclude(pk=product.pk)
        )
        if product.family:
            related = related.exclude(family=product.family)

        context.update({
            "specification": product.specification_rows(),
            "images": list(product.images.all()),
            "breadcrumbs": crumbs,
            "variants": variants,
            "related": related[:4],
        })
        return context
