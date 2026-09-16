"""Фильтры каталога: справочники из адреса, поиск, цена, скидка."""

from django.http import QueryDict
from django.test import TestCase

from catalog.facets import BY_CODE, FACETS
from catalog.filters import ProductFilterSet
from catalog.models import Product
from core.tests.factories import (
    Color, Flower, Kind, Occasion, Size, make_category, make_product, make_value,
)


def filtered(query: str):
    params = QueryDict(query)
    return list(ProductFilterSet(params, Product.objects.catalog()).queryset)


class AttributeFilterTests(TestCase):
    def setUp(self):
        self.roza = make_value(Flower, "Роза", slug="roza")
        self.pion = make_value(Flower, "Пион", slug="pion")
        self.only_roza = make_product(name="розы", flowers=[self.roza])
        self.only_pion = make_product(name="пионы", flowers=[self.pion])
        self.both = make_product(name="микс", flowers=[self.roza, self.pion])

    def test_comma_and_repeat_forms_are_equal(self):
        comma = filtered("flower=roza,pion")
        repeat = filtered("flower=roza&flower=pion")
        self.assertEqual(set(comma), set(repeat))
        self.assertEqual(set(comma), {self.only_roza, self.only_pion, self.both})

    def test_multiple_facet_does_not_duplicate_rows(self):
        rows = filtered("flower=roza,pion")
        self.assertEqual(len(rows), 3)

    def test_single_value(self):
        self.assertEqual(set(filtered("flower=pion")), {self.only_pion, self.both})

    def test_every_facet_is_filterable_by_url(self):
        """Каждый справочник из реестра работает через ?code=slug."""
        singles = {Kind: "kind", Color: "color", Size: "size"}
        values = {}
        for spec in FACETS:
            values[spec.code] = make_value(spec.model, f"значение {spec.code}",
                                           slug=f"val-{spec.code}")
        product = make_product(name="полный")
        for spec in FACETS:
            if spec.multiple:
                getattr(product, spec.field).set([values[spec.code]])
            else:
                setattr(product, spec.field, values[spec.code])
        product.save()
        make_product(name="пустой")
        for spec in FACETS:
            with self.subTest(code=spec.code):
                self.assertEqual(filtered(f"{spec.code}=val-{spec.code}"), [product])
        self.assertEqual(set(singles), {Kind, Color, Size})

    def test_chips_show_titles_not_slugs(self):
        params = QueryDict("flower=roza")
        titles = {"flower": {"roza": "Троянда"}}
        filterset = ProductFilterSet(params, Product.objects.catalog(), titles=titles)
        list(filterset.queryset)
        labels = [chip["label"] for chip in filterset.chips]
        self.assertTrue(any("Троянда" in label for label in labels), labels)


class OtherFilterTests(TestCase):
    def test_discount_flag(self):
        sale = make_product(price="80", old_price="100")
        make_product(price="80")
        self.assertEqual(filtered("discount=1"), [sale])

    def test_price_range(self):
        cheap = make_product(price="100")
        mid = make_product(price="500")
        make_product(price="900")
        self.assertEqual(set(filtered("price_min=100&price_max=500")), {cheap, mid})
        self.assertEqual(set(filtered("price_min=600")), set(filtered("price_min=600")))

    def test_garbage_price_is_ignored(self):
        make_product(price="100")
        self.assertEqual(len(filtered("price_min=abc")), 1)

    def test_availability(self):
        in_stock = make_product(stock=3)
        out = make_product(stock=0)
        self.assertEqual(filtered("stock=in"), [in_stock])
        self.assertEqual(filtered("stock=out"), [out])

    def test_category_includes_children(self):
        root = make_category("Букеты")
        child = make_category("Розы", parent=root)
        inside = make_product(category=child)
        make_product(category=make_category("Другое"))
        self.assertEqual(filtered(f"category={root.slug}"), [inside])


class SearchTests(TestCase):
    def test_cyrillic_search_ignores_case(self):
        """LIKE в SQLite чувствителен к регистру кириллицы (грабля 19)."""
        product = make_product(name="Пионы розовые", name_uk="Півонії рожеві")
        self.assertEqual(filtered("q=пионы"), [product])
        self.assertEqual(filtered("q=Півонії"), [product])
        self.assertEqual(filtered("q=півонії"), [product])

    def test_search_by_article_and_composition(self):
        product = make_product(article="ZZ-9", composition="эвкалипт, розы")
        make_product(article="AA-1")
        self.assertEqual(filtered("q=zz-9"), [product])
        self.assertEqual(filtered("q=эвкалипт"), [product])

    def test_search_by_flower_name(self):
        roza = make_value(Flower, "Роза", name_uk="Троянда")
        product = make_product(name="Букет", flowers=[roza])
        make_product(name="Другой")
        self.assertEqual(filtered("q=троянда"), [product])
        self.assertEqual(filtered("q=роза"), [product])
