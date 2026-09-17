"""makelocales: collecting strings from templates and code, writing and checking .po."""

import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from core import i18n_tools


class ExtractionTests(SimpleTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "templates").mkdir()
        (self.root / "app").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, text):
        path = self.root / rel
        path.write_text(text, encoding="utf-8")
        return path

    def test_template_tags(self):
        self.write("templates/a.html", (
            '{% load i18n %}{% trans "Найти" %} {% trans \'Вход\' as x %}\n'
            '{% blocktrans with sum=total|money %}Итого {{ sum }} ₴{% endblocktrans %}\n'
            '{% blocktrans trimmed %}\n   много\n   пробелов\n{% endblocktrans %}\n'
            '{{ user.first_name|default:_("Кабинет") }}\n'
            '{% trans "Кавычка \\"внутри\\"" %}'
        ))
        found = i18n_tools.collect(self.root)
        self.assertEqual(set(found), {
            "Найти", "Вход", "Итого %(sum)s ₴", "много пробелов", "Кабинет",
            'Кавычка "внутри"',
        })
        self.assertEqual(found["Найти"].places, ["templates/a.html:1"])

    def test_python_calls(self):
        self.write("app/views.py", (
            'from django.utils.translation import gettext as _, gettext_noop\n'
            'A = _("Один")\n'
            'B = gettext_noop(\n    "Два"\n)\n'
            'C = _("Три" " четыре")\n'
            'D = _(name)\n'
            'E = other("не строка перевода")\n'
        ))
        found = i18n_tools.collect(self.root)
        self.assertEqual(set(found), {"Один", "Два", "Три четыре"})

    def test_skips_tests_venv_and_migrations(self):
        (self.root / ".venv").mkdir()
        (self.root / "app" / "migrations").mkdir()
        self.write(".venv/x.py", '_("мимо")')
        self.write("app/migrations/0001.py", '_("мимо")')
        self.write("app/test_x.py", '_("мимо")')
        self.write("app/ok.py", '_("есть")')
        self.assertEqual(set(i18n_tools.collect(self.root)), {"есть"})


class PoTests(SimpleTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "templates").mkdir()
        (self.root / "templates" / "a.html").write_text(
            '{% trans "Найти" %}{% trans "Вход" %}', encoding="utf-8")
        self.locale = self.root / "locale"

    def tearDown(self):
        self.tmp.cleanup()

    def po(self, language):
        return self.locale / language / "LC_MESSAGES" / "django.po"

    def test_sync_keeps_translations_adds_new_drops_old(self):
        i18n_tools.sync(self.root, self.locale, "TEST")
        uk = i18n_tools.read_po(self.po("uk"))
        self.assertEqual(uk, {"Найти": "", "Вход": ""})
        ru = i18n_tools.read_po(self.po("ru"))
        self.assertEqual(ru, {"Найти": "Найти", "Вход": "Вход"})

        # translate one string by hand and change the template
        text = self.po("uk").read_text(encoding="utf-8").replace(
            'msgid "Найти"\nmsgstr ""', 'msgid "Найти"\nmsgstr "Знайти"')
        self.po("uk").write_text(text, encoding="utf-8")
        (self.root / "templates" / "a.html").write_text(
            '{% trans "Найти" %}{% trans "Новое" %}', encoding="utf-8")

        report = i18n_tools.sync(self.root, self.locale, "TEST")
        uk = i18n_tools.read_po(self.po("uk"))
        self.assertEqual(uk, {"Найти": "Знайти", "Новое": ""})
        self.assertEqual(report["uk"]["added"], ["Новое"])
        self.assertEqual(report["uk"]["removed"], ["Вход"])
        self.assertEqual(report["uk"]["untranslated"], ["Новое"])

    def test_check_reports_missing_and_untranslated(self):
        problems = i18n_tools.check(self.root, self.locale)
        self.assertEqual(set(problems["missing"]), {"Найти", "Вход"})
        i18n_tools.sync(self.root, self.locale, "TEST")
        problems = i18n_tools.check(self.root, self.locale)
        self.assertEqual(problems["missing"], [])
        self.assertEqual(set(problems["untranslated"]), {"Найти", "Вход"})

    def test_po_roundtrip_escapes(self):
        (self.root / "templates" / "a.html").write_text(
            '{% trans "Строка с \\"кавычками\\"" %}', encoding="utf-8")
        i18n_tools.sync(self.root, self.locale, "TEST")
        self.assertIn('Строка с "кавычками"', i18n_tools.read_po(self.po("ru")))


class ProjectCatalogTests(SimpleTestCase):
    def test_project_translations_are_complete(self):
        """Same as makelocales --check: no untranslated strings in the code."""
        from django.conf import settings

        problems = i18n_tools.check(Path(settings.BASE_DIR), Path(settings.LOCALE_PATHS[0]))
        self.assertEqual(problems["missing"], [])
        self.assertEqual(problems["untranslated"], [])
