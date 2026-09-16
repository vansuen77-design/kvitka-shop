"""Собирает переводы: locale/<язык>/LC_MESSAGES/django.po → django.mo

Зачем своя команда вместо штатной manage.py compilemessages: та вызывает
внешнюю программу msgfmt из пакета GNU gettext, которого на Windows нет
и который пришлось бы ставить отдельно. Формат .mo простой и описан в
документации gettext, поэтому проще собрать его самим — тогда переводы
работают на любом компьютере без лишних установок.

Запуск:  python manage.py compilelocales
"""

from __future__ import annotations

import struct
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

MAGIC = 0x950412DE  # подпись .mo в порядке байтов little-endian


def parse_po(text: str) -> dict[str, str]:
    """Разбирает .po в словарь «оригинал → перевод».

    Понимает то, что нам нужно: msgid, msgstr, продолжение строк и
    комментарии. Множественные формы (msgid_plural) не поддерживаем —
    в проекте склонения делает свой шаблонный фильтр plural.
    """
    entries: dict[str, str] = {}
    key: list[str] = []
    value: list[str] = []
    target: list[str] | None = None

    def flush() -> None:
        if target is None:
            return
        msgid, msgstr = "".join(key), "".join(value)
        # пустой msgid — служебный заголовок, пустой перевод — не переведено
        if msgid and msgstr:
            entries[msgid] = msgstr

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("msgid "):
            flush()
            key, value = [unquote(line[6:])], []
            target = key
        elif line.startswith("msgstr "):
            value = [unquote(line[7:])]
            target = value
        elif line.startswith('"') and target is not None:
            target.append(unquote(line))
    flush()
    return entries


def unquote(chunk: str) -> str:
    """«"текст\\n"» → «текст» с настоящим переводом строки."""
    chunk = chunk.strip()
    if len(chunk) >= 2 and chunk[0] == '"' and chunk[-1] == '"':
        chunk = chunk[1:-1]
    return (chunk.replace("\\n", "\n").replace("\\t", "\t")
                 .replace('\\"', '"').replace("\\\\", "\\"))


def build_mo(entries: dict[str, str]) -> bytes:
    """Собирает двоичный .mo — формат из документации GNU gettext."""
    items = sorted(entries.items())
    # заголовок каталога: без него gettext не считает файл валидным
    items.insert(0, ("", "Content-Type: text/plain; charset=UTF-8\n"))

    ids = b"".join(k.encode("utf-8") + b"\x00" for k, _ in items)
    strs = b"".join(v.encode("utf-8") + b"\x00" for _, v in items)

    count = len(items)
    start_ids = 7 * 4 + count * 8 * 2      # заголовок + две таблицы смещений
    start_strs = start_ids + len(ids)

    id_table, str_table = [], []
    offset_id = offset_str = 0
    for key, val in items:
        key_bytes = key.encode("utf-8")
        val_bytes = val.encode("utf-8")
        id_table += [len(key_bytes), start_ids + offset_id]
        str_table += [len(val_bytes), start_strs + offset_str]
        offset_id += len(key_bytes) + 1
        offset_str += len(val_bytes) + 1

    header = struct.pack(
        "<7I", MAGIC, 0, count,
        7 * 4,                    # где начинается таблица оригиналов
        7 * 4 + count * 8,        # где начинается таблица переводов
        0, 0,                     # хеш-таблица не нужна
    )
    tables = struct.pack(f"<{len(id_table)}I", *id_table)
    tables += struct.pack(f"<{len(str_table)}I", *str_table)
    return header + tables + ids + strs


class Command(BaseCommand):
    help = "Собирает .po в .mo без установки gettext"

    def handle(self, *args, **options):
        roots = [Path(path) for path in settings.LOCALE_PATHS]
        total = 0
        for root in roots:
            for po in sorted(root.glob("*/LC_MESSAGES/*.po")):
                entries = parse_po(po.read_text(encoding="utf-8"))
                mo = po.with_suffix(".mo")
                mo.write_bytes(build_mo(entries))
                total += 1
                language = po.parent.parent.name
                self.stdout.write(f"  {language}: {len(entries)} строк → {mo.name}")
        if not total:
            self.stdout.write(self.style.WARNING("Файлов .po не найдено."))
            return
        self.stdout.write(self.style.SUCCESS(f"Собрано каталогов: {total}."))
