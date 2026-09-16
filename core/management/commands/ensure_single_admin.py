"""Оставляет в базе ровно одну учётную запись администратора.

Лишние не удаляются, а отключаются: войти ими нельзя, но история
изменений в админке остаётся целой. Запускается из ЗАПУСТИТЬ.bat.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()


class Command(BaseCommand):
    help = "Оставляет одного активного администратора, остальных отключает"

    def add_arguments(self, parser):
        parser.add_argument(
            "--keep", dest="keep", default=None,
            help="Имя учётной записи, которую оставить. "
                 "По умолчанию — созданная последней.",
        )

    def handle(self, *args, **options):
        admins = list(
            User.objects.filter(is_superuser=True, is_active=True).order_by("-date_joined")
        )
        if not admins:
            self.stdout.write("Администраторов нет — создайте его через СОЗДАТЬ-АДМИНА.bat.")
            return
        if len(admins) == 1:
            self.stdout.write(f"Администратор один: {admins[0].username}.")
            return

        keep_name = options["keep"]
        keep = next((u for u in admins if u.username == keep_name), None) if keep_name else None
        keep = keep or admins[0]

        for user in admins:
            if user.pk == keep.pk:
                continue
            user.is_active = False
            user.is_staff = False
            user.is_superuser = False
            user.save(update_fields=["is_active", "is_staff", "is_superuser"])
            self.stdout.write(f"  {user.username} — отключён")

        self.stdout.write(self.style.SUCCESS(f"Остался один администратор: {keep.username}."))
