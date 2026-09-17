"""Catalog pages: list, category, product page, JSON, banner, filter panel."""

import json

from django.test import TestCase
from django.urls import reverse

from catalog.filters import Sorting
from core.tests.factories import (
    Flower, Occasion, Size, make_category, make_photo, make_product, make_status,
    make_value,
)


class CatalogPageTests(TestCase):
    def setUp(self):
        self.root = make_category("Букеты", name_uk="Букети")
        self.child = make_category("Розы", name_uk="Троянди", parent=self.root)
        self.product = make_product(name="Розы", name_uk="Троянди", category=self.child)
        self.hidden = make_product(name="скрытый", category=self.child, is_active=False)

    def test_index_lists_only_active(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.product.title)
        self.assertNotContains(response, "скрытый")

    def test_category_page_and_sorting_keep_category_in_form_action(self):
        response = self.client.get(self.root.get_absolute_url() + "?sort=cheap")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'action="{self.root.get_absolute_url()}"')
        self.assertContains(response, self.product.title)

    def test_json_answer_has_no_store_and_vary(self):
        """One URL serves HTML and JSON: JSON gets no-store, both get Vary."""
        html = self.client.get("/")
        self.assertIn("X-Requested-With", html.get("Vary", ""))

        response = self.client.get("/", HTTP_X_REQUESTED_WITH="fetch")
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("X-Requested-With", response["Vary"])
        data = json.loads(response.content)
        self.assertEqual(data["count"], 1)
        self.assertIn(self.product.title, data["html"])

    def test_product_page(self):
        response = self.client.get(self.product.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.product.title)
        # breadcrumbs: catalog → category → product
        self.assertContains(response, self.child.title)

    def test_inactive_product_is_404(self):
        self.assertEqual(self.client.get(self.hidden.get_absolute_url()).status_code, 404)

    def test_empty_category_hidden_from_menu(self):
        empty = make_category("Пустой", name_uk="Порожній")
        response = self.client.get("/")
        self.assertNotContains(response, empty.get_absolute_url())
        self.assertContains(response, self.root.get_absolute_url())

    def test_tile_shows_facet_values(self):
        roza = make_value(Flower, "Роза", name_uk="Троянда")
        size = make_value(Size, "Средний", name_uk="Середній")
        self.product.size = size
        self.product.save()
        self.product.flowers.set([roza])
        self.assertEqual(self.product.tile_values(), ["Троянда", "Середній"])
        response = self.client.get("/")
        self.assertContains(response, "Троянда · Середній")

    def test_card_add_form_works_without_js(self):
        response = self.client.get("/")
        self.assertContains(response, reverse("orders:form-add"))
        self.assertContains(response, 'name="quantity"')


class FacetPanelTests(TestCase):
    def setUp(self):
        from io import StringIO
        from django.core.management import call_command
        call_command("seed_facets", stdout=StringIO())

    def test_empty_group_is_hidden_but_selected_value_stays(self):
        roza = make_value(Flower, "Роза", slug="roza", name_uk="Троянда")
        make_value(Occasion, "Свадьба", slug="svadba", name_uk="Весілля")
        make_product(flowers=[roza])

        response = self.client.get("/")
        self.assertContains(response, 'name="flower"')
        # no product has an occasion — the group is absent entirely
        self.assertNotContains(response, 'name="occasion"')

        # a selected value stays even if no product has it
        response = self.client.get("/?occasion=svadba")
        self.assertContains(response, 'value="svadba"')


class BannerTests(TestCase):
    def setUp(self):
        self.a = make_category("A", name_uk="A")
        self.b = make_category("B", name_uk="B")
        self.a_products = [make_product(name=f"a{i}", category=self.a) for i in range(4)]
        self.b_products = [make_product(name=f"b{i}", category=self.b) for i in range(2)]
        for product in self.a_products + self.b_products:
            make_photo(product)

    def test_category_banner_shows_three_own_newest(self):
        response = self.client.get(self.a.get_absolute_url())
        banner = response.context["banner_products"]
        self.assertEqual(len(banner), 3)
        self.assertTrue(all(p.category == self.a for p in banner))
        self.assertEqual(banner[0], self.a_products[-1])

    def test_index_banner_takes_one_per_root(self):
        response = self.client.get("/")
        banner = response.context["banner_products"]
        self.assertEqual([p.category for p in banner], [self.a, self.b])

    def test_banner_skips_products_without_photo(self):
        make_product(name="без фото", category=make_category("C", name_uk="C"))
        banner = self.client.get("/").context["banner_products"]
        self.assertNotIn("без фото", [p.name for p in banner])

    def test_novinka_goes_first_in_banner(self):
        novinka = make_status("Новинка", slug=Sorting.NEW_STATUS_SLUG)
        first = self.a_products[0]
        first.status = novinka
        first.save()
        banner = self.client.get(self.a.get_absolute_url()).context["banner_products"]
        self.assertEqual(banner[0], first)
