"""Order admin: the florist sees contacts, delivery, contents and manages the status."""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from orders.models import Order, OrderLine

STATUS_COLORS = {
    Order.Status.NEW: "#B23A5E",
    Order.Status.CONFIRMED: "#A9691F",
    Order.Status.DELIVERING: "#3F6E8C",
    Order.Status.DONE: "#4A6B45",
    Order.Status.CANCELLED: "#8C8079",
}


class OrderLineInline(admin.TabularInline):
    model = OrderLine
    extra = 0
    fields = ("article", "product_name", "quantity", "unit_price",
              "amount_display")
    readonly_fields = ("amount_display",)
    verbose_name = "позиция"
    verbose_name_plural = "позиции заказа"

    @admin.display(description="сумма")
    def amount_display(self, obj):
        return f"{obj.amount} ₴" if obj.pk else "—"


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    # The list shows everything needed to assemble and deliver a bouquet:
    # who ordered, where and when to deliver, what to write on the card.
    # Packed into a few columns, otherwise the table would have to be
    # scrolled sideways to read a single order.
    list_display = (
        "number", "created_short", "customer", "delivery_info",
        "total_amount", "comment_short", "status_badge", "status",
    )
    list_display_links = ("number", "customer")
    list_editable = ("status",)
    list_filter = ("status", "delivery", "payment", "delivery_date", "created_at")
    search_fields = ("name", "phone", "email", "address", "recipient_name",
                     "recipient_phone", "lines__article")
    list_select_related = ("user",)
    date_hierarchy = "created_at"
    inlines = [OrderLineInline]
    list_per_page = 40
    save_on_top = True
    readonly_fields = ("user", "created_at", "updated_at",
                       "total_quantity", "goods_amount", "delivery_cost",
                       "total_amount")

    fieldsets = (
        ("Покупатель", {
            "fields": ("name", "phone", "email"),
        }),
        ("Доставка", {
            "fields": ("delivery", "address", ("delivery_date", "delivery_time"),
                       ("recipient_name", "recipient_phone"), "card_text",
                       "payment"),
        }),
        ("Заказ", {
            "fields": ("status", "comment", "manager_note",
                       ("total_quantity", "goods_amount"),
                       ("delivery_cost", "total_amount")),
        }),
        ("Служебное", {
            "classes": ("collapse",),
            "fields": ("user", "created_at", "updated_at"),
        }),
    )

    @admin.display(description="заказ", ordering="pk")
    def number(self, obj):
        return obj.number

    @admin.display(description="оформлен", ordering="created_at")
    def created_short(self, obj):
        return obj.created_at.strftime("%d.%m %H:%M")

    @admin.display(description="покупатель", ordering="name")
    def customer(self, obj):
        rows = [format_html("<b>{}</b>", obj.name),
                format_html('<a href="tel:{}">{}</a>', obj.phone, obj.phone)]
        if obj.email:
            rows.append(format_html('<a href="mailto:{}">{}</a>',
                                    obj.email, obj.email))
        return format_html('<div style="line-height:1.5">{}</div>',
                           mark_safe("<br>".join(rows)))

    @admin.display(description="доставка", ordering="delivery_date")
    def delivery_info(self, obj):
        rows = []
        when = " ".join(filter(None, [
            obj.delivery_date.strftime("%d.%m") if obj.delivery_date else "",
            obj.get_delivery_time_display() if obj.delivery_time else "",
        ]))
        if obj.is_pickup:
            rows.append(format_html("<b>Самовывоз</b> {}", when))
        else:
            rows.append(format_html("<b>{}</b> {}", obj.address, when))
        if obj.recipient_name or obj.recipient_phone:
            rows.append(format_html(
                '<span style="color:#6B625B">получатель: {} {}</span>',
                obj.recipient_name, obj.recipient_phone))
        if obj.card_text:
            rows.append(format_html(
                '<span style="color:#6B625B">открытка: «{}»</span>', obj.card_text))
        return format_html('<div style="line-height:1.5">{}</div>',
                           mark_safe("<br>".join(rows)))

    @admin.display(description="комментарий")
    def comment_short(self, obj):
        if not obj.comment:
            return format_html('<span style="color:#B5ADA6">—</span>')
        text = obj.comment.strip()
        short = text if len(text) <= 70 else text[:70].rstrip() + "…"
        # the full text is shown as a tooltip: it can be long
        return format_html(
            '<span title="{}" style="display:inline-block;max-width:260px">{}</span>',
            text, short)

    @admin.display(description="")
    def status_badge(self, obj):
        return format_html(
            '<span style="display:inline-block;padding:3px 9px;border-radius:3px;'
            'background:{};color:#fff;font-size:11px">{}</span>',
            STATUS_COLORS.get(obj.status, "#6B625B"),
            obj.get_status_display(),
        )

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        form.instance.recalculate()
