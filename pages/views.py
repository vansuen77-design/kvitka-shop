"""Показ информационной страницы."""

from django.views.generic import DetailView

from core.mixins import PageTitleMixin
from pages.models import InfoPage


class InfoPageView(PageTitleMixin, DetailView):
    model = InfoPage
    template_name = "pages/page_detail.html"
    context_object_name = "page"

    def get_queryset(self):
        return InfoPage.objects.active()

    def get_page_title(self) -> str:
        return self.object.title

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumbs"] = [
            {"title": "Каталог", "url": "/"},
            {"title": self.object.title, "url": None},
        ]
        context["blocks"] = self.object.blocks()
        context["neighbours"] = (
            InfoPage.objects.active()
            .filter(group=self.object.group, external_url="")
            .exclude(pk=self.object.pk)
        )
        return context
