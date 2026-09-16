"""Выгрузка прайса: XLSX для людей и XML для площадок.

XLSX собирается вручную из ZIP с XML внутри — так работает формат Office.
Сделано специально без сторонних библиотек: ставить ничего не нужно,
файл открывается в Excel, LibreOffice и Google Таблицах.
"""

import zipfile
from datetime import datetime
from io import BytesIO
from xml.sax.saxutils import escape

from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from django.views import View

from catalog.facets import FACETS
from catalog.models import Product

# Колонки прайса: сначала общее, потом все характеристики из справочников,
# потом состав, остаток и цена. Добавили справочник в catalog/facets.py —
# в прайсе появилась новая колонка.
BASE_COLUMNS = [("Артикул", 14), ("Название", 46), ("Раздел", 20)]
TAIL_COLUMNS = [
    ("Цветков", 10), ("Состав", 40),
    ("Остаток, шт", 13), ("Цена, ₴", 12), ("Статус", 16),
]


def price_columns():
    middle = [(spec.label, 18) for spec in FACETS]
    return BASE_COLUMNS + middle + TAIL_COLUMNS


def _column_name(index: int) -> str:
    """1 → A, 27 → AA."""
    name = ""
    while index:
        index, rest = divmod(index - 1, 26)
        name = chr(65 + rest) + name
    return name


class XlsxWriter:
    """Минимальный писатель .xlsx: один лист, строки списками значений."""

    def __init__(self, sheet_title: str = "Прайс") -> None:
        self.sheet_title = sheet_title
        self.rows: list[list] = []
        self.widths: list[int] = []

    def set_widths(self, widths: list[int]) -> None:
        self.widths = widths

    def add_row(self, values: list) -> None:
        self.rows.append(values)

    # --- сборка ------------------------------------------------------
    def _cell(self, ref: str, value, bold: bool) -> str:
        style = ' s="1"' if bold else ""
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return f'<c r="{ref}"{style}><v>{value}</v></c>'
        text = escape(str(value if value is not None else ""))
        return (f'<c r="{ref}" t="inlineStr"{style}>'
                f"<is><t xml:space=\"preserve\">{text}</t></is></c>")

    def _sheet_xml(self) -> str:
        cols = ""
        if self.widths:
            items = "".join(
                f'<col min="{i}" max="{i}" width="{w}" customWidth="1"/>'
                for i, w in enumerate(self.widths, start=1)
            )
            cols = f"<cols>{items}</cols>"
        body = []
        for row_index, row in enumerate(self.rows, start=1):
            cells = "".join(
                self._cell(f"{_column_name(i)}{row_index}", value, row_index == 1)
                for i, value in enumerate(row, start=1)
            )
            body.append(f'<row r="{row_index}">{cells}</row>')
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f'{cols}<sheetData>{"".join(body)}</sheetData></worksheet>'
        )

    def build(self) -> bytes:
        buffer = BytesIO()
        title = escape(self.sheet_title)
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("[Content_Types].xml",
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                '<Default Extension="xml" ContentType="application/xml"/>'
                '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
                "</Types>")
            archive.writestr("_rels/.rels",
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
                "</Relationships>")
            archive.writestr("xl/workbook.xml",
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                f'<sheets><sheet name="{title}" sheetId="1" r:id="rId1"/></sheets></workbook>')
            archive.writestr("xl/_rels/workbook.xml.rels",
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
                '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
                "</Relationships>")
            archive.writestr("xl/styles.xml",
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font>'
                '<font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
                '<fills count="2"><fill><patternFill patternType="none"/></fill>'
                '<fill><patternFill patternType="gray125"/></fill></fills>'
                '<borders count="1"><border/></borders>'
                '<cellStyleXfs count="1">'
                '<xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
                '<cellXfs count="2">'
                '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
                '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>'
                '</cellXfs>'
                '<cellStyles count="1">'
                '<cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
                "</styleSheet>")
            archive.writestr("xl/worksheets/sheet1.xml", self._sheet_xml())
        return buffer.getvalue()


def _price_rows():
    """Товары для выгрузки — те же, что видит покупатель."""
    return Product.objects.catalog().order_by("category__position", "article")


class PriceXlsxView(View):
    """Прайс одним файлом .xlsx."""

    def get(self, request, *args, **kwargs):
        columns = price_columns()
        writer = XlsxWriter(f"Прайс {settings.SHOP['NAME']}")
        writer.set_widths([width for _, width in columns])
        writer.add_row([title for title, _ in columns])
        for product in _price_rows():
            writer.add_row([
                product.article,
                product.name,
                product.category.name if product.category else "",
                *[product.attribute_value(spec) for spec in FACETS],
                product.stems or "",
                product.composition,
                product.stock_quantity,
                float(product.price),
                product.status.name if product.status else "",
            ])
        stamp = timezone.localtime().strftime("%Y-%m-%d")
        response = HttpResponse(
            writer.build(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="kvitka-price-{stamp}.xlsx"'
        return response


class PriceXmlView(View):
    """Фид в формате YML — его понимают Пром, Розетка и Google Merchant."""

    def get(self, request, *args, **kwargs):
        shop = settings.SHOP
        base = request.build_absolute_uri("/").rstrip("/")
        now = timezone.localtime().strftime("%Y-%m-%d %H:%M")
        products = list(_price_rows())

        categories, seen = [], {}
        for product in products:
            category = product.category
            if category and category.pk not in seen:
                seen[category.pk] = True
                categories.append(category)

        parts = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<yml_catalog date="{now}"><shop>',
            f"<name>{escape(shop['NAME'])}</name>",
            f"<company>{escape(shop['NAME'])}</company>",
            f"<url>{escape(base)}/</url>",
            f"<currencies><currency id=\"UAH\" rate=\"1\"/></currencies>",
            "<categories>",
        ]
        for category in categories:
            parent = f' parentId="{category.parent_id}"' if category.parent_id else ""
            parts.append(f'<category id="{category.pk}"{parent}>'
                         f"{escape(category.name)}</category>")
        parts.append("</categories><offers>")

        for product in products:
            available = "true" if product.stock_quantity else "false"
            parts.append(f'<offer id="{product.pk}" available="{available}">')
            parts.append(f"<url>{escape(base + product.get_absolute_url())}</url>")
            parts.append(f"<price>{product.price}</price>")
            parts.append("<currencyId>UAH</currencyId>")
            if product.category_id:
                parts.append(f"<categoryId>{product.category_id}</categoryId>")
            if product.has_photo:
                parts.append(f"<picture>{escape(base + product.cover.image.url)}</picture>")
            parts.append(f"<vendor>{escape(shop['NAME'])}</vendor>")
            parts.append(f"<vendorCode>{escape(product.article)}</vendorCode>")
            parts.append(f"<name>{escape(product.title)}</name>")
            parts.append(f"<description>{escape(product.summary_uk or product.summary or product.title)}</description>")
            parts.append(f"<quantity_in_stock>{product.stock_quantity}</quantity_in_stock>")
            if product.stems:
                parts.append(f'<param name="Цветков в букете">{product.stems}</param>')
            if product.composition:
                parts.append(f'<param name="Состав">{escape(product.composition)}</param>')
            # характеристики берём из справочников — по ним же работает подбор
            for spec in FACETS:
                value = product.attribute_value(spec)
                if value:
                    parts.append(f'<param name="{escape(spec.label)}">'
                                 f"{escape(value)}</param>")
            parts.append("</offer>")

        parts.append("</offers></shop></yml_catalog>")
        return HttpResponse("".join(parts), content_type="application/xml; charset=utf-8")
