"""Информационные страницы: разметка текста, подвал, страница согласия."""

from io import StringIO
from django.core.management import call_command
from django.test import TestCase
from django.utils import translation

from pages.context_processors import PRIVACY_SLUG
from pages.models import InfoPage


class BlocksTests(TestCase):
    def test_blocks_parse_titles_lists_and_text(self):
        page = InfoPage.objects.create(name="Тест", body=(
            "## Заголовок\nАбзац первый\n\n— пункт один\n- пункт два\n\nПоследний"
        ))
        kinds = [(b["kind"], b.get("text") or b.get("items")) for b in page.blocks()]
        self.assertEqual(kinds, [
            ("title", "Заголовок"), ("text", "Абзац первый"),
            ("list", ["пункт один", "пункт два"]), ("text", "Последний"),
        ])

    def test_body_follows_language(self):
        page = InfoPage.objects.create(name="Тест", body="рус", body_uk="укр", lead="л", lead_uk="")
        with translation.override("uk"):
            self.assertEqual(page.body_text, "укр")
            self.assertEqual(page.lead_text, "л")
        with translation.override("ru"):
            self.assertEqual(page.body_text, "рус")


class PageViewTests(TestCase):
    def setUp(self):
        call_command("seed_pages", stdout=StringIO())

    def test_seeded_pages_open_in_both_languages(self):
        for page in InfoPage.objects.active().filter(external_url=""):
            with self.subTest(slug=page.slug):
                self.assertEqual(self.client.get(page.get_absolute_url()).status_code, 200)
                self.client.cookies["django_language"] = "ru"
                self.assertEqual(self.client.get(page.get_absolute_url()).status_code, 200)

    def test_privacy_page_exists_and_linked_in_cart(self):
        page = InfoPage.objects.get(slug=PRIVACY_SLUG)
        response = self.client.get("/korzina/")
        self.assertContains(response, page.get_absolute_url())

    def test_footer_columns(self):
        response = self.client.get("/")
        buyer = response.context["footer_buyer"]
        partner = response.context["footer_partner"]
        self.assertTrue(buyer)
        self.assertTrue(partner)
        self.assertTrue(all(p.group == InfoPage.Group.BUYER for p in buyer))

    def test_hidden_page_not_in_footer_but_opens(self):
        page = InfoPage.objects.first()
        page.group = InfoPage.Group.HIDDEN
        page.save()
        response = self.client.get("/")
        self.assertNotIn(page, response.context["footer_buyer"])
        self.assertEqual(self.client.get(page.get_absolute_url()).status_code, 200)

    def test_inactive_page_404(self):
        page = InfoPage.objects.first()
        page.is_active = False
        page.save()
        self.assertEqual(self.client.get(page.get_absolute_url()).status_code, 404)
