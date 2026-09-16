"""Админка каталога.

Здесь владелец ведёт ассортимент: цены, остатки, описания, фотографии,
статусы, разделы и справочники подбора.
"""

from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html

from catalog.deletion import describe, plural
from catalog.models import (
    Category,
    Color,
    FacetGroup,
    Flower,
    Kind,
    Occasion,
    Product,
    ProductImage,
    Size,
    Status,
)


# --- вложенные блоки ------------------------------------------------------
class ProductImageInline(admin.TabularInline):
    """Фотографии прямо внутри карточки товара."""

    model = ProductImage
    extra = 1
    fields = ("preview", "image", "alt", "position")
    readonly_fields = ("preview",)
    verbose_name = "фотография"
    verbose_name_plural = ("фотографии — первая по порядку становится обложкой; "
                           "чтобы убрать снимок, отметьте «Удалить?» и нажмите «Сохранить»")

    @admin.display(description="просмотр")
    def preview(self, obj):
        if obj.pk and obj.image:
            return format_html(
                '<img src="{}" style="height:90px;border:1px solid #ddd;'
                'border-radius:3px;object-fit:contain;background:#fff">',
                obj.image.url,
            )
        return "—"


class SubcategoryInline(admin.TabularInline):
    """Подразделы внутри раздела."""

    model = Category
    extra = 1
    fields = ("name", "name_uk", "position", "is_active")
    verbose_name = "подраздел"
    verbose_name_plural = "подразделы"


class UnpublishWarningMixin:
    """Предупреждает, что удаление значения уберёт товары из каталога.

    Само снятие с публикации делает сигнал в catalog/signals.py — здесь
    только текст, который менеджер видит перед тем, как нажать «Да».
    """

    def delete_view(self, request, object_id, extra_context=None):
        obj = self.get_object(request, object_id)
        extra_context = {**(extra_context or {}),
                         "kvitka_unpublish": describe(obj) if obj else None}
        return super().delete_view(request, object_id, extra_context)

    def delete_queryset(self, request, queryset):
        total = 0
        for obj in queryset:
            info = describe(obj)
            total += info["published"] if info else 0
        super().delete_queryset(request, queryset)
        if total:
            self.message_user(
                request,
                f"Сняты с публикации {total} {plural(total)} — "
                f"они остались в базе, вернуть можно галкой в списке товаров.",
            )

    def delete_model(self, request, obj):
        info = describe(obj)
        super().delete_model(request, obj)
        if info and info["published"]:
            count = info["published"]
            self.message_user(
                request,
                f"Сняты с публикации {count} {plural(count)} — "
                f"они остались в базе, вернуть можно галкой в списке товаров.",
            )


# --- товары ---------------------------------------------------------------
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "thumb", "article", "name", "kind", "size", "category",
        "price", "status", "stock_quantity", "is_active",
    )
    list_display_links = ("article", "name")
    list_editable = ("price", "status", "stock_quantity", "is_active")
    # справочники подбора перечислены здесь руками: сами они в фильтрах
    # не появятся. Добавили строку в catalog/facets.py — допишите и сюда
    list_filter = ("status", "category", "kind", "flowers", "occasions",
                   "color", "size", "is_active")
    search_fields = ("article", "name", "name_uk", "family", "composition",
                     "flowers__name")
    filter_horizontal = ("flowers", "occasions")
    list_per_page = 30
    save_on_top = True
    inlines = [ProductImageInline]
    actions = ["activate", "deactivate"]

    fieldsets = (
        ("Основное", {
            "fields": ("article", "name", "name_uk", "category", "status",
                       "is_active", "position"),
        }),
        ("Цена и остаток", {
            "fields": ("price", "old_price", "stock_quantity"),
            "description": "Старая цена выше текущей — на карточке появится "
                           "зачёркнутая цена и процент скидки. Остаток — "
                           "сколько таких букетов можно собрать сегодня.",
        }),
        ("Подбор — по этим полям товар находят в каталоге", {
            "fields": ("kind", "flowers", "occasions", "color", "size"),
            "description": "Это те самые группы в левой панели каталога. "
                           "Значения ведутся в справочниках рядом — новое "
                           "значение появляется в фильтре само.",
        }),
        ("Варианты размера", {
            "fields": ("family", "stems", "height_cm"),
            "description": "Букеты с одинаковым семейством (например "
                           "«rozy-krasnye») получают на странице переключатель "
                           "размера. Число цветков — подпись кнопки.",
        }),
        ("Описание и состав", {
            "fields": ("summary", "summary_uk", "composition", "composition_uk",
                       "description", "description_uk"),
        }),
        ("Адрес страницы", {
            "classes": ("collapse",),
            "fields": ("slug",),
            "description": "Оставьте пустым — заполнится само по названию.",
        }),
    )

    def get_queryset(self, request):
        return (
            super().get_queryset(request)
            .select_related("category", "status", "kind", "size")
        )

    @admin.display(description="фото")
    def thumb(self, obj):
        cover = obj.cover
        if cover and cover.image:
            return format_html(
                '<img src="{}" style="height:56px;width:56px;object-fit:cover;'
                'background:#fff;border:1px solid #e3dbd2;border-radius:3px">',
                cover.image.url,
            )
        return format_html('<span style="color:#999">нет фото</span>')

    @admin.action(description="Показывать на сайте")
    def activate(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"Показаны на сайте: {updated}")

    @admin.action(description="Скрыть с сайта")
    def deactivate(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"Скрыты: {updated}")


