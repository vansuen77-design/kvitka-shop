"""Product.normalize_quantity — единственное место, где решается количество."""

from django.test import TestCase

from core.tests.factories import make_product, make_status


class NormalizeQuantityTests(TestCase):
    def setUp(self):
        self.product = make_product(stock=7)

    def test_within_stock_stays(self):
        self.assertEqual(self.product.normalize_quantity(3), 3)

    def test_above_stock_is_cut_to_stock(self):
        self.assertEqual(self.product.normalize_quantity(999), 7)

    def test_zero_and_negative_mean_remove(self):
        self.assertEqual(self.product.normalize_quantity(0), 0)
        self.assertEqual(self.product.normalize_quantity(-5), 0)

    def test_garbage_is_zero(self):
        self.assertEqual(self.product.normalize_quantity("abc"), 0)
        self.assertEqual(self.product.normalize_quantity(None), 0)

    def test_string_number_is_accepted(self):
        self.assertEqual(self.product.normalize_quantity("2"), 2)

    def test_empty_stock_gives_zero(self):
        empty = make_product(stock=0)
        self.assertEqual(empty.normalize_quantity(1), 0)

    def test_minimum_is_one(self):
        self.assertEqual(self.product.minimum_quantity, 1)


class OrderableTests(TestCase):
    def test_status_blocks_ordering(self):
        gone = make_status("Снят с продажи", orderable=False)
        product = make_product(stock=5, status=gone)
        self.assertFalse(product.is_orderable)
        self.assertEqual(product.stock_label, gone.title)

    def test_no_stock_blocks_ordering(self):
        product = make_product(stock=0)
        self.assertFalse(product.is_orderable)
        self.assertEqual(product.stock_state, "out")

    def test_low_stock_state(self):
        self.assertEqual(make_product(stock=2).stock_state, "low")
        self.assertEqual(make_product(stock=20).stock_state, "ok")


class DiscountTests(TestCase):
    def test_discount_only_when_old_price_higher(self):
        self.assertTrue(make_product(price="100", old_price="150").has_discount)
        self.assertFalse(make_product(price="100", old_price="100").has_discount)
        self.assertFalse(make_product(price="100", old_price="90").has_discount)
        self.assertFalse(make_product(price="100").has_discount)

    def test_percent_rounds_and_hides_zero(self):
        self.assertEqual(make_product(price="75", old_price="100").discount_percent, 25)
        self.assertEqual(make_product(price="999.8", old_price="1000").discount_percent, 0)
        self.assertEqual(make_product(price="100").discount_percent, 0)
