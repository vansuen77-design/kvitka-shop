from django.apps import AppConfig


class CatalogConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "catalog"
    verbose_name = "Каталог"

    def ready(self):
        # подключаем снятие товаров с публикации при удалении справочника
        from catalog import signals  # noqa: F401
