"""Миксины для представлений: маленькие кусочки поведения, которые
подмешиваются к классам Django (CBV)."""

import json

from django.http import HttpResponse, JsonResponse
from django.utils.cache import patch_vary_headers


class PageTitleMixin:
    """Добавляет заголовок страницы и хлебные крошки в контекст."""

    page_title: str = ""
    breadcrumbs: list | None = None

    def get_page_title(self) -> str:
        return self.page_title

    def get_breadcrumbs(self) -> list:
        return list(self.breadcrumbs or [])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("page_title", self.get_page_title())
        context.setdefault("breadcrumbs", self.get_breadcrumbs())
        return context


class JsonRequestMixin:
    """Разбирает тело запроса как JSON (fetch с фронтенда)."""

    def get_payload(self) -> dict:
        if self.request.content_type == "application/json":
            try:
                raw = self.request.body.decode("utf-8") or "{}"
                data = json.loads(raw)
            except (ValueError, UnicodeDecodeError):
                return {}
            return data if isinstance(data, dict) else {}
        return self.request.POST.dict()

    @staticmethod
    def ok(**data) -> JsonResponse:
        return JsonResponse({"ok": True, **data})

    @staticmethod
    def fail(message: str, status: int = 400) -> JsonResponse:
        return JsonResponse({"ok": False, "error": message}, status=status)


class AjaxTemplateMixin:
    """Если запрос пришёл через fetch, отдаём только фрагмент списка.

    Один адрес отдаёт и HTML, и JSON — поэтому оба ответа помечены
    Vary: X-Requested-With, а JSON ещё и no-store: иначе кнопка «Назад»
    показывала бы вместо страницы голый JSON из кэша браузера (грабля 18).
    """

    ajax_template_name: str = ""

    def is_ajax(self) -> bool:
        return self.request.headers.get("X-Requested-With") == "fetch"

    @staticmethod
    def mark_vary(response: HttpResponse) -> HttpResponse:
        patch_vary_headers(response, ["X-Requested-With"])
        return response

    def render_fragment(self, context) -> HttpResponse:
        from django.template.loader import render_to_string

        html = render_to_string(self.ajax_template_name, context, request=self.request)
        response = JsonResponse(
            {
                "ok": True,
                "html": html,
                "count": context.get("total_count", 0),
                "query": self.request.GET.urlencode(),
            }
        )
        response["Cache-Control"] = "no-store"
        return self.mark_vary(response)
