"""Карта сайта для поисковых систем.

Домен берётся из запроса, а не из django.contrib.sites: у нас одна
установка на один адрес, и отдельная таблица с доменом — это ещё одно
место, которое забудут поправить при переезде. Так карта сайта
переезжает вместе с сайтом и врать не может.
"""

from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from catalog.models import Category, Product
from pages.models import InfoPage


class HttpsSitemap(Sitemap):
    """Общая основа: заставляет писать в карте https.

    Сама по себе карта берёт схему из запроса, а к Django приходит
    обычный http с адреса 127.0.0.1 — снаружи стоит Cloudflare, и о том,
    что посетитель пришёл по https, Django не знает. Без этой строки в
    карту уходили бы адреса вида http://, и поисковик считал бы их
    отдельной небезопасной версией сайта.

    На копии у себя (DEBUG) оставляем как есть: там https нет.
    """

    @property
    def protocol(self) -> str | None:
        return None if settings.DEBUG else "https"


class StaticSitemap(HttpsSitemap):
    """Страницы без своей записи в базе. Сейчас это только главная —
    она же весь каталог."""

    changefreq = "daily"
    priority = 1.0

    def items(self) -> list[str]:
        return ["catalog:index"]

    def location(self, item: str) -> str:
        return reverse(item)


class CategorySitemap(HttpsSitemap):
    """Разделы каталога. Меняются чаще товаров: приход и уход позиций
    виден именно на них."""

    changefreq = "daily"
    priority = 0.8

    def items(self):
        # nonempty(): пустой раздел отдавать поисковику незачем — он
        # приведёт человека на страницу без товаров
        return Category.objects.active().nonempty().order_by("position", "name")

    def lastmod(self, obj: Category):
        return obj.updated_at


class ProductSitemap(HttpsSitemap):
    """Карточки товаров — основная масса адресов.

    limit разбивает выдачу на файлы, если товаров станет много: в одну
    карту по стандарту помещается 50 000 адресов, но файл такого размера
    поисковики читают неохотно.
    """

    changefreq = "weekly"
    priority = 0.6
    limit = 2000

    def items(self):
        return Product.objects.published().order_by("-created_at")

    def lastmod(self, obj: Product):
        return obj.updated_at


class InfoPageSitemap(HttpsSitemap):
    """Доставка, оплата, о магазине. Меняются редко, но в поиске нужны:
    по ним покупатель решает, можно ли вам доверять."""

    changefreq = "monthly"
    priority = 0.3

    def items(self):
        return InfoPage.objects.active()

    def lastmod(self, obj: InfoPage):
        return obj.updated_at


SITEMAPS = {
    "main": StaticSitemap,
    "categories": CategorySitemap,
    "products": ProductSitemap,
    "info": InfoPageSitemap,
}
