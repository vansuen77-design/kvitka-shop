"""New-order notifications: to the florist in Telegram, to the customer by e-mail.

Why this way:

* Sending happens in a background thread. The customer must not wait
  while we reach Telegram or the mail server, and must not see an error
  if they are down: the order is already saved, the notification is
  secondary.
* No error from here reaches the customer. Everything that went wrong is
  written to the server log (journalctl -u kvitka).
* The customer e-mail is built in the language they ordered in
  (Order.language): in the background thread the request language is
  no longer active.
* Standard library only, no requests: one dependency fewer.
"""

from __future__ import annotations

import html
import json
import logging
import threading
import urllib.error
import urllib.request

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import translation

logger = logging.getLogger("kvitka")

API = "https://api.telegram.org/bot{token}/sendMessage"
TIMEOUT = 10
MAX_LINES = 25          # more than that does not fit a message readably
LIMIT = 4000            # Telegram caps messages at 4096 characters


def enabled() -> bool:
    conf = getattr(settings, "TELEGRAM", {})
    return bool(conf.get("TOKEN") and conf.get("CHAT_ID"))


def notify_new_order(order, background: bool = True) -> None:
    """Entry point. Called right after the order is saved.

    ``background=False`` is for tests and commands: send here and now.
    """
    if enabled():
        try:
            text = build_message(order)
        except Exception:
            logger.exception("Telegram: could not build the text for order %s", order.pk)
        else:
            _run(_send, text, background=background)
    if order.email:
        _run(_email_customer, order.pk, order.language, background=background)


def _run(target, *args, background: bool) -> None:
    if not background:
        target(*args)
        return
    thread = threading.Thread(target=target, args=args, daemon=True)
    thread.start()


# --- text ----------------------------------------------------------------
def _esc(value) -> str:
    return html.escape(str(value or ""))


def _money(value) -> str:
    return f"{value:,.0f}".replace(",", " ")


def build_message(order) -> str:
    lines = list(order.lines.all())

    head = [
        f"💐 <b>Заказ №{order.pk}</b>",
        _esc(order.created_at.strftime("%d.%m.%Y %H:%M")),
        "",
        f"<b>{_esc(order.name)}</b>",
        f"📞 {_esc(order.phone)}",
    ]
    if order.email:
        head.append(f"✉️ {_esc(order.email)}")
    head.append("")

    # --- delivery -------------------------------------------------------
    if order.is_pickup:
        head.append("🏬 Самовывоз")
    else:
        head.append(f"🚚 Курьером: {_esc(order.address)}")
    when = []
    if order.delivery_date:
        when.append(order.delivery_date.strftime("%d.%m.%Y"))
    if order.delivery_time:
        when.append(order.get_delivery_time_display())
    if when:
        head.append("🕒 " + " ".join(when))
    if order.recipient_name or order.recipient_phone:
        head.append(
            f"🎁 Получатель: {_esc(order.recipient_name)} {_esc(order.recipient_phone)}".rstrip()
        )
    if order.card_text:
        head.append(f"💌 Открытка: «{_esc(order.card_text)}»")
    head.append(f"💳 {_esc(order.get_payment_display())}")
    head.append("")

    body = [f"<b>Позиции ({len(lines)})</b>"]
    for line in lines[:MAX_LINES]:
        body.append(
            f"<code>{_esc(line.article)}</code> — {_esc(line.product_name)}\n"
            f"    {line.quantity} шт × {_money(line.unit_price)} ₴ "
            f"= <b>{_money(line.amount)} ₴</b>"
        )
    if len(lines) > MAX_LINES:
        body.append(f"… и ещё {len(lines) - MAX_LINES} позиций — смотрите в админке")
    body.append("")
    delivery = "бесплатно" if order.delivery_cost == 0 else f"{_money(order.delivery_cost)} ₴"
    body.append(f"Товары: {_money(order.goods_amount)} ₴ · доставка: {delivery}")
    body.append(f"<b>Итого: {_money(order.total_amount)} ₴</b>")

    tail = []
    if order.comment:
        tail += ["", f"💬 {_esc(order.comment)}"]
    url = getattr(settings, "SITE_URL", "")
    if url:
        tail += ["", f"{url}{settings.ADMIN_PATH}/orders/order/{order.pk}/change/"]

    text = "\n".join(head + body + tail)
    if len(text) > LIMIT:
        text = text[:LIMIT] + "\n…"
    return text


# --- sending -------------------------------------------------------------
def _send(text: str) -> None:
    conf = settings.TELEGRAM
    payload = json.dumps({
        "chat_id": conf["CHAT_ID"],
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }).encode("utf-8")

    request = urllib.request.Request(
        API.format(token=conf["TOKEN"]),
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            answer = json.loads(response.read().decode("utf-8"))
        if not answer.get("ok"):
            logger.error("Telegram refused: %s", answer)
    except urllib.error.HTTPError as error:
        # the Telegram response body explains the cause better than the code
        detail = error.read().decode("utf-8", "replace")[:300]
        logger.error("Telegram %s: %s", error.code, detail)
    except Exception:
        logger.exception("Telegram: sending failed")


def send_raw(text: str) -> None:
    """Synchronous send — needed by the telegram_test check command."""
    _send(text)


# --- customer e-mail -----------------------------------------------------
def _email_customer(order_id: int, language: str) -> None:
    """"Order accepted" to the customer's e-mail, in their language.

    The order is re-read from the database: the thread outlives the
    request, and the object from the view may have no lines by then.
    """
    from orders.context_processors import shop_settings
    from orders.models import Order

    try:
        order = Order.objects.prefetch_related("lines").get(pk=order_id)
        if not order.email:
            return
        with translation.override(language or settings.LANGUAGE_CODE):
            context = {"order": order, "shop": shop_settings(),
                       "SITE_URL": settings.SITE_URL}
            subject = render_to_string("orders/email_subject.txt", context).strip()
            body = render_to_string("orders/email_body.txt", context)
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [order.email],
                  fail_silently=False)
    except Exception:
        logger.exception("Order %s: customer e-mail was not sent", order_id)