# --- справочники ----------------------------------------------------------
@admin.register(Category)
class CategoryAdmin(UnpublishWarningMixin, admin.ModelAdmin):
    list_display = ("name", "name_uk", "parent", "products_count",
                    "position", "is_active")
    list_editable = ("position", "is_active")
    list_filter = ("parent", "is_active")
    search_fields = ("name",)
    inlines = [SubcategoryInline]
    fields = ("name", "name_uk", "parent", "description", "position",
              "is_active", "slug")

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(total=Count("products"))

    @admin.display(description="товаров", ordering="total")
    def products_count(self, obj):
        return obj.total


@admin.register(Status)
class StatusAdmin(UnpublishWarningMixin, admin.ModelAdmin):
    list_display = ("swatch", "name", "is_orderable", "note", "position", "is_active")
    list_display_links = ("name",)
    list_editable = ("is_orderable", "note", "position", "is_active")
    fields = ("name", "name_uk", "color", "is_orderable", "note",
              "position", "is_active")

    @admin.display(description="цвет")
    def swatch(self, obj):
        return format_html(
            '<span style="display:inline-block;width:22px;height:22px;'
            'border-radius:3px;background:{};border:1px solid #0002"></span>',
            obj.color,
        )


class AttributeAdmin(UnpublishWarningMixin, admin.ModelAdmin):
    """Общая админка справочников подбора: значение, порядок, видимость.

    Каждое значение — пункт в левой панели каталога. Счётчик показывает,
    сколько товаров на него ссылается. Значение без товаров покупателю
    не показывается — панель прячет пустые пункты, пока товар не появится.
    """

    list_display = ("name", "name_uk", "products_count", "position", "is_active")
    list_editable = ("position", "is_active")
    search_fields = ("name",)
    fields = ("name", "name_uk", "position", "is_active")

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(total=Count("products"))

    @admin.display(description="товаров", ordering="total")
    def products_count(self, obj):
        return obj.total


@admin.register(Kind)
class KindAdmin(AttributeAdmin):
    pass


@admin.register(Flower)
class FlowerAdmin(AttributeAdmin):
    pass


@admin.register(Occasion)
class OccasionAdmin(AttributeAdmin):
    pass


@admin.register(Color)
class ColorAdmin(AttributeAdmin):
    pass


@admin.register(Size)
class SizeAdmin(AttributeAdmin):
    pass


@admin.register(FacetGroup)
class FacetGroupAdmin(admin.ModelAdmin):
    """Панель подбора: какие группы показывать покупателю и в каком порядке."""

    list_display = ("name", "code", "values_count", "position",
                    "has_search", "is_active")
    list_display_links = ("name",)
    list_editable = ("position", "has_search", "is_active")
    ordering = ("position", "name")
    readonly_fields = ("code",)
    fields = ("code", "name", "position", "has_search", "is_active")

    def has_add_permission(self, request) -> bool:
        # строки заводит команда seed_facets — по одной на справочник
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False

    @admin.display(description="значений в справочнике")
    def values_count(self, obj):
        from catalog.facets import BY_CODE

        spec = BY_CODE.get(obj.code)
        return spec.model.objects.count() if spec else "—"
