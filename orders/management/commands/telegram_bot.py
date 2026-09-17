"""Info bot: orders and customers right in Telegram.

Why. The admin is closed from the outside and opens only through an SSH
tunnel — right for management, but inconvenient when you just want to
glance from the phone how many orders came in. The bot covers exactly
that need: read only, changes nothing.

Who it answers. Strictly one person — the one whose id is in .env
(TELEGRAM_CHAT_ID). Any message from another id is silently ignored and
logged: if someone found the bot and writes to it, it is visible.

How it works. Long polling: updates are requested with a timeout,
Telegram holds the connection and answers as soon as a message arrives.
No webhook — so no external address or port is needed.

The id of the last processed update is stored in a file next to the
database. Without it the bot would answer old commands again after a restart.

Run:  manage.py telegram_bot
On the server it runs as the kvitka-bot service (see deploy/kvitka-bot.service).
Code by ISHOD, 2026.
"""

from __future__ import annotations

import html
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Sum
from django.utils import timezone

from orders.models import Order

logger = logging.getLogger("kvitka")

API = "https://api.telegram.org/bot{token}/{method}"
POLL_TIMEOUT = 25          # how long Telegram holds the connection
HTTP_TIMEOUT = POLL_TIMEOUT + 10
LIMIT = 3900               # Telegram's ceiling is 4096, keep a margin
PAGE = 10                  # how many records are shown at once

HELP = f"""<b>{settings.SHOP["NAME"]} — справочная</b>

/zakazy — последние заказы
/zakaz 12 — что в заказе №12
/novye — только новые, ещё не подтверждённые
/segodnya — что везём сегодня
/pokupateli — кто завёл кабинет
/svodka — цифры за сутки и неделю
/ostatki — какие букеты заканчиваются

Бот только показывает. Менять статусы и товары — в админке."""


def esc(value) -> str:
    return html.escape(str(value or ""))


def money(value) -> str:
    return f"{value or 0:,.0f}".replace(",", " ") + " ₴"


