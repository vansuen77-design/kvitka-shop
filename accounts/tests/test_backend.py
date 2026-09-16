"""Вход по почте: без учёта регистра, дубль почты не пускает никого."""

from django.contrib.auth import authenticate, get_user_model
from django.test import TestCase

from core.tests.factories import make_user

User = get_user_model()


class EmailBackendTests(TestCase):
    def setUp(self):
        self.user = make_user(email="Buyer@Example.com", password="correct-horse-9")

    def test_login_ignores_case(self):
        self.assertEqual(authenticate(username="buyer@example.com", password="correct-horse-9"),
                         self.user)

    def test_wrong_password(self):
        self.assertIsNone(authenticate(username="buyer@example.com", password="nope"))

    def test_unknown_email_and_empty(self):
        self.assertIsNone(authenticate(username="nobody@example.com", password="x"))
        self.assertIsNone(authenticate(username="", password="x"))
        self.assertIsNone(authenticate(username="buyer@example.com", password=None))

    def test_duplicate_email_lets_nobody_in(self):
        User.objects.create_user(username="twin", email="buyer@example.com",
                                 password="correct-horse-9")
        self.assertIsNone(authenticate(username="buyer@example.com", password="correct-horse-9"))

    def test_inactive_user_rejected(self):
        self.user.is_active = False
        self.user.save()
        self.assertIsNone(authenticate(username="buyer@example.com", password="correct-horse-9"))

    def test_login_form_works(self):
        response = self.client.post("/kabinet/vhod/", {"username": "BUYER@example.com",
                                                        "password": "correct-horse-9"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)
