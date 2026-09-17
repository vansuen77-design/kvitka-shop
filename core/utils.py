"""Helper functions with no dependency on Django models."""

from decimal import Decimal

_TRANSLIT_MAP = {
    "а": "a", "б": "b", "в": "v", "г": "g", "ґ": "g", "д": "d", "е": "e",
    "ё": "e", "є": "e", "ж": "zh", "з": "z", "и": "i", "і": "i", "ї": "yi",
    "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p",
    "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e",
    "ю": "yu", "я": "ya",
}


def transliterate(text: str) -> str:
    """Cyrillic -> Latin, so that slugs come out readable."""
    result = []
    for char in text.lower():
        if char in _TRANSLIT_MAP:
            result.append(_TRANSLIT_MAP[char])
        elif char.isalnum():
            result.append(char)
        else:
            result.append("-")
    slug = "".join(result)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")


def format_money(value) -> str:
    """1008 -> "1 008". A thin space separates thousands."""
    if value is None:
        return "0"
    amount = Decimal(value).quantize(Decimal("1"))
    text = f"{int(amount):,}".replace(",", " ")
    return text


def plural_ru(number: int, one: str, few: str, many: str) -> str:
    """Russian plural forms: 1 модель, 2 модели, 5 моделей."""
    number = abs(int(number))
    if number % 10 == 1 and number % 100 != 11:
        return one
    if 2 <= number % 10 <= 4 and not 12 <= number % 100 <= 14:
        return few
    return many
