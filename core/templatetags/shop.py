"""Шаблонные фильтры магазина."""

from pathlib import Path

from django import template
from django.conf import settings
from django.contrib.staticfiles import finders
from django.templatetags.static import static

from core.utils import format_money, plural_ru

register = template.Library()


@register.filter(name="money")
def money(value) -> str:
    """{{ 1008|money }} -> «1 008 ₴»"""
    return f"{format_money(value)} {settings.SHOP['CURRENCY']}"


@register.filter(name="money_plain")
def money_plain(value) -> str:
    """Число без валюты: «1 008»."""
    return format_money(value)


@register.filter(name="plural")
def plural(number, forms: str) -> str:
    """{{ 5|plural:"модель,модели,моделей" }} -> «моделей»"""
    parts = [part.strip() for part in forms.split(",")]
    while len(parts) < 3:
        parts.append(parts[-1])
    return plural_ru(number, *parts[:3])


@register.filter(name="get_item")
def get_item(mapping, key):
    """{{ dict|get_item:key }} — в шаблонах Django нет доступа по ключу-переменной."""
    if not hasattr(mapping, "get"):
        return []
    return mapping.get(key, [])


@register.simple_tag(takes_context=True)
def query_replace(context, **kwargs) -> str:
    """Меняет параметры в текущем GET-запросе, сохраняя остальные фильтры."""
    request = context["request"]
    params = request.GET.copy()
    for key, value in kwargs.items():
        if value in (None, ""):
            params.pop(key, None)
        else:
            params[key] = value
    return params.urlencode()


# --- адреса статики с отметкой времени -----------------------------------
# Сервер отдаёт css и js в обход middleware, поэтому запрет кэширования
# на них не действует: браузер держит старый файл, и правки «не видны»,
# пока не нажать Ctrl+F5. Дописываем к адресу время изменения файла —
# поменяли файл, адрес изменился, браузер скачал заново.
_cache: dict[str, str] = {}


@register.simple_tag
def versioned(path: str) -> str:
    url = static(path)
    if path in _cache:
        return _cache[path]
    try:
        found = finders.find(path)
        stamp = int(Path(found).stat().st_mtime) if found else 0
    except (OSError, TypeError):
        stamp = 0
    result = f"{url}?v={stamp}" if stamp else url
    _cache[path] = result
    return result
