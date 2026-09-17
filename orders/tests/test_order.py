"""Checkout: the cart page, no-JS forms, API, "thank you"."""

import datetime
import json
from decimal import Decimal

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.tests.factories import make_product, make_status, make_user
from orders.models import Order


def shop_with(**changes):
    return {**settings.SHOP, **changes}


def order_data(**changes):
    data = {
        "name": "Тест", "phone": "+380671234567", "email": "",
        "delivery": Order.Delivery.COURIER, "address": "вул. Тестова, 1",
        "delivery_date": timezone.localdate().isoformat(), "delivery_time": "12-15",
        "recipient_name": "", "recipient_phone": "", "card_text": "",
        "payment": Order.Payment.CASH, "comment": "", "agree": "on",
    }
    data.update(changes)
    return data


class CartApiTests(TestCase):
    def setUp(self):
        self.product = make_product(price="300", stock=4)

    def post_json(self, name, payload):
        return self.client.post(reverse(name), data=json.dumps(payload),
                                content_type="application/json")

    def test_add_update_remove_clear(self):
        response = self.post_json("orders:api-add", {"product": self.product.pk, "quantity": 2})
        data = json.loads(response.content)
        self.assertTrue(data["ok"])
        self.assertEqual(data["cart"]["quantity"], 2)
        self.assertIn(self.product.title, data["html"])

        response = self.post_json("orders:api-update", {"product": self.product.pk, "quantity": 99})
        self.assertEqual(json.loads(response.content)["cart"]["quantity"], 4)

        response = self.post_json("orders:api-remove", {"product": self.product.pk})
        self.assertEqual(json.loads(response.content)["cart"]["positions"], 0)

        self.post_json("orders:api-add", {"product": self.product.pk, "quantity": 1})
        response = self.post_json("orders:api-clear", {})
        self.assertEqual(json.loads(response.content)["cart"]["positions"], 0)

    def test_add_rejects_bad_input(self):
        for payload in ({"product": 999999, "quantity": 1},
                        {"product": self.product.pk, "quantity": "x"},
                        {"product": self.product.pk, "quantity": 0}):
            response = self.post_json("orders:api-add", payload)
            self.assertEqual(response.status_code, 400, payload)
            self.assertFalse(json.loads(response.content)["ok"])

    def test_add_rejects_not_orderable(self):
        gone = make_status("Снят", orderable=False)
        product = make_product(status=gone, stock=3)
        response = self.post_json("orders:api-add", {"product": product.pk, "quantity": 1})
        self.assertEqual(response.status_code, 400)


class NoJsFormsTests(TestCase):
    def setUp(self):
        self.product = make_product(price="300", stock=4)

    def test_form_add_redirects_to_cart(self):
        response = self.client.post(reverse("orders:form-add"),
                                    {"product": self.product.pk, "quantity": 9})
        self.assertRedirects(response, reverse("orders:cart"))
        session_cart = self.client.session[settings.CART_SESSION_KEY]
        self.assertEqual(session_cart[str(self.product.pk)], 4)

    def test_form_add_unknown_product_is_404(self):
        response = self.client.post(reverse("orders:form-add"), {"product": 999, "quantity": 1})
        self.assertEqual(response.status_code, 404)

    def test_form_update_and_remove(self):
        self.client.post(reverse("orders:form-add"), {"product": self.product.pk, "quantity": 1})
        self.client.post(reverse("orders:form-update"), {"product": self.product.pk, "quantity": 3})
        self.assertEqual(self.client.session[settings.CART_SESSION_KEY][str(self.product.pk)], 3)
        self.client.post(reverse("orders:form-update"),
                         {"product": self.product.pk, "quantity": 3, "remove": "1"})
        self.assertEqual(self.client.session[settings.CART_SESSION_KEY], {})

    def test_cart_page_has_line_forms(self):
        self.client.post(reverse("orders:form-add"), {"product": self.product.pk, "quantity": 1})
        response = self.client.get(reverse("orders:cart"))
        self.assertContains(response, reverse("orders:form-update"))
        self.assertContains(response, 'name="remove"')


