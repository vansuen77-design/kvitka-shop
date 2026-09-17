"""Admin login with a one-time code from Telegram.

The problem. The admin panel is open from the internet — convenient to use
from any computer. But then the password is the only barrier, and bots
guess passwords around the clock.

The solution. Our gate stands in front of Django's login form: until the
session carries a "code passed" mark, a "Send me the code" page is shown
instead of the admin. The code goes to the owner's Telegram — the one
person whose id is in .env. Without access to that Telegram nobody gets in,
even knowing the username and password.

Implementation notes:

* The code is stored as a hash, not plain text. Sessions live in the
  database, and a leaked database must not reveal valid codes.
* It lives five minutes and burns after the first successful check.
* Five wrong attempts — the code is cancelled entirely, a new one is
  needed. Otherwise a six-digit number is brute-forced in an evening.
* A new code may be requested no more than once every 45 seconds:
  otherwise the gate becomes a "spam the owner" button.
* Requests from the server itself (127.0.0.1) bypass the gate. That is
  the fallback entrance through an SSH tunnel when Telegram is down.

Code by ISHOD, 2026.
"""

from __future__ import annotations

import hmac
import logging
import secrets
from hashlib import sha256

from django.conf import settings
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger("kvitka")

SESSION_KEY = "admin_gate"          # holds: code hash, expiry, attempts
PASSED_KEY = "admin_gate_passed"    # until when we let in without a code
NEXT_KEY = "admin_gate_next"        # where to return after the check

# gate page path — so that reverse() is not called on every request
GATE_PATH = "/vhod-v-upravlenie/"

CODE_LENGTH = 6
MAX_ATTEMPTS = 5


def conf(name: str, default):
    return getattr(settings, name, default)


def _hash(code: str) -> str:
    """The code is kept in the session only as a hash, salted with SECRET_KEY."""
    return sha256(f"{settings.SECRET_KEY}:{code}".encode("utf-8")).hexdigest()


def enabled() -> bool:
    telegram = getattr(settings, "TELEGRAM", {})
    return bool(
        conf("ADMIN_TELEGRAM_GATE", False)
        and telegram.get("TOKEN") and telegram.get("CHAT_ID")
    )


def is_passed(request) -> bool:
    until = request.session.get(PASSED_KEY)
    if not until:
        return False
    return timezone.now().timestamp() < float(until)


def mark_passed(request) -> None:
    hours = conf("ADMIN_GATE_HOURS", 12)
    until = timezone.now().timestamp() + hours * 3600
    request.session[PASSED_KEY] = until
    request.session.pop(SESSION_KEY, None)


# --- code -----------------------------------------------------------------
def issue_code(request) -> tuple[bool, str]:
    """Creates a code and sends it to the owner. Returns (success, message)."""
    from orders.notify import send_raw

    now = timezone.now().timestamp()
    state = request.session.get(SESSION_KEY) or {}
    pause = conf("ADMIN_GATE_RESEND_SECONDS", 45)
    if state.get("sent_at") and now - float(state["sent_at"]) < pause:
        left = int(pause - (now - float(state["sent_at"])))
        return False, f"Код уже отправлен. Новый можно запросить через {left} с."

    code = "".join(secrets.choice("0123456789") for _ in range(CODE_LENGTH))
    request.session[SESSION_KEY] = {
        "hash": _hash(code),
        "expires": now + conf("ADMIN_GATE_CODE_SECONDS", 300),
        "attempts": 0,
        "sent_at": now,
    }
    request.session.modified = True

    minutes = conf("ADMIN_GATE_CODE_SECONDS", 300) // 60
    # the code itself is never logged — more people read logs than
    # you would think
    send_raw(
        f"🔐 <b>Вход в админку {settings.SHOP['NAME']}</b>\n\n"
        f"Код: <code>{code}</code>\n\n"
        f"Действует {minutes} мин. Если это не вы — просто не вводите его "
        "и смените пароль администратора."
    )
    logger.info("Admin gate: code sent")
    return True, "Код отправлен в Telegram."


