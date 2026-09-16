"""Проверка связи с Telegram — без оформления настоящего заказа.

    python manage.py telegram_test            — короткое тестовое сообщение
    python manage.py telegram_test --last     — текст по последнему заказу

Команда синхронная и намеренно шумная: если что-то настроено неверно,
вы увидите ответ Telegram прямо в окне, а не в журнале сервера.
"""

from django.conf import settings
from django.core.management.base import BaseCommand

from orders import notify
from orders.models import Order


class Command(BaseCommand):
    help = "Отправляет тестовое сообщение в Telegram"

    def add_arguments(self, parser):
        parser.add_argument(
            "--last", action="store_true",
            help="Взять последний заказ и отправить его так, как ушёл бы флористу.",
        )

    def handle(self, *args, **options):
        conf = getattr(settings, "TELEGRAM", {})
        token, chat = conf.get("TOKEN", ""), conf.get("CHAT_ID", "")

        self.stdout.write(f"Токен:  {'задан (' + str(len(token)) + ' символов)' if token else 'ПУСТО'}")
        self.stdout.write(f"Чат:    {chat or 'ПУСТО'}")
        self.stdout.write(f"Адрес:  {getattr(settings, 'SITE_URL', '') or 'не задан'}")

        if not notify.enabled():
            self.stdout.write(self.style.ERROR(
                "\nНе хватает TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID в файле .env — "
                "уведомления сейчас выключены."
            ))
            return

        if options["last"]:
            order = Order.objects.order_by("-pk").first()
            if order is None:
                self.stdout.write(self.style.WARNING(
                    "Заявок ещё нет — отправляю обычное тестовое сообщение."
                ))
                text = "✅ Проверка связи. Уведомления о заказах настроены."
            else:
                text = notify.build_message(order)
        else:
            text = "✅ Проверка связи. Уведомления о заказах настроены."

        self.stdout.write("\nОтправляю...")
        notify.send_raw(text)
        self.stdout.write(self.style.SUCCESS(
            "Отправлено. Если сообщение не пришло — смотрите строку с ошибкой выше: "
            "чаще всего это неверный токен или бот, которому вы ещё не написали /start."
        ))
