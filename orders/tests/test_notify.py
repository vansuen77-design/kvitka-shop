"""Уведомления: текст для Telegram собирается, без токена — молчим,
письмо покупателю уходит на его языке."""

import datetime
from decimal import Decimal
from unittest import mock

from django.core import mail
from django.test import TestCase, override_settings

from orders import notify
from orders.models import Order, OrderLine


def make_order(**extra):
    order = Order.objects.create(
        name="Оля", phone="+380501112233", address="вул. Садова, 5",
        delivery_date=datetime.date(2026, 9, 20), delivery_time="12-15",
        recipient_name="Марія", card_text="З днем народження!", **extra,
    )
    OrderLine.objects.create(order=order, article="R-11", product_name="Троянди",
                             quantity=2, unit_price=Decimal("890"))
    order.recalculate()
    return order


class BuildMessageTests(TestCase):
    def test_message_has_delivery_details(self):
        text = notify.build_message(make_order())
        for piece in ("Заказ №", "Оля", "+380501112233", "вул. Садова, 5",
                      "20.09.2026", "12:00–15:00", "Марія", "З днем народження!",
                      "R-11", "Троянди", "2 шт", "Итого"):
            self.assertIn(piece, text)

    def test_pickup_message(self):
        text = notify.build_message(make_order(delivery=Order.Delivery.PICKUP))
        self.assertIn("Самовывоз", text)

    def test_html_is_escaped(self):
        text = notify.build_message(make_order(comment="<b>жирно</b>"))
        self.assertIn("&lt;b&gt;", text)

    @override_settings(TELEGRAM={"TOKEN": "", "CHAT_ID": ""})
    def test_disabled_without_token(self):
        self.assertFalse(notify.enabled())
        with mock.patch("orders.notify.threading.Thread") as thread:
            notify.notify_new_order(make_order())
        thread.assert_not_called()

    @override_settings(TELEGRAM={"TOKEN": "t", "CHAT_ID": "1"})
    def test_sends_in_background_when_enabled(self):
        with mock.patch("orders.notify.threading.Thread") as thread:
            notify.notify_new_order(make_order())
        thread.assert_called_once()
        thread.return_value.start.assert_called_once()


class CustomerEmailTests(TestCase):
    @override_settings(TELEGRAM={"TOKEN": "", "CHAT_ID": ""})
    def test_no_email_no_letter(self):
        notify.notify_new_order(make_order(), background=False)
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(TELEGRAM={"TOKEN": "", "CHAT_ID": ""})
    def test_letter_in_customer_language(self):
        order = make_order(email="olya@example.com", language="uk")
        notify.notify_new_order(order, background=False)
        self.assertEqual(len(mail.outbox), 1)
        letter = mail.outbox[0]
        self.assertEqual(letter.to, ["olya@example.com"])
        self.assertIn(order.number, letter.subject)
        self.assertIn("Троянди", letter.body)
        self.assertIn("R-11", letter.body)
        # тема и тело — на украинском, а не на языке текущего потока
        self.assertIn("прийнято", letter.subject)
        self.assertNotIn("Здравствуйте", letter.body)

    @override_settings(TELEGRAM={"TOKEN": "", "CHAT_ID": ""})
    def test_letter_in_russian(self):
        notify.notify_new_order(make_order(email="o@example.com", language="ru"), background=False)
        self.assertIn("Здравствуйте, Оля", mail.outbox[0].body)

    @override_settings(TELEGRAM={"TOKEN": "", "CHAT_ID": ""})
    def test_email_goes_in_background_thread(self):
        with mock.patch("orders.notify.threading.Thread") as thread:
            notify.notify_new_order(make_order(email="o@example.com"))
        thread.assert_called_once()
        self.assertEqual(len(mail.outbox), 0)
