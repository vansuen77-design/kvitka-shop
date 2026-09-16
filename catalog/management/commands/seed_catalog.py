"""Первичное наполнение каталога:

    python manage.py seed_catalog          # добавить недостающее
    python manage.py seed_catalog --reset  # пересоздать товары

Создаёт статусы, разделы, справочники подбора и демонстрационные
букеты с картинками-заглушками (catalog/placeholders.py). Названия
и значения справочников — сразу на двух языках: русское для админки,
украинское для витрины (Product.title всегда украинский).

Владелец заменяет демо-товары своими в админке; команда безопасна для
повторного запуска — то, что уже есть, не трогает.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from catalog import placeholders
from catalog.models import (
    Category, Color, Flower, Kind, Occasion, Product, ProductImage, Size, Status,
)

# (русское имя, украинское имя, цвет плашки, можно заказать, пояснение)
STATUSES = [
    ("В наличии", "В наявності", "#4F7A4B", True, "соберём за час"),
    ("Новинка", "Новинка", "#B23A5E", True, ""),
    ("Под заказ", "Під замовлення", "#8E8085", True, "привезём за 1–2 дня"),
    ("Снят с продажи", "Знято з продажу", "#8C8079", False, "сезон закончился"),
]

# Адрес статуса «Новинка» задаётся явно: по нему ищут сортировка
# и баннер (Sorting.NEW_STATUS_SLUG). Остальные — по названию.
STATUS_SLUGS = {"Новинка": "novinka"}

# (русское имя, украинское имя, адрес, подразделы)
CATEGORIES = [
    ("Букеты", "Букети", "bukety", [
        ("Розы", "Троянди", "rozy"),
        ("Тюльпаны", "Тюльпани", "tyulpany"),
        ("Пионы", "Півонії", "piony"),
        ("Сборные букеты", "Збірні букети", "sbornye-bukety"),
    ]),
    ("Композиции", "Композиції", "kompozitsii", [
        ("Цветы в коробке", "Квіти в коробці", "v-korobke"),
        ("Цветы в корзине", "Квіти в кошику", "v-korzine"),
    ]),
    ("Растения в горшках", "Рослини в горщиках", "rasteniya", []),
]

# Справочники подбора: (русское, украинское, адрес). Адреса заданы явно,
# чтобы ссылки вида ?flower=roza не зависели от транслитерации.
ATTRIBUTES = {
    Kind: [
        ("Букет", "Букет", "buket"),
        ("Композиция в коробке", "Композиція в коробці", "korobka"),
        ("Композиция в корзине", "Композиція в кошику", "korzina"),
        ("Растение в горшке", "Рослина в горщику", "gorshok"),
    ],
    Flower: [
        ("Роза", "Троянда", "roza"),
        ("Тюльпан", "Тюльпан", "tyulpan"),
        ("Пион", "Півонія", "pion"),
        ("Хризантема", "Хризантема", "hrizantema"),
        ("Эустома", "Еустома", "eustoma"),
        ("Гербера", "Гербера", "gerbera"),
        ("Гортензия", "Гортензія", "gortenziya"),
        ("Орхидея", "Орхідея", "orhideya"),
        ("Эвкалипт", "Евкаліпт", "evkalipt"),
    ],
    Occasion: [
        ("День рождения", "День народження", "den-rozhdeniya"),
        ("Признание в любви", "Освідчення в коханні", "lyubov"),
        ("Свадьба", "Весілля", "svadba"),
        ("8 Марта", "8 Березня", "8-marta"),
        ("Юбилей", "Ювілей", "yubiley"),
        ("Без повода", "Без приводу", "bez-povoda"),
        ("Соболезнование", "Співчуття", "soboleznovanie"),
    ],
    Color: [
        ("Красный", "Червоний", "red"),
        ("Розовый", "Рожевий", "pink"),
        ("Белый", "Білий", "white"),
        ("Жёлтый", "Жовтий", "yellow"),
        ("Фиолетовый", "Фіолетовий", "purple"),
        ("Микс", "Мікс", "mix"),
        ("Зелёный", "Зелений", "green"),
    ],
    Size: [
        ("Малый (S)", "Малий (S)", "s"),
        ("Средний (M)", "Середній (M)", "m"),
        ("Большой (L)", "Великий (L)", "l"),
        ("Огромный (XL)", "Величезний (XL)", "xl"),
    ],
}

# Товары. Семейство family связывает варианты одного букета — у них
# общий переключатель размера на странице товара.
PRODUCTS = [
    # --- розы: три размера одного букета ----------------------------------
    {
        "article": "R-11", "name": "Букет из 11 красных роз", "name_uk": "Букет з 11 червоних троянд",
        "category": "rozy", "kind": "buket", "flowers": ["roza"], "occasions": ["lyubov", "den-rozhdeniya"],
        "color": "red", "size": "s", "family": "rozy-krasnye", "stems": 11, "height": 60,
        "price": 890, "stock": 12, "status": "В наличии",
        "summary": "Классика, которая не подводит", "summary_uk": "Класика, яка не підводить",
        "composition": "11 роз Freedom 60 см, крафт-упаковка, атласная лента",
        "composition_uk": "11 троянд Freedom 60 см, крафт-упаковка, атласна стрічка",
        "description": "Бордовые розы Freedom с плотным бутоном — стоят в вазе до десяти дней. Собираем в крафт и перевязываем лентой.",
        "description_uk": "Бордові троянди Freedom зі щільним бутоном — стоять у вазі до десяти днів. Збираємо в крафт і перев'язуємо стрічкою.",
    },
    {
        "article": "R-25", "name": "Букет из 25 красных роз", "name_uk": "Букет з 25 червоних троянд",
        "category": "rozy", "kind": "buket", "flowers": ["roza"], "occasions": ["lyubov", "yubiley"],
        "color": "red", "size": "m", "family": "rozy-krasnye", "stems": 25, "height": 60,
        "price": 1850, "old_price": 2050, "stock": 6, "status": "В наличии",
        "summary": "Пышный букет на серьёзный повод", "summary_uk": "Пишний букет на серйозний привід",
        "composition": "25 роз Freedom 60 см, крафт-упаковка, атласная лента",
        "composition_uk": "25 троянд Freedom 60 см, крафт-упаковка, атласна стрічка",
        "description": "Тот же сорт Freedom, только вдвое больше. Плотная охапка держит форму сама, без каркаса.",
        "description_uk": "Той самий сорт Freedom, тільки вдвічі більше. Щільний оберемок тримає форму сам, без каркаса.",
    },
    {
        "article": "R-51", "name": "Букет из 51 красной розы", "name_uk": "Букет з 51 червоної троянди",
        "category": "rozy", "kind": "buket", "flowers": ["roza"], "occasions": ["lyubov", "yubiley", "svadba"],
        "color": "red", "size": "l", "family": "rozy-krasnye", "stems": 51, "height": 60,
        "price": 3600, "stock": 2, "status": "Под заказ",
        "summary": "Охапка, которую видно из другого конца улицы", "summary_uk": "Оберемок, який видно з іншого кінця вулиці",
        "composition": "51 роза Freedom 60 см, дизайнерская упаковка, лента",
        "composition_uk": "51 троянда Freedom 60 см, дизайнерська упаковка, стрічка",
        "description": "Собираем под заказ: нужно время, чтобы отобрать полсотни одинаковых бутонов. Подтверждаем по телефону.",
        "description_uk": "Збираємо під замовлення: потрібен час, щоб відібрати півсотні однакових бутонів. Підтверджуємо телефоном.",
    },
    {
        "article": "R-P15", "name": "Букет из 15 розовых роз", "name_uk": "Букет з 15 рожевих троянд",
        "category": "rozy", "kind": "buket", "flowers": ["roza", "evkalipt"], "occasions": ["den-rozhdeniya", "bez-povoda"],
        "color": "pink", "size": "m", "stems": 15, "height": 50,
        "price": 1150, "stock": 8, "status": "Новинка",
        "summary": "Нежные розы с эвкалиптом", "summary_uk": "Ніжні троянди з евкаліптом",
        "composition": "15 роз Pink Mondial 50 см, эвкалипт, матовая плёнка",
        "composition_uk": "15 троянд Pink Mondial 50 см, евкаліпт, матова плівка",
        "description": "Пудрово-розовый сорт с крупным бутоном и ветки эвкалипта для объёма и запаха.",
        "description_uk": "Пудрово-рожевий сорт із великим бутоном і гілки евкаліпта для об'єму та запаху.",
    },
    # --- тюльпаны ---------------------------------------------------------
    {
        "article": "T-25", "name": "25 тюльпанов микс", "name_uk": "25 тюльпанів мікс",
        "category": "tyulpany", "kind": "buket", "flowers": ["tyulpan"], "occasions": ["8-marta", "bez-povoda"],
        "color": "mix", "size": "m", "family": "tyulpany-mix", "stems": 25, "height": 40,
        "price": 750, "stock": 20, "status": "В наличии",
        "summary": "Весна в одной охапке", "summary_uk": "Весна в одному оберемку",
        "composition": "25 тюльпанов разных цветов, крафт-упаковка",
        "composition_uk": "25 тюльпанів різних кольорів, крафт-упаковка",
        "description": "Красные, жёлтые, розовые и белые тюльпаны в одном букете. Собираем из того, что привезли утром.",
        "description_uk": "Червоні, жовті, рожеві та білі тюльпани в одному букеті. Збираємо з того, що привезли вранці.",
    },
    {
        "article": "T-51", "name": "51 тюльпан микс", "name_uk": "51 тюльпан мікс",
        "category": "tyulpany", "kind": "buket", "flowers": ["tyulpan"], "occasions": ["8-marta", "yubiley"],
        "color": "mix", "size": "l", "family": "tyulpany-mix", "stems": 51, "height": 40,
        "price": 1400, "stock": 5, "status": "В наличии",
        "summary": "Большая весенняя охапка", "summary_uk": "Великий весняний оберемок",
        "composition": "51 тюльпан разных цветов, крафт-упаковка, лента",
        "composition_uk": "51 тюльпан різних кольорів, крафт-упаковка, стрічка",
        "description": "Та же охапка вдвое больше — на праздник в офис или большой юбилей.",
        "description_uk": "Той самий оберемок удвічі більший — на свято в офіс або великий ювілей.",
    },
    {
        "article": "T-W19", "name": "19 белых тюльпанов", "name_uk": "19 білих тюльпанів",
        "category": "tyulpany", "kind": "buket", "flowers": ["tyulpan"], "occasions": ["svadba", "8-marta"],
        "color": "white", "size": "s", "stems": 19, "height": 40,
        "price": 620, "stock": 0, "status": "В наличии",
        "summary": "Строгий белый монобукет", "summary_uk": "Строгий білий монобукет",
        "composition": "19 белых тюльпанов, белая матовая плёнка",
        "composition_uk": "19 білих тюльпанів, біла матова плівка",
        "description": "Белые тюльпаны в белой упаковке — на свадьбу, крестины или просто так.",
        "description_uk": "Білі тюльпани в білій упаковці — на весілля, хрестини або просто так.",
    },
    # --- пионы ------------------------------------------------------------
    {
        "article": "P-7", "name": "7 розовых пионов", "name_uk": "7 рожевих півоній",
        "category": "piony", "kind": "buket", "flowers": ["pion"], "occasions": ["den-rozhdeniya", "lyubov"],
        "color": "pink", "size": "s", "stems": 7, "height": 45,
        "price": 1250, "stock": 4, "status": "Новинка",
        "summary": "Сезонные пионы Sarah Bernhardt", "summary_uk": "Сезонні півонії Sarah Bernhardt",
        "composition": "7 пионов Sarah Bernhardt, крафт-упаковка",
        "composition_uk": "7 півоній Sarah Bernhardt, крафт-упаковка",
        "description": "Пионы — цветок на месяц в году. Раскрываются в вазе за пару дней и пахнут на всю комнату.",
        "description_uk": "Півонії — квітка на місяць у році. Розкриваються у вазі за пару днів і пахнуть на всю кімнату.",
    },
    # --- сборные ----------------------------------------------------------
    {
        "article": "M-1", "name": "Букет «Утро в саду»", "name_uk": "Букет «Ранок у саду»",
        "category": "sbornye-bukety", "kind": "buket", "flowers": ["roza", "eustoma", "evkalipt", "gortenziya"],
        "occasions": ["den-rozhdeniya", "bez-povoda", "yubiley"],
        "color": "mix", "size": "m", "stems": 21, "height": 50,
        "price": 1650, "stock": 3, "status": "В наличии",
        "summary": "Авторский букет флориста", "summary_uk": "Авторський букет флориста",
        "composition": "Кустовые розы, эустома, гортензия, эвкалипт, дизайнерская упаковка",
        "composition_uk": "Кущові троянди, еустома, гортензія, евкаліпт, дизайнерська упаковка",
        "description": "Собираем из того, что лучше всего выглядит сегодня. Состав может немного отличаться от фото — гамма и объём сохраняются.",
        "description_uk": "Збираємо з того, що найкраще виглядає сьогодні. Склад може трохи відрізнятися від фото — гама й об'єм зберігаються.",
    },
    {
        "article": "M-2", "name": "Букет «Солнечный»", "name_uk": "Букет «Сонячний»",
        "category": "sbornye-bukety", "kind": "buket", "flowers": ["gerbera", "hrizantema", "tyulpan"],
        "occasions": ["den-rozhdeniya", "bez-povoda"],
        "color": "yellow", "size": "s", "stems": 15, "height": 45,
        "price": 780, "old_price": 890, "stock": 7, "status": "В наличии",
        "summary": "Жёлтые герберы и хризантемы", "summary_uk": "Жовті гербери та хризантеми",
        "composition": "Герберы, кустовая хризантема, жёлтые тюльпаны, крафт",
        "composition_uk": "Гербери, кущова хризантема, жовті тюльпани, крафт",
        "description": "Яркий и стойкий: герберы и хризантемы стоят до двух недель.",
        "description_uk": "Яскравий і стійкий: гербери та хризантеми стоять до двох тижнів.",
    },
    {
        "article": "M-3", "name": "Траурный букет из белых хризантем", "name_uk": "Жалобний букет із білих хризантем",
        "category": "sbornye-bukety", "kind": "buket", "flowers": ["hrizantema"], "occasions": ["soboleznovanie"],
        "color": "white", "size": "m", "stems": 12, "height": 60,
        "price": 900, "stock": 5, "status": "В наличии",
        "summary": "Сдержанный букет без упаковки", "summary_uk": "Стриманий букет без упаковки",
        "composition": "12 одноголовых белых хризантем, зелень, лента",
        "composition_uk": "12 одноголових білих хризантем, зелень, стрічка",
        "description": "Чётное число цветов, без яркой упаковки. Доставим к назначенному времени.",
        "description_uk": "Парна кількість квітів, без яскравої упаковки. Доставимо на призначений час.",
    },
    # --- композиции -------------------------------------------------------
    {
        "article": "K-1", "name": "Розы в шляпной коробке", "name_uk": "Троянди в капелюшній коробці",
        "category": "v-korobke", "kind": "korobka", "flowers": ["roza", "evkalipt"], "occasions": ["lyubov", "den-rozhdeniya", "yubiley"],
        "color": "pink", "size": "m", "stems": 19,
        "price": 1950, "stock": 4, "status": "В наличии",
        "summary": "Не нужна ваза — стоит на флористической губке", "summary_uk": "Не потрібна ваза — стоїть на флористичній губці",
        "composition": "19 роз, эвкалипт, шляпная коробка 20 см, губка с водой",
        "composition_uk": "19 троянд, евкаліпт, капелюшна коробка 20 см, губка з водою",
        "description": "Композицию нужно только поливать раз в два дня. Коробка остаётся на память.",
        "description_uk": "Композицію потрібно лише поливати раз на два дні. Коробка залишається на пам'ять.",
    },
    {
        "article": "K-2", "name": "Корзина «Летний луг»", "name_uk": "Кошик «Літній луг»",
        "category": "v-korzine", "kind": "korzina", "flowers": ["gerbera", "hrizantema", "eustoma", "evkalipt"],
        "occasions": ["yubiley", "den-rozhdeniya"],
        "color": "mix", "size": "l", "stems": 35,
        "price": 2400, "stock": 2, "status": "Под заказ",
        "summary": "Большая корзина на юбилей или в офис", "summary_uk": "Великий кошик на ювілей або в офіс",
        "composition": "Герберы, хризантемы, эустома, зелень, плетёная корзина 35 см",
        "composition_uk": "Гербери, хризантеми, еустома, зелень, плетений кошик 35 см",
        "description": "Собираем под заказ за день. Ставится на стол и стоит без ухода до недели.",
        "description_uk": "Збираємо під замовлення за день. Ставиться на стіл і стоїть без догляду до тижня.",
    },
    # --- растения ---------------------------------------------------------
    {
        "article": "G-1", "name": "Орхидея фаленопсис, 2 ветки", "name_uk": "Орхідея фаленопсис, 2 гілки",
        "category": "rasteniya", "kind": "gorshok", "flowers": ["orhideya"], "occasions": ["den-rozhdeniya", "bez-povoda"],
        "color": "white", "height": 60,
        "price": 850, "stock": 6, "status": "В наличии",
        "summary": "Цветёт до трёх месяцев", "summary_uk": "Цвіте до трьох місяців",
        "composition": "Орхидея фаленопсис в горшке 12 см, кашпо в подарок",
        "composition_uk": "Орхідея фаленопсис у горщику 12 см, кашпо в подарунок",
        "description": "Белая орхидея на двух цветоносах. Поливать раз в неделю, держать подальше от батареи.",
        "description_uk": "Біла орхідея на двох квітконосах. Поливати раз на тиждень, тримати подалі від батареї.",
    },
    {
        "article": "G-2", "name": "Гортензия в горшке", "name_uk": "Гортензія в горщику",
        "category": "rasteniya", "kind": "gorshok", "flowers": ["gortenziya"], "occasions": ["bez-povoda"],
        "color": "purple", "height": 40,
        "price": 620, "stock": 3, "status": "В наличии",
        "summary": "Пышные шапки соцветий", "summary_uk": "Пишні шапки суцвіть",
        "composition": "Гортензия крупнолистная в горшке 14 см",
        "composition_uk": "Гортензія великолиста в горщику 14 см",
        "description": "Летом можно высадить в сад — будет цвести каждый год.",
        "description_uk": "Влітку можна висадити в сад — цвістиме щороку.",
    },
]


class Command(BaseCommand):
    help = "Наполняет каталог статусами, разделами, справочниками и демо-букетами с картинками."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true",
            help="Удалить существующие товары перед наполнением",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["reset"]:
            deleted, _ = Product.objects.all().delete()
            self.stdout.write(f"Удалено записей: {deleted}")

        self.statuses = self.ensure_statuses()
        self.categories = self.ensure_categories()
        self.attributes = self.ensure_attributes()

        created = 0
        for index, payload in enumerate(PRODUCTS, start=1):
            if Product.objects.filter(article=payload["article"]).exists():
                self.stdout.write(f"  {payload['article']} — уже есть, пропускаю")
                continue
            self.create_product(payload, position=index * 10)
            created += 1

        self.stdout.write(self.style.SUCCESS(
            f"Готово: добавлено {created} товаров, "
            f"{Status.objects.count()} статусов."
        ))

    # --- справочники -----------------------------------------------------
    def ensure_statuses(self) -> dict:
        result = {}
        for position, (name, name_uk, color, orderable, note) in enumerate(STATUSES, start=1):
            status, _ = Status.objects.get_or_create(
                name=name,
                defaults={
                    "name_uk": name_uk, "color": color, "is_orderable": orderable,
                    "note": note, "position": position,
                    "slug": STATUS_SLUGS.get(name, ""),
                },
            )
            result[name] = status
        return result

    def ensure_categories(self) -> dict:
        result = {}
        for position, (name, name_uk, slug, children) in enumerate(CATEGORIES, start=1):
            root, _ = Category.objects.get_or_create(
                slug=slug,
                defaults={"name": name, "name_uk": name_uk, "parent": None,
                          "position": position * 10},
            )
            result[slug] = root
            for index, (child_name, child_uk, child_slug) in enumerate(children, start=1):
                child, _ = Category.objects.get_or_create(
                    slug=child_slug,
                    defaults={"name": child_name, "name_uk": child_uk, "parent": root,
                              "position": position * 10 + index},
                )
                result[child_slug] = child
        return result

    def ensure_attributes(self) -> dict:
        """Создаёт значения справочников подбора и возвращает их по адресу."""
        result: dict[type, dict] = {}
        for model, rows in ATTRIBUTES.items():
            bucket = {}
            for position, (name, name_uk, slug) in enumerate(rows, start=1):
                value, _ = model.objects.get_or_create(
                    slug=slug,
                    defaults={"name": name, "name_uk": name_uk, "position": position * 10},
                )
                bucket[slug] = value
            result[model] = bucket
        return result

    # --- товар -----------------------------------------------------------
    def create_product(self, payload: dict, position: int = 100) -> Product:
        product = Product.objects.create(
            article=payload["article"],
            name=payload["name"],
            name_uk=payload["name_uk"],
            category=self.categories[payload["category"]],
            status=self.statuses.get(payload["status"]),
            kind=self.attributes[Kind][payload["kind"]],
            color=self.attributes[Color][payload["color"]],
            size=self.attributes[Size][payload["size"]] if payload.get("size") else None,
            family=payload.get("family", ""),
            stems=payload.get("stems", 0),
            height_cm=payload.get("height", 0),
            summary=payload["summary"],
            summary_uk=payload["summary_uk"],
            # порядок в каталоге «сначала популярные» — как в этом списке
            position=position,
            composition=payload["composition"],
            composition_uk=payload["composition_uk"],
            description=payload["description"],
            description_uk=payload["description_uk"],
            stock_quantity=payload["stock"],
            price=Decimal(payload["price"]),
            old_price=Decimal(payload["old_price"]) if payload.get("old_price") else None,
        )
        product.flowers.set([self.attributes[Flower][s] for s in payload["flowers"]])
        product.occasions.set([self.attributes[Occasion][s] for s in payload["occasions"]])

        self.attach_placeholder(product, payload["color"])
        self.stdout.write(f"  {product.article} — добавлен")
        return product

    def attach_placeholder(self, product: Product, color: str) -> None:
        """Картинка-заглушка вместо фото; владелец заменит в админке."""
        target = Path(settings.MEDIA_ROOT) / "products" / f"demo-{product.article.lower()}.png"
        if not target.exists():
            placeholders.write(target, seed=product.article, color=color,
                               stems=product.stems or 7)
        ProductImage.objects.create(
            product=product,
            image=f"products/{target.name}",
            alt=product.title,
            position=1,
        )
