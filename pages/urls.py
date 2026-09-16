from django.urls import path

from pages.views import InfoPageView

app_name = "pages"

urlpatterns = [
    path("<slug:slug>/", InfoPageView.as_view(), name="detail"),
]
