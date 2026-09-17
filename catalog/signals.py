"""Unpublishing products when an attribute value is deleted."""

from django.db.models.signals import pre_delete
from django.dispatch import receiver

from catalog.deletion import is_reference, unpublish_products


@receiver(pre_delete)
def unpublish_on_reference_delete(sender, instance, **kwargs) -> None:
    """Before a reference value is deleted, hide its products.

    pre_delete specifically: after deletion the link is already gone
    (SET_NULL) and the affected products can no longer be found.
    """
    if is_reference(instance):
        unpublish_products(instance)
