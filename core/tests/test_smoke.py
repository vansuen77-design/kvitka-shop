"""Дымовые проверки: главные адреса отвечают, чужое — 404, админка за шлюзом."""

from django.test import TestCase, override_settings

GATE_ON = {"TELEGRAM": {"TOKEN": "t", "CHAT_ID": "1"}, "ADMIN_TELEGRAM_GATE": True}


class SmokeTests(TestCase):
    def test_pages_answer(self):
        for url in ("/", "/korzina/", "/kabinet/vhod/", "/kabinet/registratsiya/",
                    "/price/xlsx/", "/price/xml/", "/robots.txt", "/sitemap.xml"):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_unknown_page_is_404(self):
        self.assertEqual(self.client.get("/tovar/net-takogo/").status_code, 404)
        self.assertEqual(self.client.get("/katalog/net-takogo/").status_code, 404)

    @override_settings(ADMIN_LOCAL_ONLY=False, ADMIN_ACCESS_BY_IP=False,
                       ADMIN_GATE_ALLOW_LOCAL=False, **GATE_ON)
    def test_admin_without_code_goes_to_gate(self):
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/vhod-v-upravlenie/")
