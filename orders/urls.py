from django.urls import path

from orders.views import (
    CartAddView,
    CartClearView,
    CartFormAddView,
    CartFormUpdateView,
    CartRemoveView,
    CartUpdateView,
    CartView,
    OrderSuccessView,
)

app_name = "orders"

urlpatterns = [
    path("", CartView.as_view(), name="cart"),
    path("prinyat/<int:pk>/", OrderSuccessView.as_view(), name="success"),
    # plain forms — work without JavaScript
    path("dobavit/", CartFormAddView.as_view(), name="form-add"),
    path("izmenit/", CartFormUpdateView.as_view(), name="form-update"),
    # the same for fetch: the response is JSON plus ready line markup
    path("api/dobavit/", CartAddView.as_view(), name="api-add"),
    path("api/obnovit/", CartUpdateView.as_view(), name="api-update"),
    path("api/udalit/", CartRemoveView.as_view(), name="api-remove"),
    path("api/ochistit/", CartClearView.as_view(), name="api-clear"),
]
