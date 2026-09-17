"""Seed commands: empty database → working catalog, re-running is safe."""

from io import StringIO
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase, override_settings

from catalog.facets import FACETS
from catalog.filters import Sorting
from catalog.models import Category, FacetGroup, Product, Status


class SeedTests(TestCase):
    def setUp(self):
        self.media = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.media.cleanup()

    def test_seed_everything_twice(self):
        with override_settings(MEDIA_ROOT=Path(self.media.name)):
            call_command("seed_facets", stdout=StringIO())
            call_command("seed_pages", stdout=StringIO())
            call_command("seed_catalog", stdout=StringIO())
            products = Product.objects.count()
            self.assertGreater(products, 0)
            # every demo product got an image and a Ukrainian name
            for product in Product.objects.all():
                self.assertTrue(product.has_photo, product.article)
                self.assertTrue(product.name_uk, product.article)
                self.assertTrue((Path(self.media.name) / product.cover.image.name).exists())
            # the "New" status — by the slug that sorting looks for
            self.assertTrue(Status.objects.filter(slug=Sorting.NEW_STATUS_SLUG).exists())
            self.assertEqual(FacetGroup.objects.count(), len(FACETS))
            self.assertTrue(Category.objects.filter(parent__isnull=False).exists())

            call_command("seed_catalog", stdout=StringIO())
            call_command("seed_facets", stdout=StringIO())
            self.assertEqual(Product.objects.count(), products)

    def test_catalog_renders_after_seed(self):
        with override_settings(MEDIA_ROOT=Path(self.media.name)):
            call_command("seed_facets", stdout=StringIO())
            call_command("seed_catalog", stdout=StringIO())
            response = self.client.get("/")
            self.assertEqual(response.status_code, 200)
            # families have a switcher
            family = Product.objects.exclude(family="").first()
            self.assertContains(self.client.get(family.get_absolute_url()), 'class="variants"')
