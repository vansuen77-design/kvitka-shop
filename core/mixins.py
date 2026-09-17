"""View mixins: small pieces of behaviour mixed into Django's class-based
views."""

import json

from django.http import HttpResponse, JsonResponse
from django.utils.cache import patch_vary_headers


class PageTitleMixin:
    """Adds the page title and breadcrumbs to the context."""

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
    """Parses the request body as JSON (fetch from the frontend)."""

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
    """If the request came via fetch, return only the list fragment.

    One URL serves both HTML and JSON — so both responses are marked
    Vary: X-Requested-With, and JSON additionally no-store: otherwise the
    Back button would show raw JSON from the browser cache instead of the page.
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