def check_code(request, entered: str) -> tuple[bool, str]:
    state = request.session.get(SESSION_KEY) or {}
    if not state:
        return False, "Сначала запросите код."

    now = timezone.now().timestamp()
    if now > float(state.get("expires", 0)):
        request.session.pop(SESSION_KEY, None)
        return False, "Код просрочен — запросите новый."

    entered = "".join(c for c in (entered or "") if c.isdigit())
    if not entered:
        return False, "Введите код из шести цифр."

    # constant-time comparison: otherwise the response delay leaks
    # the code bit by bit
    if hmac.compare_digest(state.get("hash", ""), _hash(entered)):
        mark_passed(request)
        logger.info("Admin gate: code accepted")
        return True, ""

    attempts = int(state.get("attempts", 0)) + 1
    if attempts >= MAX_ATTEMPTS:
        request.session.pop(SESSION_KEY, None)
        logger.warning("Admin gate: code cancelled after %s attempts", attempts)
        return False, "Слишком много попыток. Запросите новый код."

    state["attempts"] = attempts
    request.session[SESSION_KEY] = state
    request.session.modified = True
    return False, f"Код не подошёл. Осталось попыток: {MAX_ATTEMPTS - attempts}."


# --- gate page ------------------------------------------------------------
def gate_view(request):
    """The "send me the code" page. Works without JavaScript."""
    if not enabled() or is_passed(request):
        return HttpResponseRedirect(request.session.pop(NEXT_KEY, None)
                                    or settings.ADMIN_PATH + "/")

    note = ""
    error = ""
    waiting = bool(request.session.get(SESSION_KEY))

    if request.method == "POST":
        if "send" in request.POST:
            ok, message = issue_code(request)
            note, error = (message, "") if ok else ("", message)
            waiting = bool(request.session.get(SESSION_KEY))
        else:
            ok, message = check_code(request, request.POST.get("code", ""))
            if ok:
                target = request.session.pop(NEXT_KEY, None) or settings.ADMIN_PATH + "/"
                return HttpResponseRedirect(target)
            error = message
            waiting = bool(request.session.get(SESSION_KEY))

    return render(request, "admin/gate.html", {
        "waiting": waiting,
        "note": note,
        "error": error,
        "minutes": conf("ADMIN_GATE_CODE_SECONDS", 300) // 60,
    })


# --- middleware -----------------------------------------------------------
class AdminGateMiddleware(MiddlewareMixin):
    """Blocks the admin until the Telegram code is entered.

    Placed AFTER SessionMiddleware: without a session there is nowhere to
    keep the "code passed" mark.
    """

    def process_request(self, request):
        if not enabled():
            return None

        path = request.path
        # Cheap path check first, reverse() only afterwards: no need for
        # it on every storefront page.
        if not path.startswith(settings.ADMIN_PATH) and path != GATE_PATH:
            return None

        try:
            gate_url = reverse("admin-gate")
        except NoReverseMatch:
            # The gate URL is missing from the URLConf — usually means new
            # code reached the server but config/urls.py is still old.
            # Silently let through to the admin: it has its own login form,
            # which is better than taking the whole site down.
            logger.error("Admin gate: admin-gate URL not found, gate skipped")
            return None

        if path == gate_url:
            return None

        # The server itself gets in without a code: that is the SSH tunnel
        # entrance, the fallback for when Telegram is down.
        #
        # On the local copy this prevents testing the gate — all requests
        # there are local. Set ADMIN_GATE_ALLOW_LOCAL=0 in the copy's .env
        # and the code is asked even on 127.0.0.1.
        if conf("ADMIN_GATE_ALLOW_LOCAL", True):
            address = request.META.get("HTTP_CF_CONNECTING_IP") or \
                request.META.get("REMOTE_ADDR", "")
            if address in ("127.0.0.1", "::1", "localhost"):
                return None

        if is_passed(request):
            return None

        request.session[NEXT_KEY] = request.get_full_path()
        return HttpResponseRedirect(gate_url)
