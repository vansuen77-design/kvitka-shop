"""Админка информационных страниц."""

from django.contrib import admin

from pages.models import InfoPage


@admin.register(InfoPage)
class InfoPageAdmin(admin.ModelAdmin):
    list_display = ("name", "group", "address", "position", "is_active")
    list_display_links = ("name",)
    list_editable = ("group", "position", "is_active")
    list_filter = ("group", "is_active")
    search_fields = ("name", "name_uk", "lead", "lead_uk", "body", "body_uk")
    prepopulated_fields = {"slug": ("name",)}
    save_on_top = True

    fieldsets = (
        ("Страница", {"fields": ("name", "slug", "lead", "body")}),
        ("Украинская версия", {
            "fields": ("name_uk", "lead_uk", "body_uk"),
            "description": "Не заполнено - на украинской версии сайта "
                           "покажется русский текст.",
        }),
        ("Где показывать", {
            "fields": ("group", "position", "is_active", "external_url"),
        }),
    )

    @admin.display(description="адрес")
    def address(self, obj):
        return obj.get_absolute_url()
