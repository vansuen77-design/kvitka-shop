"""Менеджеры и QuerySet каталога — вся логика выборок собрана здесь,
чтобы представления оставались тонкими."""

from django.db import models
from django.db.models import Exists, F, OuterRef, Q

from core.models import ActivatableQuerySet

# Связи, которые каталог подтягивает одним запросом. FK — в select_related,
# множественные справочники и фото — в prefetch. Новый справочник из
# catalog/facets.py надо дописать сюда, иначе плитка пойдёт в базу за
# каждым товаром отдельно.
RELATED = ("category", "status", "kind", "color", "size")
PREFETCH = ("images", "flowers", "occasions")


class CategoryQuerySet(ActivatableQuerySet):
    """Выборки разделов каталога."""

    def nonempty(self) -> "CategoryQuerySet":
        """Только разделы, в которых есть что показать.

        Пустой раздел в меню — обещание, которого витрина не выполняет:
        человек заходит и видит голую страницу. Раньше такие разделы
        приходилось прятать галочкой в админке и не забывать вернуть её,
        когда товар приедет. Теперь раздел исчезает и возвращается сам.

        Считаем товары и в самом разделе, и в его подразделах: у
        «Женского белья» своих товаров нет, они лежат в «Трусах женских»,
        и без второй проверки родитель пропал бы вместе с ними.

        Exists вместо join с distinct: join размножает строки по числу
        товаров, а distinct в SQLite не дружит с сортировкой по полю,
        которого нет в выборке.

        Импорт внутри метода намеренно: models.py подтягивает этот файл,
        и обратная ссылка наверху превратилась бы в кольцо импортов.
        """
        from catalog.models import Product

        here = Product.objects.filter(is_active=True, category=OuterRef("pk"))
        inside = Product.objects.filter(is_active=True, category__parent=OuterRef("pk"))
        return self.filter(Exists(here) | Exists(inside))


class ProductQuerySet(ActivatableQuerySet):
    """Выборки товаров. Каждый метод возвращает новый QuerySet,
    поэтому их можно соединять в цепочку."""

    def published(self) -> "ProductQuerySet":
        return self.active()

    def with_relations(self) -> "ProductQuerySet":
        return self.select_related(*RELATED).prefetch_related(*PREFETCH)

    # --- фильтры ---------------------------------------------------------
    def in_category(self, slug: str) -> "ProductQuerySet":
        return self.filter(Q(category__slug=slug) | Q(category__parent__slug=slug))

    def in_stock(self) -> "ProductQuerySet":
        return self.filter(stock_quantity__gt=0)

    def with_discount(self) -> "ProductQuerySet":
        """Только товары со скидкой — для кнопки «Акции» в шапке.

        Признак тот же, что показывает зачёркнутую цену на карточке
        (свойство Product.has_discount): старая цена заполнена и выше
        текущей. Считать здесь по-своему нельзя — «Акции» и плашка
        «−5 %» разъехались бы, и покупатель увидел бы в акциях товар
        без скидки.
        """
        return self.filter(old_price__isnull=False, old_price__gt=F("price"))

    def with_status(self, slugs) -> "ProductQuerySet":
        return self.filter(status__slug__in=list(slugs))

    def with_attribute(self, lookup: str, slugs, multiple: bool = False):
        """Фильтр по любому справочнику подбора.

        Отдельного метода на каждую характеристику нет специально: все
        они фильтруются одинаково — по адресу значения.
        Какие вообще бывают, описано в catalog/facets.py.
        """
        queryset = self.filter(**{lookup: list(slugs)})
        return queryset.distinct() if multiple else queryset

    def availability(self, values) -> "ProductQuerySet":
        """«В наличии» / «Нет в наличии» — считаем по остатку."""
        values = set(values)
        if values == {"in"}:
            return self.filter(stock_quantity__gt=0)
        if values == {"out"}:
            return self.filter(stock_quantity=0)
        return self

    def price_between(self, low=None, high=None) -> "ProductQuerySet":
        qs = self
        if low is not None:
            qs = qs.filter(price__gte=low)
        if high is not None:
            qs = qs.filter(price__lte=high)
        return qs

    def search(self, term: str) -> "ProductQuerySet":
        term = (term or "").strip()
        if not term:
            return self
        # LIKE в SQLite не различает регистр только у латиницы (грабля 19):
        # «роза» и «Роза» — разные строки. Поэтому ищем и как ввели, и
        # с заглавной, и целиком строчными — по русскому и украинскому
        # названию, артикулу, составу и цветку.
        variants = {term, term.lower(), term.capitalize()}
        query = Q()
        for word in variants:
            query |= (
                Q(name__contains=word)
                | Q(name_uk__contains=word)
                | Q(article__icontains=word)
                | Q(composition__contains=word)
                | Q(composition_uk__contains=word)
                | Q(flowers__name__contains=word)
                | Q(flowers__name_uk__contains=word)
            )
        return self.filter(query).distinct()


class ProductManager(models.Manager.from_queryset(ProductQuerySet)):
    """Менеджер по умолчанию: сразу отдаёт готовый к выводу набор."""

    def catalog(self) -> ProductQuerySet:
        return self.get_queryset().published().with_relations()