class Command(BaseCommand):
    help = "Telegram bot: shows orders and customers to the owner"

    def add_arguments(self, parser):
        parser.add_argument(
            "--once", action="store_true",
            help="Process pending updates and exit. For testing.",
        )

    # --- talking to Telegram ----------------------------------------------
    def api(self, method: str, **params):
        url = API.format(token=self.token, method=method)
        data = urllib.parse.urlencode(params).encode("utf-8")
        with urllib.request.urlopen(url, data=data, timeout=HTTP_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def send(self, text: str) -> None:
        if len(text) > LIMIT:
            text = text[:LIMIT] + "\n…"
        try:
            self.api("sendMessage", chat_id=self.chat_id, text=text,
                     parse_mode="HTML", disable_web_page_preview="true")
        except Exception:
            logger.exception("Bot: could not send the reply")

    # --- startup ----------------------------------------------------------
    def handle(self, *args, **options):
        conf = getattr(settings, "TELEGRAM", {})
        self.token = conf.get("TOKEN") or ""
        self.chat_id = str(conf.get("CHAT_ID") or "")
        if not self.token or not self.chat_id:
            raise CommandError(
                "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is not set in .env — "
                "nothing for the bot to work with."
            )

        self.offset_file = Path(settings.BASE_DIR) / "var" / "bot-offset"
        self.offset_file.parent.mkdir(parents=True, exist_ok=True)
        offset = self.read_offset()

        self.stdout.write("Bot started. Answers the owner only.")
        while True:
            try:
                answer = self.api("getUpdates", offset=offset,
                                  timeout=POLL_TIMEOUT)
            except urllib.error.HTTPError as error:
                # Telegram answers with a code — the cause is clear from it,
                # and "network unavailable" would be a lie here
                if error.code == 401:
                    raise CommandError(
                        "Telegram rejected the token (401). Check "
                        "TELEGRAM_BOT_TOKEN in .env on the server."
                    )
                if error.code == 409:
                    # the same bot is polled from somewhere else: usually it
                    # was left running on the owner's computer
                    logger.warning(
                        "Bot: the same bot is already running elsewhere (409). "
                        "Keep a single instance."
                    )
                    time.sleep(15)
                    continue
                logger.warning("Bot: Telegram answered %s", error.code)
                time.sleep(10)
                continue
            except (urllib.error.URLError, TimeoutError, OSError) as error:
                # the network blinked — wait and retry, that is normal
                logger.warning("Bot: network unavailable (%s)", error)
                time.sleep(5)
                continue
            except Exception:
                logger.exception("Bot: unexpected error while polling")
                time.sleep(10)
                continue

            for update in answer.get("result", []):
                offset = update["update_id"] + 1
                try:
                    self.handle_update(update)
                except Exception:
                    logger.exception("Bot: error while handling a message")
            self.write_offset(offset)

            if options["once"]:
                self.stdout.write("Single run finished.")
                return

    def read_offset(self) -> int:
        try:
            return int(self.offset_file.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return 0

    def write_offset(self, offset: int) -> None:
        try:
            self.offset_file.write_text(str(offset), encoding="utf-8")
        except OSError:
            logger.warning("Bot: could not save the update offset")

    # --- parsing a message ------------------------------------------------
    def handle_update(self, update: dict) -> None:
        message = update.get("message") or update.get("edited_message") or {}
        text = (message.get("text") or "").strip()
        sender = str(message.get("chat", {}).get("id") or "")
        if not text:
            return
        if sender != self.chat_id:
            # a stranger: no reply at all, so the bot does not confirm it is alive
            logger.warning("Bot: message from foreign id %s — skipped", sender)
            return

        command, _, argument = text.partition(" ")
        command = command.lstrip("/").split("@")[0].lower()
        handlers = {
            "start": self.cmd_help, "help": self.cmd_help,
            "zakazy": self.cmd_orders, "заказы": self.cmd_orders,
            "zakaz": self.cmd_order, "заказ": self.cmd_order,
            "novye": self.cmd_new, "новые": self.cmd_new,
            "segodnya": self.cmd_today, "сегодня": self.cmd_today,
            "pokupateli": self.cmd_customers, "покупатели": self.cmd_customers,
            "svodka": self.cmd_summary, "сводка": self.cmd_summary,
            "ostatki": self.cmd_stock, "остатки": self.cmd_stock,
        }
        handler = handlers.get(command)
        if handler is None:
            self.send("Не знаю такой команды.\n\n" + HELP)
            return
        self.send(handler(argument.strip()))

    # --- the commands themselves ------------------------------------------
    def cmd_help(self, argument: str) -> str:
        return HELP

    def cmd_orders(self, argument: str) -> str:
        orders = Order.objects.all()[:PAGE]
        if not orders:
            return "Заказов пока нет."
        lines = [f"<b>Последние заказы</b> (всего {Order.objects.count()})", ""]
        for order in orders:
            lines.append(
                f"{esc(order.number)} · {order.created_at:%d.%m %H:%M} · "
                f"{esc(order.get_status_display())}\n"
                f"   {esc(order.name)}, {esc(order.phone)}\n"
                f"   {order.total_quantity} шт · {money(order.total_amount)}"
            )
        lines.append("\nПодробнее: /zakaz номер")
        return "\n".join(lines)

    def cmd_new(self, argument: str) -> str:
        orders = Order.objects.new()[:PAGE]
        if not orders:
            return "Новых заказов нет — все разобраны."
        lines = [f"<b>Новые заказы: {Order.objects.new().count()}</b>", ""]
        for order in orders:
            lines.append(
                f"{esc(order.number)} · {order.created_at:%d.%m %H:%M}\n"
                f"   {esc(order.name)}, {esc(order.phone)}\n"
                f"   {order.total_quantity} шт · {money(order.total_amount)}"
            )
        return "\n".join(lines)

    def cmd_order(self, argument: str) -> str:
        digits = "".join(c for c in argument if c.isdigit())
        if not digits:
            return "Напишите номер: <code>/zakaz 12</code>"
        order = Order.objects.filter(pk=int(digits)).first()
        if order is None:
            return f"Заказа №{digits} нет."

        lines = [
            f"<b>Заказ {esc(order.number)}</b>",
            f"{order.created_at:%d.%m.%Y %H:%M} · {esc(order.get_status_display())}",
            "",
            f"<b>{esc(order.name)}</b>",
            f"Телефон: {esc(order.phone)}",
        ]
        if order.email:
            lines.append(f"Почта: {esc(order.email)}")
        lines.append(self.delivery_lines(order))
        if order.user_id:
            lines.append("Есть кабинет на сайте")
        if order.comment:
            lines.append(f"\nКомментарий: {esc(order.comment)}")

        lines.append("\n<b>Позиции</b>")
        for line in order.lines.all():
            lines.append(
                f"{esc(line.article)} × {line.quantity} шт — {money(line.amount)}"
            )
        lines.append(f"Доставка: {money(order.delivery_cost)}")
        lines.append(f"<b>Итого: {money(order.total_amount)}</b>")
        return "\n".join(lines)

    @staticmethod
    def delivery_lines(order) -> str:
        """Where, when and to whom to deliver — as one block."""
        rows = []
        if order.is_pickup:
            rows.append("Самовывоз")
        else:
            rows.append(f"Адрес: {esc(order.address)}")
        when = " ".join(filter(None, [
            f"{order.delivery_date:%d.%m.%Y}" if order.delivery_date else "",
            order.get_delivery_time_display() if order.delivery_time else "",
        ]))
        if when:
            rows.append(f"Когда: {when}")
        if order.recipient_name or order.recipient_phone:
            rows.append(f"Получатель: {esc(order.recipient_name)} {esc(order.recipient_phone)}".rstrip())
        if order.card_text:
            rows.append(f"Открытка: «{esc(order.card_text)}»")
        rows.append(f"Оплата: {esc(order.get_payment_display())}")
        return "\n".join(rows)

    def cmd_today(self, argument: str) -> str:
        today = timezone.localdate()
        orders = Order.objects.open().filter(delivery_date=today).order_by("delivery_time")
        if not orders:
            return "На сегодня доставок нет."
        lines = [f"<b>Сегодня, {today:%d.%m}: {orders.count()}</b>", ""]
        for order in orders[:PAGE * 2]:
            slot = order.get_delivery_time_display() if order.delivery_time else "любое время"
            where = "самовывоз" if order.is_pickup else esc(order.address)
            lines.append(
                f"{slot} · {esc(order.number)} · {esc(order.get_status_display())}\n"
                f"   {where}\n   {esc(order.name)}, {esc(order.phone)}"
            )
        return "\n".join(lines)

    def cmd_customers(self, argument: str) -> str:
        User = get_user_model()
        users = (User.objects.filter(is_staff=False)
                 .select_related("profile").order_by("-date_joined")[:PAGE])
        total = User.objects.filter(is_staff=False).count()
        if not users:
            return "Кабинетов пока никто не заводил."
        lines = [f"<b>Покупатели с кабинетом: {total}</b>", ""]
        for user in users:
            profile = getattr(user, "profile", None)
            row = (f"{esc(user.first_name or user.email)} · "
                   f"{user.date_joined:%d.%m.%Y}")
            if profile and profile.phone:
                row += f"\n   {esc(profile.phone)}"
            orders = Order.objects.filter(user=user).count()
            if orders:
                row += f"\n   заказов: {orders}"
            lines.append(row)
        return "\n".join(lines)

    def cmd_summary(self, argument: str) -> str:
        from catalog.models import Product

        now = timezone.now()
        User = get_user_model()

        def slice_stats(since):
            rows = Order.objects.filter(created_at__gte=since).aggregate(
                count=Count("id"), amount=Sum("total_amount"))
            return rows["count"] or 0, rows["amount"] or 0

        day_count, day_amount = slice_stats(now - timedelta(days=1))
        week_count, week_amount = slice_stats(now - timedelta(days=7))

        return "\n".join([
            "<b>Сводка</b>",
            "",
            f"<b>Сутки:</b> {day_count} заказов на {money(day_amount)}",
            f"<b>Неделя:</b> {week_count} заказов на {money(week_amount)}",
            "",
            f"Новых, не подтверждённых: {Order.objects.new().count()}",
            f"Заказов всего: {Order.objects.count()}",
            "",
            f"Кабинетов: {User.objects.filter(is_staff=False).count()}",
            f"Товаров на сайте: {Product.objects.published().count()}",
            f"Без остатка: {Product.objects.published().filter(stock_quantity=0).count()}",
        ])

    def cmd_stock(self, argument: str) -> str:
        from catalog.models import Product

        # "running low" — fewer than five bouquets: the catalog tile uses
        # the same threshold (Product.stock_state)
        low = list(Product.objects.published().filter(stock_quantity__lt=5)
                   .order_by("stock_quantity")[:40])
        if not low:
            return "Всё в порядке: букетов на исходе нет."
        lines = [f"<b>Заканчивается: {len(low)}</b>", ""]
        for product in low[:PAGE]:
            lines.append(
                f"{esc(product.article)} — {product.stock_quantity} шт"
                f"\n   {esc(product.name)}"
            )
        return "\n".join(lines)
