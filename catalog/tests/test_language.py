"""Bilingual UI: the product name is always Ukrainian, the rest follows the page language."""

from io import StringIO
from django.test import TestCase, override_settings
from django.utils import translation

from catalog.facets import FACETS
from catalog.models import FacetGroup
from core.tests.factories import Flower, make_product, make_value


class TitleTests(TestCase):
    def test_product_title_is_ukrainian_on_both_languages(self):
        product = make_product(name="Розы", name_uk="Троянди")
        with translation.override("ru"):
            self.assertEqual(product.title, "Троянди")
        with translation.override("uk"):
            self.assertEqual(product.title, "Троянди")

    def test_product_title_falls_back_to_russian(self):
        product = make_product(name="Розы", name_uk="")
        self.assertEqual(product.title, "Розы")

    def test_reference_title_follows_language(self):
        value = make_value(Flower, "Роза", name_uk="Троянда")
        with translation.override("ru"):
            self.assertEqual(value.title, "Роза")
        with translation.override("uk"):
            self.assertEqual(value.title, "Троянда")

    def test_description_and_composition_fall_back(self):
        product = make_product(description="описание", description_uk="",
                               composition="состав", composition_uk="склад")
        with translation.override("uk"):
            self.assertEqual(product.description_text, "описание")
            self.assertEqual(product.composition_text, "склад")
        with translation.override("ru"):
            self.assertEqual(product.composition_text, "состав")


class FacetLabelTests(TestCase):
    def test_facet_labels_translated_from_po(self):
        """Filter group labels come from .po, not from a dictionary in code."""
        with translation.override("uk"):
            for spec in FACETS:
                with self.subTest(label=spec.label):
                    from django.utils.translation import trans_real
                    self.assertIn(spec.label, trans_real.translation("uk")._catalog)

    def test_seed_facets_fills_ukrainian_names(self):
        from django.core.management import call_command

        call_command("seed_facets", stdout=StringIO())
        for spec in FACETS:
            group = FacetGroup.objects.get(code=spec.code)
            self.assertTrue(group.name_uk, spec.code)

    def test_specification_labels_are_ukrainian(self):
        product = make_product(stems=5)
        with translation.override("uk"):
            rows = dict(product.specification_rows())
        self.assertIn("Квіток у букеті", rows)


class LanguageSwitchTests(TestCase):
    def test_ukrainian_by_default_despite_russian_browser(self):
        response = self.client.get("/", HTTP_ACCEPT_LANGUAGE="ru")
        self.assertEqual(response["Content-Language"], "uk")

    def test_cookie_wins(self):
        self.client.cookies["django_language"] = "ru"
        response = self.client.get("/")
        self.assertEqual(response["Content-Language"], "ru")

    def test_switcher_sets_cookie_without_js(self):
        response = self.client.post("/i18n/setlang/", {"language": "ru", "next": "/"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.cookies["django_language"].value, "ru")
