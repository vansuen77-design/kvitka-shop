"""Root URLs of the project."""

from django.conf import settings
from django.contrib import admin
from django.contrib.sitemaps.views import index as sitemap_index, sitemap
from django.urls import include, path, re_path

from core.admin_gate import gate_view
from core.sitemaps import SITEMAPS
from core.views import robots_txt
from django.views.static import serve

# Admin titles come from the shop settings so the name lives in one place
admin.site.site_header = f"{settings.SHOP['NAME']} — управление магазином"
admin.site.site_title = settings.SHOP["NAME"]
admin.site.index_title = "Цветы с доставкой"

urlpatterns = [
    # For search engines. robots.txt and sitemap.xml must live at the site
    # root: crawlers look for them only there.
    #
    # sitemap.xml is not the address list itself but an index: it links to
    # four parts (home, categories, products, info pages). The extra layer
    # is for growth. One sitemap holds a limited number of addresses, and
    # once there are more products than that, the sitemap would silently
    # split into pages — and the crawler would see only the first one and
    # never learn about new products. With an index that cannot happen.
    path("robots.txt", robots_txt, name="robots"),
    path("sitemap.xml", sitemap_index,
         {"sitemaps": SITEMAPS, "sitemap_url_name": "sitemap-section"},
         name="sitemap"),
    path("sitemap-<section>.xml", sitemap,
         {"sitemaps": SITEMAPS}, name="sitemap-section"),
    # the gate before the admin: a one-time code from Telegram.
    # Placed above the admin itself so that the admin does not capture the URL.
    path("vhod-v-upravlenie/", gate_view, name="admin-gate"),
    path("admin/", admin.site.urls),
    # language switcher: a plain POST form, works without JavaScript
    path("i18n/", include("django.conf.urls.i18n")),
    path("korzina/", include(("orders.urls", "orders"), namespace="orders")),
    path("kabinet/", include(("accounts.urls", "accounts"), namespace="accounts")),
    path("info/", include(("pages.urls", "pages"), namespace="pages")),
    path("", include(("catalog.urls", "catalog"), namespace="catalog")),
]

# Product photos and collected static files.
#
# Usually a web server does this, but here the server is the computer
# itself and there is nobody else to serve files. The load of a small shop
# is low, and Cloudflare in front of us caches the images anyway.
urlpatterns += [
    re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
    re_path(r"^static/(?P<path>.*)$", serve, {"document_root": settings.STATIC_ROOT}),
]
