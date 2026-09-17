"""Language, Russian admin, error pages, robots and sitemap."""

from django.conf import settings
from django.test import TestCase, override_settings

from core.tests.factories import make_category, make_product, make_user


class LanguageMiddlewareTests(TestCase):
    def test_admin_is_russian_even_with_ukrainian_cookie(self):
        user = make_user(email="admin@example.com")
        user.is_staff = user.is_superuser = True
        user.save()
        self.client.force_login(user)
        self.client.cookies["django_language"] = "uk"
        response = self.client.get("/admin/")
        self.assertEqual(response["Content-Language"], "ru")

    def test_middleware_order_matches_template(self):
        """Middleware order: sessions before the admin checks."""
        names = settings.MIDDLEWARE
        session = names.index("django.contrib.sessions.middleware.SessionMiddleware")
        access = names.index("core.middleware.AdminAccessMiddleware")
        gate = names.index("core.admin_gate.AdminGateMiddleware")
        default = names.index("core.middleware.DefaultLanguageMiddleware")
        locale = names.index("django.middleware.locale.LocaleMiddleware")
        admin_lang = names.index("core.middleware.AdminLanguageMiddleware")
        common = names.index("django.middleware.common.CommonMiddleware")
        self.assertLess(session, access)
        self.assertLess(session, gate)
        self.assertLess(default, locale)
        self.assertLess(locale, admin_lang)
        self.assertLess(admin_lang, common)
        self.assertEqual(settings.TIME_ZONE, "Europe/Kyiv")


class ErrorPagesTests(TestCase):
    def test_404_has_header_and_cart(self):
        response = self.client.get("/takoy-stranicy-net/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, settings.SHOP["NAME"], status_code=404)
        self.assertContains(response, "/korzina/", status_code=404)


class RobotsAndSitemapTests(TestCase):
    def test_robots_closes_service_paths(self):
        body = self.client.get("/robots.txt").content.decode()
        for path in ("/admin/", "/korzina/", "/kabinet/", "/vhod-v-upravlenie/"):
            self.assertIn(f"Disallow: {path}", body)
        self.assertIn("Sitemap:", body)

    def test_sitemap_lists_products_and_nonempty_categories(self):
        category = make_category("Букеты", name_uk="Букети")
        empty = make_category("Пусто", name_uk="Порожньо")
        product = make_product(category=category)
        index = self.client.get("/sitemap.xml")
        self.assertEqual(index.status_code, 200)
        products = self.client.get("/sitemap-products.xml").content.decode()
        self.assertIn(product.get_absolute_url(), products)
        categories = self.client.get("/sitemap-categories.xml").content.decode()
        self.assertIn(category.get_absolute_url(), categories)
        self.assertNotIn(empty.get_absolute_url(), categories)

    def test_canonical_drops_filters_keeps_page(self):
        for _ in range(settings.CATALOG_PAGE_SIZE + 1):
            make_product()
        response = self.client.get("/?sort=cheap&stock=in&page=2")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["canonical_url"].split("://", 1)[1].split("/", 1)[1],
                         "?page=2")
