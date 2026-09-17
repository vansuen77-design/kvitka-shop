"""Catalog sorting: "discount" and "new" are computed on the database side."""

from django.test import TestCase

from catalog.filters import Sorting
from catalog.models import Product
from core.tests.factories import make_product, make_status


class SaleSortingTests(TestCase):
    def setUp(self):
        self.cheap_big_sale = make_product(name="дешёвый −50%", price="50", old_price="100")
        self.pricey_small_sale = make_product(name="дорогой −5%", price="950", old_price="1000")
        self.no_sale = make_product(name="без скидки", price="10")

    def ordered(self, key):
        sorting = Sorting(key)
        queryset = sorting.prepare(Product.objects.published())
        return list(queryset.order_by(*sorting.order_by))

    def test_sale_orders_by_share_not_by_hryvnias(self):
        self.assertEqual(self.ordered("sale")[:2],
                         [self.cheap_big_sale, self.pricey_small_sale])

    def test_sale_annotation_is_not_null(self):
        """Decimal division in SQLite yields NULL — catch the regression."""
        sorting = Sorting("sale")
        rows = sorting.prepare(Product.objects.published()).values_list("discount", flat=True)
        self.assertTrue(all(value is not None for value in rows))

    def test_products_without_discount_go_last(self):
        self.assertEqual(self.ordered("sale")[-1], self.no_sale)

    def test_cheap_and_expensive(self):
        self.assertEqual(self.ordered("cheap")[0], self.no_sale)
        self.assertEqual(self.ordered("expensive")[0], self.pricey_small_sale)


class NewSortingTests(TestCase):
    def test_novinka_status_goes_first(self):
        novinka = make_status("Новинка", slug=Sorting.NEW_STATUS_SLUG)
        old = make_product(name="старый")
        new = make_product(name="новый", status=novinka)
        plain = make_product(name="просто последний")
        sorting = Sorting("new")
        rows = list(sorting.prepare(Product.objects.published()).order_by(*sorting.order_by))
        self.assertEqual(rows[0], new)
        # within — by date added, the last added comes first
        self.assertEqual(rows[1], plain)
        self.assertEqual(rows[2], old)

    def test_novinka_found_by_name_when_slug_differs(self):
        novinka = make_status("Новинка", slug="drugoy-adres")
        new = make_product(status=novinka)
        make_product()
        sorting = Sorting("new")
        rows = list(sorting.prepare(Product.objects.published()).order_by(*sorting.order_by))
        self.assertEqual(rows[0], new)


class SortingKeysTests(TestCase):
    def test_unknown_key_falls_back_to_default(self):
        self.assertEqual(Sorting("nonsense").key, Sorting.DEFAULT)
        self.assertEqual(Sorting(None).key, Sorting.DEFAULT)

    def test_created_at_always_last(self):
        for key in Sorting.OPTIONS:
            self.assertEqual(Sorting(key).order_by[-1], "-created_at")

    def test_choices_mark_selected(self):
        choices = Sorting("cheap").as_choices()
        selected = [c["key"] for c in choices if c["selected"]]
        self.assertEqual(selected, ["cheap"])
