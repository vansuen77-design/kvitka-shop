"""Shop template filters."""

from pathlib import Path

from django import template
from django.conf import settings
from django.contrib.staticfiles import finders
from django.templatetags.static import static

from core.utils import format_money, plural_ru

register = template.Library()


@register.filter(name="money")
def money(value) -> str:
    """{{ 1008|money }} -> "1 008 ₴\""""
    return f"{format_money(value)} {settings.SHOP['CURRENCY']}"


@register.filter(name="money_plain")
def money_plain(value) -> str:
    """Number without currency: "1 008"."""
    return format_money(value)


@register.filter(name="plural")
def plural(number, forms: str) -> str:
    """{{ 5|plural:"модель,модели,моделей" }} -> "моделей" (Russian plural forms)"""
    parts = [part.strip() for part in forms.split(",")]
    while len(parts) < 3:
        parts.append(parts[-1])
    return plural_ru(number, *parts[:3])


@register.filter(name="get_item")
def get_item(mapping, key):
    """{{ dict|get_item:key }} — Django templates cannot index by a variable key."""
    if not hasattr(mapping, "get"):
        return []
    return mapping.get(key, [])


@register.simple_tag(takes_context=True)
def query_replace(context, **kwargs) -> str:
    """Changes parameters of the current GET query, keeping the other filters."""
    request = context["request"]
    params = request.GET.copy()
    for key, value in kwargs.items():
        if value in (None, ""):
            params.pop(key, None)
        else:
            params[key] = value
    return params.urlencode()


# --- static URLs with a timestamp ---------------------------------------
# The server serves css and js bypassing middleware, so the no-cache rule
# does not apply to them: the browser keeps the old file and edits are
# "invisible" until Ctrl+F5. The file's modification time is appended to
# the URL — file changed, URL changed, browser downloads it again.
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
