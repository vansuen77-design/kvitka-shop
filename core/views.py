"""Служебные страницы, не принадлежащие ни одному разделу."""

from django.http import HttpRequest, HttpResponse
from django.urls import reverse

from core.context_processors import site_address


def robots_txt(request: HttpRequest) -> HttpResponse:
    """Правила обхода для поисковых роботов.

    Отдаём из Django, а не файлом в static, ради одной строки — адреса
    карты сайта. Он должен быть полным, с доменом, и переезжать вместе
    с сайтом.

    Закрываем только служебное: админку и шлюз перед ней, кабинет
    покупателя, корзину и выгрузки прайса. Страницы каталога с галками
    фильтров намеренно оставлены открытыми — дубли берёт на себя
    canonical в шапке страницы, а запрет через robots.txt мешал бы
    поисковику дойти до самих товаров.
    """
    sitemap_url = f"{site_address(request)}{reverse('sitemap')}"
    lines = [
        "User-agent: *",
        "Disallow: /admin/",
        "Disallow: /vhod-v-upravlenie/",
        "Disallow: /kabinet/",
        "Disallow: /korzina/",
        "Disallow: /price/",
        "Disallow: /i18n/",
        "",
        f"Sitemap: {sitemap_url}",
        "",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")
