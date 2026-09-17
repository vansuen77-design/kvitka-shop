"""Service middleware.
Code by ISHOD, 2026. All rights to the source code belong to the author.
"""

import ipaddress
import logging

from django.conf import settings
from django.http import Http404
from django.utils import translation
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger("kvitka")


class NoCacheMiddleware(MiddlewareMixin):
    """Forbids the browser to cache pages.

    During development the browser happily serves a page from its cache —
    after an update you still see the old layout until Ctrl+F5.
    Enabled only under DEBUG (see config/settings.py).
    """

    def process_response(self, request, response):
        response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"
        return response


class AdminAccessMiddleware(MiddlewareMixin):
    """Lets only allowed IP addresses reach the admin panel.

    The site is open to the whole internet, so /admin/ is visible to
    everyone and the password is the only protection. Bots will try to
    guess it around the clock. So only our own addresses reach the login form.

    WHERE THE IP COMES FROM. The site sits behind a Cloudflare tunnel, so the
    connection to Django always arrives from 127.0.0.1 — visitors cannot be
    told apart by it. Cloudflare puts the real address into the
    CF-Connecting-IP header, and that is what we check.

    WHY THE HEADER CAN BE TRUSTED. Normally a header can be forged, but not
    here: the server listens on 127.0.0.1 only, no port is exposed, and the
    only way in is the tunnel. Inside the tunnel Cloudflare overwrites
    CF-Connecting-IP with its own value whatever the client sent. If you
    leave the tunnel and open a port to the internet, this check must be
    reworked — see deploy/INSTALL.md.

    FALLBACK. Requests from the server itself (127.0.0.1) always pass.
    That is not a hole: loopback cannot be reached from outside, but you can
    forward the port over SSH and open the admin that way even if your IP
    has changed:

        ssh -L 8000:127.0.0.1:8000 kvitka@SERVER
        then http://127.0.0.1:8000/admin/ in the browser

    CONFIGURATION. Normal mode: the address is not checked, but the admin is
    behind a gate with a one-time code from Telegram (core/admin_gate.py).
    Password plus code — two steps, and the second one reaches the owner only.

    Stricter options via .env:

        ADMIN_ALLOWED_IPS=91.203.10.55, 2a02:1810::/32
            allow only these addresses, and the code is still asked

        ADMIN_LOCAL_ONLY=1
            no admin from outside at all, SSH tunnel only
    """

    HEADER = "HTTP_CF_CONNECTING_IP"

    def client_ip(self, request) -> str:
        """Visitor address: from the Cloudflare header, else from the connection."""
        header = request.META.get(self.HEADER, "")
        if header:
            # the header may be a list: the first address is the original client
            return header.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "")

    def is_allowed(self, address: str) -> bool:
        if not address:
            return False
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            return False
        if ip.is_loopback:
            return True
        # "local only" mode: the address list is ignored entirely, so that a
        # line forgotten in .env cannot open the admin to the outside
        if settings.ADMIN_LOCAL_ONLY:
            return False
        return any(ip in network for network in settings.ADMIN_ALLOWED_NETWORKS)

    def guarding(self) -> bool:
        """Whether the address should be checked at all.

        Three cases:

        * ADMIN_LOCAL_ONLY — always check, there is no admin from outside;
        * ADMIN_ALLOWED_IPS is filled — check against it;
        * the list is empty and the Telegram code gate is on — do not check.
          Otherwise nobody would reach the gate: the address is cut off
          earlier and there is nobody to ask for the code.

        If there is no list and the gate is off, the admin would stay open to
        the whole internet behind a single password. We do not do that:
        in that case only the server itself is allowed in.
        """
        if settings.ADMIN_LOCAL_ONLY:
            return True
        if not settings.ADMIN_ACCESS_BY_IP:
            return False
        if settings.ADMIN_ALLOWED_NETWORKS:
            return True
        from core.admin_gate import enabled as gate_enabled
        return not gate_enabled()

    def process_request(self, request):
        if not self.guarding():
            return None
        if not request.path.startswith(settings.ADMIN_PATH):
            return None

        address = self.client_ip(request)
        if self.is_allowed(address):
            return None

        # log the address: if the ISP changed or you are elsewhere, look at
        # the log line and add the address to .env
        logger.warning("Admin panel: denied address %s (%s)", address or "unknown",
                       request.path)
        # 404, not 403: let it look as if there were no admin here
        raise Http404


class DefaultLanguageMiddleware(MiddlewareMixin):
    """Ukrainian by default, whatever the browser says.

    Django picks the language like this: cookie → Accept-Language header →
    LANGUAGE_CODE. The middle step is harmful for a Ukrainian shop: many
    customers have a Russian browser and landed on the Russian version
    without even knowing a Ukrainian one exists.

    So Accept-Language is switched off: the language comes from the cookie,
    and if the visitor never used the switcher — Ukrainian.

    The visitor's choice is fully respected: pressed RUS — the cookie is set
    and the site stays Russian until they change their mind.

    Placed BEFORE LocaleMiddleware — it reads the already cleaned header.
    """

    HEADER = "HTTP_ACCEPT_LANGUAGE"

    def process_request(self, request):
        if request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME):
            return None      # explicit choice — do not interfere
        request.META.pop(self.HEADER, None)
        return None


class AdminLanguageMiddleware(MiddlewareMixin):
    """Keeps the admin panel in Russian, whatever the browser says.

    The storefront is bilingual and the visitor picks the language. But the
    admin is the owner's workplace: with a Ukrainian browser Django's own
    labels would be translated while field names stayed Russian — a mess.

    Placed after LocaleMiddleware to override the language it picked.
    """

    LANGUAGE = "ru"

    def process_request(self, request):
        if request.path.startswith(settings.ADMIN_PATH):
            translation.activate(self.LANGUAGE)
            request.LANGUAGE_CODE = self.LANGUAGE
        return None
