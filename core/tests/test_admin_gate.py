"""Шлюз админки: код из Telegram, срок, пять попыток, пауза между отправками."""

import re
from unittest import mock

from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase, override_settings

from core import admin_gate

GATE_ON = {"TELEGRAM": {"TOKEN": "t", "CHAT_ID": "1"}, "ADMIN_TELEGRAM_GATE": True}


def make_request(path="/admin/", address="10.0.0.5"):
    request = RequestFactory().get(path, REMOTE_ADDR=address)
    SessionMiddleware(lambda r: None).process_request(request)
    return request


@override_settings(**GATE_ON)
class CodeTests(TestCase):
    def issue(self, request):
        with mock.patch("orders.notify.send_raw") as send:
            ok, _ = admin_gate.issue_code(request)
            self.assertTrue(ok)
            text = send.call_args[0][0]
        return re.search(r"<code>(\d+)</code>", text).group(1)

    def test_hash_only_in_session(self):
        request = make_request()
        code = self.issue(request)
        state = request.session[admin_gate.SESSION_KEY]
        self.assertNotIn(code, str(state))
        self.assertEqual(state["hash"], admin_gate._hash(code))

    def test_correct_code_passes(self):
        request = make_request()
        code = self.issue(request)
        ok, _ = admin_gate.check_code(request, code)
        self.assertTrue(ok)
        self.assertTrue(admin_gate.is_passed(request))
        self.assertNotIn(admin_gate.SESSION_KEY, request.session)

    def test_five_wrong_attempts_cancel_code(self):
        request = make_request()
        code = self.issue(request)
        wrong = "000000" if code != "000000" else "111111"
        for _ in range(admin_gate.MAX_ATTEMPTS - 1):
            ok, message = admin_gate.check_code(request, wrong)
            self.assertFalse(ok)
            self.assertIn("Осталось попыток", message)
        ok, message = admin_gate.check_code(request, wrong)
        self.assertFalse(ok)
        self.assertNotIn(admin_gate.SESSION_KEY, request.session)
        # даже верный код после аннулирования не работает
        ok, _ = admin_gate.check_code(request, code)
        self.assertFalse(ok)

    def test_expired_code(self):
        request = make_request()
        code = self.issue(request)
        request.session[admin_gate.SESSION_KEY]["expires"] = 0
        ok, message = admin_gate.check_code(request, code)
        self.assertFalse(ok)
        self.assertIn("просрочен", message)

    def test_resend_pause(self):
        request = make_request()
        self.issue(request)
        with mock.patch("orders.notify.send_raw"):
            ok, message = admin_gate.issue_code(request)
        self.assertFalse(ok)
        self.assertIn("уже отправлен", message)

    def test_no_code_requested(self):
        ok, _ = admin_gate.check_code(make_request(), "123456")
        self.assertFalse(ok)


@override_settings(**GATE_ON)
class MiddlewareTests(TestCase):
    def process(self, request):
        return admin_gate.AdminGateMiddleware(lambda r: None).process_request(request)

    @override_settings(ADMIN_GATE_ALLOW_LOCAL=False)
    def test_outsider_is_redirected_to_gate(self):
        response = self.process(make_request())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], admin_gate.GATE_PATH)

    @override_settings(ADMIN_GATE_ALLOW_LOCAL=True)
    def test_localhost_passes_when_allowed(self):
        self.assertIsNone(self.process(make_request(address="127.0.0.1")))

    @override_settings(ADMIN_GATE_ALLOW_LOCAL=False)
    def test_passed_session_goes_through(self):
        request = make_request()
        admin_gate.mark_passed(request)
        self.assertIsNone(self.process(request))

    def test_storefront_untouched(self):
        self.assertIsNone(self.process(make_request(path="/")))

    @override_settings(ADMIN_GATE_ALLOW_LOCAL=False)
    def test_gate_page_renders(self):
        response = self.client.get(admin_gate.GATE_PATH)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "код")

    @override_settings(TELEGRAM={"TOKEN": "", "CHAT_ID": ""})
    def test_gate_disabled_without_telegram(self):
        self.assertFalse(admin_gate.enabled())
        self.assertIsNone(self.process(make_request()))
