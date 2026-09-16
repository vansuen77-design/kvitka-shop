"""Представления каталога — все классовые (CBV)."""

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
    """Готовит панель подбора: группы значений с количеством товаров.

    Считаем в пределах текущего раздела и без учёта уже выбранных галок —
    иначе цифры схлопнулись бы в нули после первого же клика.
    """

    def selected_values(self, param: str) -> list[str]:
        """Значения параметра из адреса: ?flower=roza,pion и ?flower=roza&flower=pion."""
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
            # каталог разнородный (у растений нет повода, у коробок нет
            # размера), поэтому группу, в которой нет ни одного товара
            # и ничего не выбрано, не показываем вовсе — пустой список
            # галок выглядит как поломка. Отдельные пустые значения
            # прячет шаблон, оставляя только выбранные
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

        # справочники, выключенные из панели, всё равно нужны для подписей
        # на «чипах» над сеткой — иначе выбранный фильтр покажет адрес
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

        # nonempty(): раздел без товаров в меню и фильтрах не показываем —
        # он ведёт на пустую страницу и выглядит как недоделанный магазин
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
    """Список товаров с фильтрами. При fetch-запросе отдаёт только сетку."""

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
        """Раздел из адреса /katalog/<slug>/ или из ?category= фильтра.

        Несуществующий раздел в адресе — 404, а не «весь каталог»:
        иначе любая опечатка в ссылке отдавала бы поисковикам дубль
        главной страницы. Устаревшее ?category= из формы просто не
        учитываем — это фильтр, а не адрес.
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
        """Заголовок страницы. Учитывает и раздел, и кнопку «Акции».

        Пришли по «Акциям» — так и пишем, иначе страница называется
        «Весь каталог», а товаров в ней треть. Внутри раздела к слову
        добавляем его название: «Акции · Букети».
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

    # сколько товаров показываем в баннере новинок
    BANNER_COUNT = 3
    # в общем каталоге берём по одной новинке из раздела; больше четырёх
    # карточек в строку не помещается — они становятся с ноготь
    BANNER_ROOTS = 4

    # «Новинка» — статус из справочника. Ищем и по адресу, и по названию:
    # если статус заведут в админке заново, адрес получится другой,
    # а название останется прежним. Так же сделано в сортировке.
    NEW_STATUS_SLUG = "novinka"
    NEW_STATUS_NAME = "Новинка"

    def banner_products(self):
        """Новинки для баннера над каталогом.

        В разделе — три последних товара этого раздела. В общем каталоге
        иначе: по одной новинке из каждого раздела верхнего уровня, чтобы
        на главной было видно и букеты, и композиции, и растения, а не три
        подряд загруженных букета роз.

        Раздел учитываем вместе с вложенными: у «Букетов» своих товаров
        нет вовсе, все лежат в «Розах» и «Тюльпанах», и без этого его
        карточка была бы пустой.

        Порядок внутри раздела: сначала помеченные статусом «Новинка»,
        внутри — по дате добавления. Статус не обязателен: без него берём
        просто то, что добавили последним.

        Наличие фото проверяем через Exists, а не через JOIN с filter():
        JOIN размножил бы товар по числу фотографий, и пришлось бы звать
        distinct(), который в SQLite плохо дружит с сортировкой.
        """
        has_photo = Exists(ProductImage.objects.filter(product=OuterRef("pk")))
        # facet_base уже знает про текущий раздел — и про адрес вида
        # /katalog/bukety/, и про ?category= из фильтров
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

        # общий каталог: по одному товару из каждого корневого раздела.
        # Запрос на раздел, а не один общий: выбрать «первую строку внутри
        # группы» SQLite умеет только через оконные функции, а их придётся
        # объяснять тому, кто полезет сюда после нас.
        roots = (
            Category.objects.active().nonempty().filter(parent__isnull=True)
            .order_by("position", "name")[:self.BANNER_ROOTS]
        )
        picked = []
        for root in roots:
            item = newest.in_category(root.slug).first()
            if item is not None:
                picked.append(item)
        # разделов нет или все пустые — ведём себя как в разделе
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
    """Карточка товара: фотографии, характеристики, переключатель размера."""

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

        # переключатель размера: товары того же семейства, включая этот.
        # Один товар в семействе — переключать не на что, не показываем
        variants = list(product.variants())
        if len(variants) < 2:
            variants = []

        # «Из этого же раздела» — без соседей по семейству: они и так
        # стоят в переключателе прямо над ценой
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
