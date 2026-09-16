from django.urls import path

from catalog.exports import PriceXlsxView, PriceXmlView
from catalog.views import CatalogView, ProductDetailView

app_name = "catalog"

urlpatterns = [
    path("", CatalogView.as_view(), name="index"),
    path("katalog/<slug:category_slug>/", CatalogView.as_view(), name="category"),
    path("tovar/<slug:slug>/", ProductDetailView.as_view(), name="product"),
    path("price/xlsx/", PriceXlsxView.as_view(), name="price-xlsx"),
    path("price/xml/", PriceXmlView.as_view(), name="price-xml"),
]
