"""Правка стандартных разделов админки.

Учётная запись администратора в проекте должна быть ровно одна: пока
суперпользователь существует, кнопка «Добавить» в разделе «Пользователи»
не показывается, а последнего администратора нельзя удалить или снять
с него права — иначе в админку никто не войдёт.
"""

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

User = get_user_model()


def superuser_count(exclude_pk=None) -> int:
    queryset = User.objects.filter(is_superuser=True, is_active=True)
    if exclude_pk is not None:
        queryset = queryset.exclude(pk=exclude_pk)
    return queryset.count()


class SingleAdminUserAdmin(DjangoUserAdmin):
    """Пользователь может быть только один — тот, что уже создан."""

    def has_add_permission(self, request) -> bool:
        return superuser_count() == 0

    def has_delete_permission(self, request, obj=None) -> bool:
        if obj is not None and obj.is_superuser and superuser_count(obj.pk) == 0:
            return False
        return super().has_delete_permission(request, obj)

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        # последнему администратору нельзя снять права — заблокируем сам чекбокс
        if obj is not None and obj.is_superuser and superuser_count(obj.pk) == 0:
            fields += ["is_superuser", "is_staff", "is_active"]
        return fields

    def get_deleted_objects(self, objs, request):
        deletable, model_count, perms_needed, protected = super().get_deleted_objects(
            objs, request
        )
        remaining = superuser_count()
        losing = sum(1 for obj in objs if obj.is_superuser and obj.is_active)
        if losing and remaining - losing < 1:
            perms_needed = set(perms_needed) | {"последний администратор"}
        return deletable, model_count, perms_needed, protected


admin.site.unregister(User)
admin.site.register(User, SingleAdminUserAdmin)
