"""Варианты одного букета: семейство family и переключатель размера."""

from django.test import TestCase

from core.tests.factories import Size, make_product, make_value


class VariantsTests(TestCase):
    def setUp(self):
        self.s = make_value(Size, "Малый", slug="s", position=10, name_uk="Малий")
        self.m = make_value(Size, "Средний", slug="m", position=20, name_uk="Середній")
        self.l = make_value(Size, "Большой", slug="l", position=30, name_uk="Великий")
        # заводим нарочно не по порядку — переключатель должен отсортировать сам
        self.big = make_product(name="51", family="rozy", size=self.l, stems=51, price="3000")
        self.small = make_product(name="11", family="rozy", size=self.s, stems=11, price="800")
        self.mid = make_product(name="25", family="rozy", size=self.m, stems=25, price="1800")

    def test_variants_ordered_by_size_position(self):
        self.assertEqual(list(self.mid.variants()), [self.small, self.mid, self.big])

    def test_variants_exclude_hidden(self):
        self.big.is_active = False
        self.big.save()
        self.assertEqual(list(self.small.variants()), [self.small, self.mid])

    def test_no_family_means_no_variants(self):
        alone = make_product(name="один")
        self.assertEqual(list(alone.variants()), [])

    def test_variant_label_prefers_stems(self):
        self.assertEqual(self.small.variant_label, "11 шт")
        no_stems = make_product(size=self.m, stems=0)
        self.assertEqual(no_stems.variant_label, self.m.title)

    def test_product_page_shows_switcher(self):
        response = self.client.get(self.mid.get_absolute_url())
        self.assertContains(response, 'class="variants"')
        self.assertContains(response, self.small.get_absolute_url())
        self.assertContains(response, self.big.get_absolute_url())
        # текущий вариант — не ссылка
        self.assertContains(response, 'aria-current="page"')

    def test_single_member_family_has_no_switcher(self):
        lonely = make_product(name="одинокий", family="tulpany")
        response = self.client.get(lonely.get_absolute_url())
        self.assertNotContains(response, 'class="variants"')
        self.assertEqual(response.context["variants"], [])

    def test_related_excludes_family(self):
        response = self.client.get(self.mid.get_absolute_url())
        self.assertNotIn(self.small, list(response.context["related"]))
