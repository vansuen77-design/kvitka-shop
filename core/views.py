"""Service pages that belong to no app."""

from django.http import HttpRequest, HttpResponse
from django.urls import reverse

from core.context_processors import site_address


def robots_txt(request: HttpRequest) -> HttpResponse:
    """Crawling rules for search engine robots.

    Served from Django rather than a static file for the sake of one line —
    the sitemap address. It must be absolute, with the domain, and move
    together with the site.

    Only service areas are closed: the admin and its gate, the customer
    account, the cart and price exports. Catalog pages with filter
    checkboxes are deliberately left open — duplicates are handled by the
    canonical link in the head, and a robots.txt ban would stop the crawler
    from reaching the products themselves.
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
