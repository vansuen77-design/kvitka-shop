"""Data every template needs: the top category menu and the page address."""

from django.conf import settings

from catalog.models import Category


def navigation(request) -> dict:
    """Top-level categories for the header and footer menus.

    nonempty(): a category without a single product is hidden. An empty
    shelf in the menu promises something that is not there, and the visitor
    leaves feeling the shop is unfinished. Once a product appears the
    category comes back by itself, nothing to switch on by hand.
    """
    return {
        "root_categories": (
            Category.objects.active().nonempty().filter(parent__isnull=True)
        ),
    }


def site_address(request) -> str:
    """Prefix of every external link: scheme and domain.

    Taken from SITE_URL, not from the request. Not out of pedantry: Django
    receives plain http from 127.0.0.1 — Cloudflare sits in front, and the
    header saying the visitor came over https never reaches us. Asking the
    request would put http:// into the sitemap and canonical links, and the
    search engine would treat that as a separate, insecure version of the site.

    It also merges www and non-www: SITE_URL is one, and both versions point
    to it as the main one.

    On the local copy SITE_URL is empty — the request address is returned
    then, otherwise local links would lead to the live site.
    """
    return settings.SITE_URL or f"{request.scheme}://{request.get_host()}"


def canonical(request) -> dict:
    """The real page address — the one that should end up in search.

    The same product list opens under dozens of URLs: ?sort=, ?q=, filter
    checkboxes in arbitrary order. To a search engine these are different
    pages with identical content, and it picks which one to show — usually
    not the one we want. So the head says plainly: this is the main address.

    The page number is kept. The second page of a list really is different
    products, and merging it with the first would hide half of the catalog
    from search.
    """
    base = site_address(request)
    page = request.GET.get("page", "")
    suffix = f"?page={page}" if page.isdigit() and page != "1" else ""
    return {
        "site_url": base,
        "canonical_url": f"{base}{request.path}{suffix}",
    }
