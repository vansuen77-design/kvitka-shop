"""Корзина в сессии: добавление, замена, удаление, итоги, порог доставки."""

from decimal import Decimal

from django.conf import settings
from django.test import RequestFactory, TestCase, override_settings
from django.contrib.sessions.middleware import SessionMiddleware

from core.tests.factories import make_product
from orders.cart import Cart


def make_request():
    request = RequestFactory().get("/")
    SessionMiddleware(lambda r: None).process_request(request)
    return request


def shop_with(**changes):
    return {**settings.SHOP, **changes}


class CartTests(TestCase):
    def setUp(self):
        self.request = make_request()
        self.cart = Cart(self.request)
        self.product = make_product(price="100", stock=5)

    def test_add_accumulates_and_respects_stock(self):
        self.assertEqual(self.cart.add(self.product, 2), 2)
        self.assertEqual(self.cart.add(self.product, 2), 4)
        # было 4, просим ещё 5 — остаток 5, итог обрезан
        self.assertEqual(self.cart.add(self.product, 5), 5)
        self.assertEqual(self.cart.totals.quantity, 5)

    def test_set_quantity_and_remove(self):
        self.cart.add(self.product, 2)
        self.cart.set_quantity(self.product.pk, 3)
        self.assertEqual(self.cart.totals.quantity, 3)
        self.cart.set_quantity(self.product.pk, 0)
        self.assertEqual(len(self.cart), 0)
        self.cart.add(self.product, 1)
        self.cart.remove(self.product.pk)
        self.assertFalse(self.cart)

    def test_clear(self):
        self.cart.add(self.product, 1)
        self.cart.clear()
        self.assertEqual(self.cart.totals.positions, 0)
        self.assertEqual(self.request.session[settings.CART_SESSION_KEY], {})

    def test_totals(self):
        other = make_product(price="250.50", stock=9)
        self.cart.add(self.product, 2)
        self.cart.add(other, 1)
        totals = self.cart.totals
        self.assertEqual(totals.positions, 2)
        self.assertEqual(totals.quantity, 3)
        self.assertEqual(totals.amount, Decimal("450.50"))

    def test_old_cart_is_trimmed_when_stock_drops(self):
        self.cart.add(self.product, 5)
        self.product.stock_quantity = 2
        self.product.save()
        fresh = Cart(self.request)
        self.assertEqual(fresh.totals.quantity, 2)

    def test_hidden_or_deleted_product_disappears(self):
        self.cart.add(self.product, 1)
        self.product.is_active = False
        self.product.save()
        self.assertEqual(Cart(self.request).totals.positions, 0)
        self.request.session[settings.CART_SESSION_KEY] = {"999999": 1, "junk": 2}
        self.assertEqual(Cart(self.request).totals.positions, 0)

    def test_persists_in_session(self):
        self.cart.add(self.product, 2)
        again = Cart(self.request)
        self.assertEqual(again.totals.quantity, 2)

    def test_as_dict_has_labels(self):
        self.cart.add(self.product, 1)
        data = self.cart.as_dict()
        self.assertEqual(data["positions"], 1)
        self.assertEqual(data["lines"][0]["name"], self.product.title)
        self.assertIn("₴", data["amount_label"])


class FreeDeliveryTests(TestCase):
    def setUp(self):
        self.request = make_request()

    def test_threshold_from_settings(self):
        """Порог читается из settings.SHOP — тесты не знают числа (грабля 23)."""
        with override_settings(SHOP=shop_with(FREE_DELIVERY_FROM=1000, DELIVERY_COST=120)):
            cart = Cart(self.request)
            cheap = make_product(price="400", stock=10)
            cart.add(cheap, 1)
            totals = cart.totals
            self.assertFalse(totals.free_delivery_reached)
            self.assertEqual(totals.free_delivery_gap, Decimal("600"))
            self.assertEqual(totals.free_delivery_progress, 40)
            self.assertEqual(totals.courier_cost, Decimal("120"))

            cart.add(cheap, 2)
            totals = cart.totals
            self.assertTrue(totals.free_delivery_reached)
            self.assertEqual(totals.free_delivery_gap, Decimal("0"))
            self.assertEqual(totals.free_delivery_progress, 100)
            self.assertEqual(totals.courier_cost, Decimal("0"))

    def test_empty_cart_never_reaches(self):
        with override_settings(SHOP=shop_with(FREE_DELIVERY_FROM=0)):
            totals = Cart(self.request).totals
            self.assertFalse(totals.free_delivery_reached)
            self.assertEqual(totals.free_delivery_progress, 100)
