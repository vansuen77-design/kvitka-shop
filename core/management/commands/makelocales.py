"""Refreshes the string lists in locale/uk and locale/ru — without GNU gettext.

    python manage.py makelocales           # collect strings, add new ones to .po
    python manage.py makelocales --check   # change nothing, only verify

Translation workflow:
    makelocales → fill in empty msgstr in locale/uk → compilelocales.
The Russian catalog fills itself: translation equals the source.

--check fails if the code has strings missing from .po, or some string has
an empty Ukrainian translation. This way the pre-delivery check catches
untranslated labels before a customer sees them.
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core import i18n_tools


class Command(BaseCommand):
    help = "Collects translation strings from templates and code into .po"

    def add_arguments(self, parser):
        parser.add_argument(
            "--check", action="store_true",
            help="Do not change files: only report new and untranslated strings",
        )

    def handle(self, *args, **options):
        root = Path(settings.BASE_DIR)
        locale_dir = Path(settings.LOCALE_PATHS[0])

        if options["check"]:
            problems = i18n_tools.check(root, locale_dir)
            for text in problems["missing"]:
                self.stdout.write(self.style.ERROR(f"  missing from .po: {text!r}"))
            for text in problems["untranslated"]:
                self.stdout.write(self.style.WARNING(f"  untranslated: {text!r}"))
            total = len(problems["missing"]) + len(problems["untranslated"])
            if total:
                raise CommandError(
                    f"Translations incomplete: {len(problems['missing'])} new strings, "
                    f"{len(problems['untranslated'])} untranslated. "
                    "Run makelocales and fill in the empty msgstr."
                )
            self.stdout.write(self.style.SUCCESS("Translations complete: every string is in .po and translated."))
            return

        report = i18n_tools.sync(root, locale_dir, settings.SHOP["NAME"])
        for language, info in report.items():
            self.stdout.write(
                f"  {language}: total {info['total']}, added {len(info['added'])}, "
                f"removed {len(info['removed'])}"
            )
        untranslated = report["uk"]["untranslated"]
        if untranslated:
            self.stdout.write(self.style.WARNING(
                f"Without Ukrainian translation: {len(untranslated)} strings — "
                "fill in msgstr in locale/uk/LC_MESSAGES/django.po, then run compilelocales."
            ))
            for text in untranslated[:60]:
                self.stdout.write(f"    {text!r}")
            if len(untranslated) > 60:
                self.stdout.write(f"    … and {len(untranslated) - 60} more")
        else:
            self.stdout.write(self.style.SUCCESS("All strings translated."))
