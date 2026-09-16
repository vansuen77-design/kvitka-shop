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
    # обычные формы — работают без JavaScript
    path("dobavit/", CartFormAddView.as_view(), name="form-add"),
    path("izmenit/", CartFormUpdateView.as_view(), name="form-update"),
    # то же самое для fetch: ответ — JSON и готовая разметка строк
    path("api/dobavit/", CartAddView.as_view(), name="api-add"),
    path("api/obnovit/", CartUpdateView.as_view(), name="api-update"),
    path("api/udalit/", CartRemoveView.as_view(), name="api-remove"),
    path("api/ochistit/", CartClearView.as_view(), name="api-clear"),
]