class CheckoutTests(TestCase):
    def setUp(self):
        self.product = make_product(name="Розы", name_uk="Троянди", price="400", stock=10,
                                    article="R-1")
        self.client.post(reverse("orders:form-add"), {"product": self.product.pk, "quantity": 2})

    def test_order_copies_lines_and_clears_cart(self):
        response = self.client.post(reverse("orders:cart"), order_data(card_text="З любов'ю"))
        order = Order.objects.get()
        self.assertRedirects(response, reverse("orders:success", args=[order.pk]))
        line = order.lines.get()
        self.assertEqual((line.article, line.product_name, line.unit_price, line.quantity),
                         ("R-1", "Троянди", Decimal("400"), 2))
        self.assertEqual(order.goods_amount, Decimal("800"))
        self.assertEqual(order.total_quantity, 2)
        self.assertEqual(order.card_text, "З любов'ю")
        self.assertEqual(self.client.session[settings.CART_SESSION_KEY], {})

    def test_order_remembers_language(self):
        self.client.post(reverse("orders:cart"), order_data())
        self.assertEqual(Order.objects.get().language, "uk")
        self.client.cookies["django_language"] = "ru"
        self.client.post(reverse("orders:form-add"), {"product": self.product.pk, "quantity": 1})
        self.client.post(reverse("orders:cart"), order_data())
        self.assertEqual(Order.objects.latest("pk").language, "ru")

    def test_line_survives_product_deletion(self):
        self.client.post(reverse("orders:cart"), order_data())
        self.product.delete()
        line = Order.objects.get().lines.get()
        self.assertIsNone(line.product)
        self.assertEqual(line.product_name, "Троянди")

    def test_delivery_cost_rules(self):
        with override_settings(SHOP=shop_with(FREE_DELIVERY_FROM=1000, DELIVERY_COST=150)):
            self.client.post(reverse("orders:cart"), order_data())
            order = Order.objects.latest("pk")
            self.assertEqual(order.delivery_cost, Decimal("150"))
            self.assertEqual(order.total_amount, Decimal("950"))

            self.client.post(reverse("orders:form-add"), {"product": self.product.pk, "quantity": 3})
            self.client.post(reverse("orders:cart"), order_data())
            order = Order.objects.latest("pk")
            self.assertEqual(order.delivery_cost, Decimal("0"))
            self.assertEqual(order.total_amount, Decimal("1200"))

            self.client.post(reverse("orders:form-add"), {"product": self.product.pk, "quantity": 1})
            self.client.post(reverse("orders:cart"),
                             order_data(delivery=Order.Delivery.PICKUP, address=""))
            order = Order.objects.latest("pk")
            self.assertEqual(order.delivery_cost, Decimal("0"))
            self.assertTrue(order.is_pickup)

    def test_courier_requires_address_and_date(self):
        response = self.client.post(reverse("orders:cart"), order_data(address="", delivery_date=""))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors.get("address"))
        self.assertTrue(response.context["form"].errors.get("delivery_date"))
        self.assertEqual(Order.objects.count(), 0)

    def test_pickup_does_not_need_address(self):
        response = self.client.post(reverse("orders:cart"),
                                    order_data(delivery=Order.Delivery.PICKUP, address=""))
        self.assertEqual(response.status_code, 302)

    def test_past_date_rejected(self):
        yesterday = (timezone.localdate() - datetime.timedelta(days=1)).isoformat()
        response = self.client.post(reverse("orders:cart"), order_data(delivery_date=yesterday))
        self.assertTrue(response.context["form"].errors.get("delivery_date"))

    def test_short_phone_rejected(self):
        response = self.client.post(reverse("orders:cart"), order_data(phone="123"))
        self.assertTrue(response.context["form"].errors.get("phone"))

    def test_empty_cart_cannot_checkout(self):
        self.client.post(reverse("orders:api-clear"), data="{}", content_type="application/json")
        response = self.client.post(reverse("orders:cart"), order_data())
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].non_field_errors())

    def test_success_page_is_private(self):
        self.client.post(reverse("orders:cart"), order_data())
        order = Order.objects.get()
        url = reverse("orders:success", args=[order.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        stranger = self.client_class()
        self.assertEqual(stranger.get(url).status_code, 404)

    def test_logged_in_user_is_linked_and_prefilled(self):
        user = make_user(name="Оля")
        from accounts.models import Profile
        Profile.objects.create(user=user, phone="+380501112233", address="вул. Садова, 5")
        self.client.force_login(user)
        response = self.client.get(reverse("orders:cart"))
        self.assertEqual(response.context["form"].initial["address"], "вул. Садова, 5")
        self.client.post(reverse("orders:cart"), order_data())
        self.assertEqual(Order.objects.get().user, user)


class OrderModelTests(TestCase):
    def test_number_and_open(self):
        order = Order.objects.create(name="a", phone="+380000000000")
        self.assertEqual(order.number, f"№{order.pk:05d}")
        self.assertTrue(order.is_open)
        order.status = Order.Status.DONE
        self.assertFalse(order.is_open)

    def test_delivery_cost_for(self):
        with override_settings(SHOP=shop_with(FREE_DELIVERY_FROM=500, DELIVERY_COST=99)):
            self.assertEqual(Order.delivery_cost_for(Order.Delivery.PICKUP, 10), Decimal("0"))
            self.assertEqual(Order.delivery_cost_for(Order.Delivery.COURIER, 499), Decimal("99"))
            self.assertEqual(Order.delivery_cost_for(Order.Delivery.COURIER, 500), Decimal("0"))
