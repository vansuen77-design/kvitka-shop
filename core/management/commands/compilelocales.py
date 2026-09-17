"""Compiles translations: locale/<lang>/LC_MESSAGES/django.po → django.mo

Why a custom command instead of manage.py compilemessages: that one calls
the external msgfmt program from GNU gettext, which is not on Windows and
would have to be installed separately. The .mo format is simple and
documented by gettext, so it is easier to build it ourselves — then
translations work on any computer without extra installs.

Run:  python manage.py compilelocales
"""

from __future__ import annotations

import struct
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

MAGIC = 0x950412DE  # .mo signature in little-endian byte order


def parse_po(text: str) -> dict[str, str]:
    """Parses a .po into a "source → translation" dictionary.

    Understands what we need: msgid, msgstr, continuation lines and
    comments. Plural forms (msgid_plural) are not supported — the project
    handles plurals with its own template filter.
    """
    entries: dict[str, str] = {}
    key: list[str] = []
    value: list[str] = []
    target: list[str] | None = None

    def flush() -> None:
        if target is None:
            return
        msgid, msgstr = "".join(key), "".join(value)
        # empty msgid is the header entry, empty translation means untranslated
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
    """'"text\\n"' → 'text' with a real line break."""
    chunk = chunk.strip()
    if len(chunk) >= 2 and chunk[0] == '"' and chunk[-1] == '"':
        chunk = chunk[1:-1]
    return (chunk.replace("\\n", "\n").replace("\\t", "\t")
                 .replace('\\"', '"').replace("\\\\", "\\"))


def build_mo(entries: dict[str, str]) -> bytes:
    """Builds the binary .mo — the format from the GNU gettext documentation."""
    items = sorted(entries.items())
    # catalog header: without it gettext does not consider the file valid
    items.insert(0, ("", "Content-Type: text/plain; charset=UTF-8\n"))

    ids = b"".join(k.encode("utf-8") + b"\x00" for k, _ in items)
    strs = b"".join(v.encode("utf-8") + b"\x00" for _, v in items)

    count = len(items)
    start_ids = 7 * 4 + count * 8 * 2      # header + two offset tables
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
        7 * 4,                    # where the source table starts
        7 * 4 + count * 8,        # where the translation table starts
        0, 0,                     # no hash table
    )
    tables = struct.pack(f"<{len(id_table)}I", *id_table)
    tables += struct.pack(f"<{len(str_table)}I", *str_table)
    return header + tables + ids + strs


class Command(BaseCommand):
    help = "Compiles .po into .mo without installing gettext"

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
                self.stdout.write(f"  {language}: {len(entries)} strings → {mo.name}")
        if not total:
            self.stdout.write(self.style.WARNING("No .po files found."))
            return
        self.stdout.write(self.style.SUCCESS(f"Catalogs compiled: {total}."))
