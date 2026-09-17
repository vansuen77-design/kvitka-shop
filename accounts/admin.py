"""Customers in the admin.

No separate section: the profile is shown right inside the user account,
next to the name and e-mail.

Inherits from SingleAdminUserAdmin in core rather than the stock UserAdmin:
the accounts app registers after core and overrides its setup, and the
"last administrator cannot be deleted" guard must survive. In the
original template it was lost here.
"""

from django.contrib import admin
from django.contrib.auth.models import User

from accounts.models import Favorite, Profile
from core.admin import SingleAdminUserAdmin


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = "анкета покупателя"
    fields = ("phone", "address", "preferred_contact")


class UserAdmin(SingleAdminUserAdmin):
    inlines = [ProfileInline]
    list_display = ("username", "first_name", "email", "phone", "is_active", "date_joined")
    list_filter = ("is_active", "is_staff", "date_joined")
    ordering = ("-date_joined",)

    @admin.display(description="телефон")
    def phone(self, obj):
        profile = getattr(obj, "profile", None)
        return profile.phone if profile else "—"


admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ("user", "product", "created_at")
    list_select_related = ("user", "product")
    search_fields = ("user__username", "product__article", "product__name")
