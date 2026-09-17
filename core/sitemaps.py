"""Sitemap for search engines.

The domain comes from the request, not from django.contrib.sites: one
installation serves one address, and a separate table with the domain is
one more place people forget to fix when moving. This way the sitemap moves
together with the site and cannot lie.
"""

from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from catalog.models import Category, Product
from pages.models import InfoPage


class HttpsSitemap(Sitemap):
    """Common base: forces https in the sitemap.

    By itself the sitemap takes the scheme from the request, and Django
    receives plain http from 127.0.0.1 — Cloudflare sits in front, and
    Django does not know the visitor came over https. Without this the
    sitemap would list http:// addresses, and the search engine would treat
    them as a separate insecure version of the site.

    On the local copy (DEBUG) it is left as is: there is no https there.
    """

    @property
    def protocol(self) -> str | None:
        return None if settings.DEBUG else "https"


class StaticSitemap(HttpsSitemap):
    """Pages without their own database record. Currently only the home
    page — which is the whole catalog."""

    changefreq = "daily"
    priority = 1.0

    def items(self) -> list[str]:
        return ["catalog:index"]

    def location(self, item: str) -> str:
        return reverse(item)


class CategorySitemap(HttpsSitemap):
    """Catalog categories. They change more often than products: items
    arriving and leaving show up on them."""

    changefreq = "daily"
    priority = 0.8

    def items(self):
        # nonempty(): no point giving an empty category to the crawler —
        # it would bring a visitor to a page without products
        return Category.objects.active().nonempty().order_by("position", "name")

    def lastmod(self, obj: Category):
        return obj.updated_at


class ProductSitemap(HttpsSitemap):
    """Product pages — the bulk of the addresses.

    limit splits the output into files when there are many products: the
    standard allows 50 000 addresses per sitemap, but search engines are
    reluctant to read files that big.
    """

    changefreq = "weekly"
    priority = 0.6
    limit = 2000

    def items(self):
        return Product.objects.published().order_by("-created_at")

    def lastmod(self, obj: Product):
        return obj.updated_at


class InfoPageSitemap(HttpsSitemap):
    """Delivery, payment, about the shop. Rarely change, but needed in
    search: by them a customer decides whether to trust you."""

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
