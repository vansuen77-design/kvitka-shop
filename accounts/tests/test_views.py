"""Account: registration, own and foreign orders, favourites, next."""

import json

from django.test import TestCase
from django.urls import reverse

from accounts.models import Favorite, Profile
from core.tests.factories import make_product, make_user
from orders.models import Order


class RegisterTests(TestCase):
    def test_register_creates_profile_and_logs_in(self):
        response = self.client.post(reverse("accounts:register"), {
            "name": "Оля", "email": "olya@example.com", "phone": "+380501112233",
            "address": "вул. Садова, 5", "password1": "strong-pass-2026",
            "password2": "strong-pass-2026", "agree": "on",
        })
        self.assertRedirects(response, reverse("accounts:dashboard"))
        profile = Profile.objects.get(user__email="olya@example.com")
        self.assertEqual(profile.address, "вул. Садова, 5")
        self.assertEqual(profile.user.username, "olya@example.com")

    def test_duplicate_email_rejected(self):
        make_user(email="olya@example.com")
        response = self.client.post(reverse("accounts:register"), {
            "name": "Оля", "email": "OLYA@example.com", "phone": "+380501112233",
            "password1": "strong-pass-2026", "password2": "strong-pass-2026", "agree": "on",
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors.get("email"))


class OrdersInCabinetTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.other = make_user(email="other@example.com")
        self.mine = Order.objects.create(user=self.user, name="я", phone="+380000000001")
        self.theirs = Order.objects.create(user=self.other, name="не я", phone="+380000000002")

    def test_requires_login(self):
        response = self.client.get(reverse("accounts:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

    def test_own_order_visible_foreign_404(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("accounts:order", args=[self.mine.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("accounts:order", args=[self.theirs.pk])).status_code, 404)
        history = self.client.get(reverse("accounts:orders"))
        self.assertContains(history, self.mine.number)
        self.assertNotContains(history, self.theirs.number)


class FavoritesTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.product = make_product()

    def toggle(self):
        return self.client.post(reverse("accounts:favorite-toggle"),
                                data=json.dumps({"product": self.product.pk}),
                                content_type="application/json")

    def test_guest_is_refused(self):
        self.assertEqual(self.toggle().status_code, 400)

    def test_toggle_on_and_off(self):
        self.client.force_login(self.user)
        data = json.loads(self.toggle().content)
        self.assertTrue(data["active"])
        self.assertEqual(Favorite.objects.filter(user=self.user).count(), 1)
        data = json.loads(self.toggle().content)
        self.assertFalse(data["active"])
        self.assertEqual(data["total"], 0)

    def test_favorites_page_lists_product(self):
        self.client.force_login(self.user)
        Favorite.objects.create(user=self.user, product=self.product)
        response = self.client.get(reverse("accounts:favorites"))
        self.assertContains(response, self.product.title)


class LoginRedirectTests(TestCase):
    def test_next_to_foreign_host_is_ignored(self):
        """Every next is validated — no open redirect."""
        make_user(email="a@example.com", password="strong-pass-2026")
        response = self.client.post(reverse("accounts:login") + "?next=https://evil.example/",
                                    {"username": "a@example.com", "password": "strong-pass-2026"})
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("evil.example", response["Location"])

    def test_next_to_own_page_is_kept(self):
        make_user(email="a@example.com", password="strong-pass-2026")
        response = self.client.post(reverse("accounts:login") + "?next=/kabinet/izbrannoe/",
                                    {"username": "a@example.com", "password": "strong-pass-2026"})
        self.assertEqual(response["Location"], "/kabinet/izbrannoe/")
