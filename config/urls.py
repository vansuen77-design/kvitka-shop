"""Корневые адреса проекта."""

from django.conf import settings
from django.contrib import admin
from django.contrib.sitemaps.views import index as sitemap_index, sitemap
from django.urls import include, path, re_path

from core.admin_gate import gate_view
from core.sitemaps import SITEMAPS
from core.views import robots_txt
from django.views.static import serve

# Заголовки админки — из настроек магазина, чтобы имя жило в одном месте
admin.site.site_header = f"{settings.SHOP['NAME']} — управление магазином"
admin.site.site_title = settings.SHOP["NAME"]
admin.site.index_title = "Цветы с доставкой"

urlpatterns = [
    # Для поисковых систем. robots.txt и sitemap.xml обязаны лежать
    # в корне сайта: роботы ищут их только там.
    #
    # sitemap.xml — не сам список адресов, а оглавление: в нём ссылки на
    # четыре части (главная, разделы, товары, информационные страницы).
    # Лишний слой нужен на вырост. В одну карту помещается ограниченное
    # число адресов, и когда товаров станет больше этого предела, карта
    # молча разобьётся на страницы — а поисковик увидит только первую
    # и о новых товарах не узнает. С оглавлением этого не случится.
    path("robots.txt", robots_txt, name="robots"),
    path("sitemap.xml", sitemap_index,
         {"sitemaps": SITEMAPS, "sitemap_url_name": "sitemap-section"},
         name="sitemap"),
    path("sitemap-<section>.xml", sitemap,
         {"sitemaps": SITEMAPS}, name="sitemap-section"),
    # шлюз перед админкой: одноразовый код из Telegram.
    # Стоит выше самой админки, чтобы адрес не перехватывался ею.
    path("vhod-v-upravlenie/", gate_view, name="admin-gate"),
    path("admin/", admin.site.urls),
    # переключатель языка: обычная форма POST, работает и без JavaScript
    path("i18n/", include("django.conf.urls.i18n")),
    path("korzina/", include(("orders.urls", "orders"), namespace="orders")),
    path("kabinet/", include(("accounts.urls", "accounts"), namespace="accounts")),
    path("info/", include(("pages.urls", "pages"), namespace="pages")),
    path("", include(("catalog.urls", "catalog"), namespace="catalog")),
]

# Фотографии товаров и собранная статика.
#
# Обычно этим занимается веб-сервер, но здесь сервер — сам компьютер,
# и раздавать файлы больше некому. Нагрузка у небольшого магазина
# невелика, а Cloudflare перед нами всё равно кэширует картинки.
urlpatterns += [
    re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
    re_path(r"^static/(?P<path>.*)$", serve, {"document_root": settings.STATIC_ROOT}),
]
