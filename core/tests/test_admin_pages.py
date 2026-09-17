"""Custom admin templates (dashboard, delete confirmation) must not crash."""

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from core.tests import factories as f
from orders.models import Order

GATE_OFF = {"TELEGRAM": {"TOKEN": "", "CHAT_ID": ""}, "ADMIN_TELEGRAM_GATE": False}


@override_settings(ADMIN_LOCAL_ONLY=False, ADMIN_ACCESS_BY_IP=False, **GATE_OFF)
class AdminPagesTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("owner", "owner@example.com", "pass-12345-x")
        self.client.force_login(self.admin)
        self.flower = f.make_value(f.Flower, "Троянда", slug="troyanda")
        self.item = f.make_product(flowers=[self.flower])
        Order.objects.create(name="Покупець", phone="0501234567")

    def test_dashboard_and_lists(self):
        for url in ("/admin/", "/admin/catalog/product/", "/admin/orders/order/",
                    "/admin/catalog/facetgroup/", "/admin/catalog/flower/",
                    "/admin/catalog/category/", "/admin/auth/user/",
                    reverse("admin:catalog_product_change", args=[self.item.pk]),
                    reverse("admin:orders_order_change", args=[Order.objects.get().pk])):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_dashboard_is_russian_even_for_ukrainian_cookie(self):
        self.client.cookies["django_language"] = "uk"
        response = self.client.get("/admin/")
        self.assertContains(response, "Последние заказы")
        self.assertEqual(response.headers.get("Content-Language"), "ru")

    def test_delete_confirmation_lists_affected_products(self):
        url = reverse("admin:catalog_flower_delete", args=[self.flower.pk])
        response = self.client.get(url)
        self.assertContains(response, "привязано 1")
        self.assertContains(response, self.item.article)

    def test_single_admin_cannot_be_removed_or_added(self):
        self.assertEqual(self.client.get(reverse("admin:auth_user_add")).status_code, 403)
        response = self.client.get(reverse("admin:auth_user_change", args=[self.admin.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="is_superuser"')
