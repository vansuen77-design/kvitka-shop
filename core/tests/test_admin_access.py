"""Admin access by address: the guarding() decision table and refusal via 404."""

import ipaddress

from django.test import RequestFactory, TestCase, override_settings

from core.middleware import AdminAccessMiddleware

NET = [ipaddress.ip_network("91.203.10.0/24")]
GATE_ON = {"TELEGRAM": {"TOKEN": "t", "CHAT_ID": "1"}, "ADMIN_TELEGRAM_GATE": True}
GATE_OFF = {"TELEGRAM": {"TOKEN": "", "CHAT_ID": ""}, "ADMIN_TELEGRAM_GATE": False}


class GuardingTests(TestCase):
    def guarding(self):
        return AdminAccessMiddleware(lambda r: None).guarding()

    @override_settings(ADMIN_LOCAL_ONLY=True, ADMIN_ALLOWED_NETWORKS=[], **GATE_ON)
    def test_local_only_always_guards(self):
        self.assertTrue(self.guarding())

    @override_settings(ADMIN_LOCAL_ONLY=False, ADMIN_ACCESS_BY_IP=False, **GATE_OFF)
    def test_disabled_by_setting(self):
        self.assertFalse(self.guarding())

    @override_settings(ADMIN_LOCAL_ONLY=False, ADMIN_ACCESS_BY_IP=True,
                       ADMIN_ALLOWED_NETWORKS=NET, **GATE_ON)
    def test_list_given_guards(self):
        self.assertTrue(self.guarding())

    @override_settings(ADMIN_LOCAL_ONLY=False, ADMIN_ACCESS_BY_IP=True,
                       ADMIN_ALLOWED_NETWORKS=[], **GATE_ON)
    def test_empty_list_with_gate_does_not_guard(self):
        self.assertFalse(self.guarding())

    @override_settings(ADMIN_LOCAL_ONLY=False, ADMIN_ACCESS_BY_IP=True,
                       ADMIN_ALLOWED_NETWORKS=[], **GATE_OFF)
    def test_empty_list_without_gate_guards(self):
        """No list and no gate — only the server itself is allowed in."""
        self.assertTrue(self.guarding())


@override_settings(ADMIN_LOCAL_ONLY=False, ADMIN_ACCESS_BY_IP=True,
                   ADMIN_ALLOWED_NETWORKS=NET, **GATE_ON)
class AccessTests(TestCase):
    def test_stranger_gets_our_404_not_500(self):
        response = self.client.get("/admin/", REMOTE_ADDR="8.8.8.8")
        self.assertEqual(response.status_code, 404)
        # our 404 page with the header, not a bare error
        self.assertContains(response, "404", status_code=404)

    def test_allowed_address_from_cloudflare_header(self):
        response = self.client.get("/admin/", REMOTE_ADDR="127.0.0.1",
                                   HTTP_CF_CONNECTING_IP="91.203.10.55")
        self.assertNotEqual(response.status_code, 404)

    def test_loopback_always_allowed(self):
        middleware = AdminAccessMiddleware(lambda r: None)
        self.assertTrue(middleware.is_allowed("127.0.0.1"))
        self.assertFalse(middleware.is_allowed("8.8.8.8"))
        self.assertFalse(middleware.is_allowed("garbage"))

    @override_settings(ADMIN_LOCAL_ONLY=True)
    def test_local_only_ignores_list(self):
        middleware = AdminAccessMiddleware(lambda r: None)
        self.assertFalse(middleware.is_allowed("91.203.10.55"))
        self.assertTrue(middleware.is_allowed("::1"))

    def test_storefront_not_affected(self):
        self.assertEqual(self.client.get("/", REMOTE_ADDR="8.8.8.8").status_code, 200)
