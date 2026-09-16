"""Ссылки для подвала — собираются из таблицы страниц.

Подвал рисуется на каждой странице сайта, поэтому здесь ничего не должно
падать: если таблицы ещё нет (не применили миграции) или база временно
недоступна, отдаём пустые списки — колонки просто не покажутся.
"""

from django.db import DatabaseError

from pages.models import InfoPage

# страница, на которую ссылается галка согласия под формой заказа
PRIVACY_SLUG = "politika-konfidentsialnosti"


def footer_links(request) -> dict:
    try:
        pages = list(InfoPage.objects.active())
    except DatabaseError:
        pages = []
    visible = [p for p in pages if p.group != InfoPage.Group.HIDDEN]
    return {
        "footer_buyer": [p for p in visible if p.group == InfoPage.Group.BUYER],
        "footer_partner": [p for p in visible if p.group == InfoPage.Group.PARTNER],
        # если страницы ещё нет, ссылка под галкой просто не покажется —
        # форма от этого не ломается
        "privacy_page": next((p for p in pages if p.slug == PRIVACY_SLUG), None),
    }
