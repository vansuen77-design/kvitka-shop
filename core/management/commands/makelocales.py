"""Обновляет списки строк в locale/uk и locale/ru — без GNU gettext.

    python manage.py makelocales           # собрать строки, дописать новые в .po
    python manage.py makelocales --check   # ничего не менять, только проверить

Порядок работы с переводами (инвариант 11):
    makelocales → перевести пустые msgstr в locale/uk → compilelocales.
Русский каталог заполняется сам: перевод равен оригиналу.

--check завершается с ошибкой, если в коде появились строки, которых
нет в .po, или у какой-то строки пустой украинский перевод. Так
проверка перед сдачей ловит непереведённые надписи до того, как их
увидит покупатель.
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core import i18n_tools


class Command(BaseCommand):
    help = "Собирает строки перевода из шаблонов и кода в .po"

    def add_arguments(self, parser):
        parser.add_argument(
            "--check", action="store_true",
            help="Не менять файлы: только сообщить о новых и непереведённых строках",
        )

    def handle(self, *args, **options):
        root = Path(settings.BASE_DIR)
        locale_dir = Path(settings.LOCALE_PATHS[0])

        if options["check"]:
            problems = i18n_tools.check(root, locale_dir)
            for text in problems["missing"]:
                self.stdout.write(self.style.ERROR(f"  нет в .po: {text!r}"))
            for text in problems["untranslated"]:
                self.stdout.write(self.style.WARNING(f"  не переведено: {text!r}"))
            total = len(problems["missing"]) + len(problems["untranslated"])
            if total:
                raise CommandError(
                    f"Переводы неполные: {len(problems['missing'])} новых строк, "
                    f"{len(problems['untranslated'])} без перевода. "
                    "Запустите makelocales и переведите пустые msgstr."
                )
            self.stdout.write(self.style.SUCCESS("Переводы полные: все строки есть в .po и переведены."))
            return

        report = i18n_tools.sync(root, locale_dir, settings.SHOP["NAME"])
        for language, info in report.items():
            self.stdout.write(
                f"  {language}: всего {info['total']}, добавлено {len(info['added'])}, "
                f"удалено {len(info['removed'])}"
            )
        untranslated = report["uk"]["untranslated"]
        if untranslated:
            self.stdout.write(self.style.WARNING(
                f"Без украинского перевода: {len(untranslated)} строк — "
                "заполните msgstr в locale/uk/LC_MESSAGES/django.po, затем compilelocales."
            ))
            for text in untranslated[:60]:
                self.stdout.write(f"    {text!r}")
            if len(untranslated) > 60:
                self.stdout.write(f"    … и ещё {len(untranslated) - 60}")
        else:
            self.stdout.write(self.style.SUCCESS("Все строки переведены."))
