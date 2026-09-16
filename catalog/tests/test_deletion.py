"""Удаление справочника снимает товары с публикации, а не стирает их."""

from django.test import TestCase

from catalog.deletion import describe
from catalog.models import Product
from core.tests.factories import Flower, Kind, make_category, make_product, make_status, make_value


class UnpublishOnDeleteTests(TestCase):
    def test_deleting_fk_value_unpublishes(self):
        kind = make_value(Kind, "Букет")
        product = make_product(kind=kind)
        other = make_product()
        kind.delete()
        product.refresh_from_db()
        other.refresh_from_db()
        self.assertFalse(product.is_active)
        self.assertIsNone(product.kind)
        self.assertTrue(other.is_active)
        self.assertEqual(Product.objects.count(), 2)

    def test_deleting_m2m_value_unpublishes(self):
        roza = make_value(Flower, "Роза")
        product = make_product(flowers=[roza])
        roza.delete()
        product.refresh_from_db()
        self.assertFalse(product.is_active)

    def test_deleting_category_unpublishes_children_products(self):
        root = make_category("Букеты")
        child = make_category("Розы", parent=root)
        product = make_product(category=child)
        root.delete()
        product.refresh_from_db()
        self.assertFalse(product.is_active)

    def test_deleting_status_unpublishes(self):
        status = make_status("Новинка")
        product = make_product(status=status)
        status.delete()
        product.refresh_from_db()
        self.assertFalse(product.is_active)

    def test_describe_counts_published(self):
        kind = make_value(Kind, "Букет")
        make_product(kind=kind)
        make_product(kind=kind, is_active=False)
        info = describe(kind)
        self.assertEqual(info["total"], 2)
        self.assertEqual(info["published"], 1)
        self.assertIsNone(describe(make_value(Kind, "пустой")))
