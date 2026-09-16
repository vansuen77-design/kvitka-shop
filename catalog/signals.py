"""Снятие товаров с публикации при удалении характеристики."""

from django.db.models.signals import pre_delete
from django.dispatch import receiver

from catalog.deletion import is_reference, unpublish_products


@receiver(pre_delete)
def unpublish_on_reference_delete(sender, instance, **kwargs) -> None:
    """Перед удалением значения справочника прячем его товары.

    Именно pre_delete: после удаления связь уже разорвана (SET_NULL),
    и найти пострадавшие товары будет нельзя.
    """
    if is_reference(instance):
        unpublish_products(instance)
