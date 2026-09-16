"""Вход в админку по одноразовому коду из Telegram.

Задача. Админка снова открыта из интернета — так ей удобно пользоваться
с любого компьютера. Но пароль в этом случае остаётся единственной
преградой, а его подбирают роботы круглосуточно.

Решение. Перед формой входа Django стоит наш шлюз: пока в сессии нет
отметки о пройденном коде, вместо админки показывается страница
«Пришлите код». Код уходит в Telegram владельцу — тому единственному
человеку, чей id записан в .env. Не имея доступа к этому Telegram,
войти нельзя, даже зная логин и пароль.

Что важно в реализации:

* Код хранится хешем, не текстом. Сессия лежит в базе, и утёкшая база
  не должна отдавать действующие коды.
* Живёт пять минут и сгорает после первой же удачной проверки.
* Пять неверных попыток — код аннулируется целиком, нужен новый.
  Иначе шестизначное число подбирается перебором за вечер.
* Просить новый код можно не чаще раза в 45 секунд: иначе шлюз
  превращается в кнопку «завалить владельца сообщениями».
* Запросы с самого сервера (127.0.0.1) шлюз не трогает. Это запасной
  вход через SSH-туннель на случай, если Telegram недоступен.

Автор кода: ISHOD, 2026.
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

SESSION_KEY = "admin_gate"          # что здесь: хеш кода, срок, попытки
PASSED_KEY = "admin_gate_passed"    # до какого времени пускаем без кода
NEXT_KEY = "admin_gate_next"        # куда вернуть после проверки

# адрес страницы шлюза — нужен, чтобы не звать reverse на каждый запрос
GATE_PATH = "/vhod-v-upravlenie/"

CODE_LENGTH = 6
MAX_ATTEMPTS = 5


def conf(name: str, default):
    return getattr(settings, name, default)


def _hash(code: str) -> str:
    """Код в сессии держим только в виде хеша — с солью из SECRET_KEY."""
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


# --- код ------------------------------------------------------------------
def issue_code(request) -> tuple[bool, str]:
    """Создаёт код и отправляет его владельцу. Возвращает (успех, что сказать)."""
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
    # сам код в журнал не пишем никогда — журнал читают больше людей,
    # чем кажется
    send_raw(
        f"🔐 <b>Вход в админку {settings.SHOP['NAME']}</b>\n\n"
        f"Код: <code>{code}</code>\n\n"
        f"Действует {minutes} мин. Если это не вы — просто не вводите его "
        "и смените пароль администратора."
    )
    logger.info("Шлюз админки: код отправлен")
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

    # сравниваем в постоянное время: иначе по задержке ответа можно
    # понемногу угадывать код
    if hmac.compare_digest(state.get("hash", ""), _hash(entered)):
        mark_passed(request)
        logger.info("Шлюз админки: код принят")
        return True, ""

    attempts = int(state.get("attempts", 0)) + 1
    if attempts >= MAX_ATTEMPTS:
        request.session.pop(SESSION_KEY, None)
        logger.warning("Шлюз админки: код аннулирован после %s попыток", attempts)
        return False, "Слишком много попыток. Запросите новый код."

    state["attempts"] = attempts
    request.session[SESSION_KEY] = state
    request.session.modified = True
    return False, f"Код не подошёл. Осталось попыток: {MAX_ATTEMPTS - attempts}."


# --- страница шлюза -------------------------------------------------------
def gate_view(request):
    """Страница «пришлите код». Работает и без JavaScript."""
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
    """Не пускает в админку, пока не введён код из Telegram.

    Стоит ПОСЛЕ SessionMiddleware: без сессии отметку о пройденном коде
    хранить негде.
    """

    def process_request(self, request):
        if not enabled():
            return None

        path = request.path
        # Сначала дешёвая проверка пути, и только потом reverse: он
        # незачем на каждой странице витрины.
        if not path.startswith(settings.ADMIN_PATH) and path != GATE_PATH:
            return None

        try:
            gate_url = reverse("admin-gate")
        except NoReverseMatch:
            # Адреса шлюза нет в URLConf — обычно это значит, что на
            # сервер доехал новый код, но старый config/urls.py.
            # Молча пропускаем в админку: там своя форма входа, и это
            # лучше, чем уронить сайт целиком.
            logger.error("Шлюз админки: адрес admin-gate не найден, шлюз пропущен")
            return None

        if path == gate_url:
            return None

        # С самого сервера пускаем без кода: это вход через SSH-туннель,
        # запасной путь на случай, если Telegram лежит.
        #
        # На копии у себя это мешает проверить шлюз — там все запросы
        # локальные. Поставьте ADMIN_GATE_ALLOW_LOCAL=0 в .env копии,
        # и код будет спрашиваться даже на 127.0.0.1.
        if conf("ADMIN_GATE_ALLOW_LOCAL", True):
            address = request.META.get("HTTP_CF_CONNECTING_IP") or \
                request.META.get("REMOTE_ADDR", "")
            if address in ("127.0.0.1", "::1", "localhost"):
                return None

        if is_passed(request):
            return None

        request.session[NEXT_KEY] = request.get_full_path()
        return HttpResponseRedirect(gate_url)
