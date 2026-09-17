"""The XLSX price list and the XML feed are built without third-party libraries."""

import zipfile
from io import BytesIO

from django.conf import settings
from django.test import TestCase

from catalog.facets import FACETS
from core.tests.factories import Flower, make_category, make_product, make_value


class ExportTests(TestCase):
    def setUp(self):
        roza = make_value(Flower, "Роза", name_uk="Троянда")
        self.product = make_product(name="Розы", name_uk="Троянди", article="X-1",
                                    category=make_category("Букеты"), flowers=[roza],
                                    stems=11, composition="11 роз")
        make_product(name="скрытый", is_active=False)

    def test_xlsx_is_valid_zip_with_sheet(self):
        response = self.client.get("/price/xlsx/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("kvitka-price-", response["Content-Disposition"])
        archive = zipfile.ZipFile(BytesIO(response.content))
        sheet = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
        self.assertIn("X-1", sheet)
        self.assertIn("Троянда", sheet)
        self.assertNotIn("скрытый", sheet)
        # one column per reference model from the registry
        for spec in FACETS:
            self.assertIn(spec.label, sheet)

    def test_xml_feed(self):
        response = self.client.get("/price/xml/")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        self.assertIn("<yml_catalog", body)
        self.assertIn("<name>Троянди</name>", body)
        self.assertIn(f"<vendor>{settings.SHOP['NAME']}</vendor>", body)
        self.assertIn('<param name="Цветков в букете">11</param>', body)
        self.assertNotIn("скрытый", body)
