from django.apps import AppConfig


class CatalogConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "catalog"
    verbose_name = "Каталог"

    def ready(self):
        # wire up unpublishing of products when a reference value is deleted
        from catalog import signals  # noqa: F401
