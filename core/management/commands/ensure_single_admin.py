"""Keeps exactly one administrator account in the database.

Extra ones are not deleted but deactivated: they cannot log in, but the
admin change history stays intact.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()


class Command(BaseCommand):
    help = "Keeps one active administrator, deactivates the rest"

    def add_arguments(self, parser):
        parser.add_argument(
            "--keep", dest="keep", default=None,
            help="Username of the account to keep. Default — the one created last.",
        )

    def handle(self, *args, **options):
        admins = list(
            User.objects.filter(is_superuser=True, is_active=True).order_by("-date_joined")
        )
        if not admins:
            self.stdout.write("No administrators — create one with tools\\create-admin.bat.")
            return
        if len(admins) == 1:
            self.stdout.write(f"Single administrator: {admins[0].username}.")
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
            self.stdout.write(f"  {user.username} — deactivated")

        self.stdout.write(self.style.SUCCESS(f"One administrator left: {keep.username}."))
