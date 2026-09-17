"""Telegram connectivity check — without placing a real order.

    python manage.py telegram_test            — a short test message
    python manage.py telegram_test --last     — the text of the latest order

The command is synchronous and deliberately noisy: if something is set up
wrong, you see Telegram's answer right in the window, not in the server log.
"""

from django.conf import settings
from django.core.management.base import BaseCommand

from orders import notify
from orders.models import Order


class Command(BaseCommand):
    help = "Sends a test message to Telegram"

    def add_arguments(self, parser):
        parser.add_argument(
            "--last", action="store_true",
            help="Take the latest order and send it as the florist would receive it.",
        )

    def handle(self, *args, **options):
        conf = getattr(settings, "TELEGRAM", {})
        token, chat = conf.get("TOKEN", ""), conf.get("CHAT_ID", "")

        self.stdout.write(f"Token:  {'set (' + str(len(token)) + ' characters)' if token else 'EMPTY'}")
        self.stdout.write(f"Chat:   {chat or 'EMPTY'}")
        self.stdout.write(f"URL:    {getattr(settings, 'SITE_URL', '') or 'not set'}")

        if not notify.enabled():
            self.stdout.write(self.style.ERROR(
                "\nTELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing from .env — "
                "notifications are currently off."
            ))
            return

        if options["last"]:
            order = Order.objects.order_by("-pk").first()
            if order is None:
                self.stdout.write(self.style.WARNING(
                    "No orders yet — sending the plain test message."
                ))
                text = "✅ Проверка связи. Уведомления о заказах настроены."
            else:
                text = notify.build_message(order)
        else:
            text = "✅ Проверка связи. Уведомления о заказах настроены."

        self.stdout.write("\nSending...")
        notify.send_raw(text)
        self.stdout.write(self.style.SUCCESS(
            "Sent. If the message did not arrive — see the error line above: "
            "most often it is a wrong token or a bot you have not yet sent /start to."
        ))
