# АМИГО — полная спецификация проекта для воспроизведения (v2, справочник)

> **Статус:** справочник с подробным кодом и историей решений. Главный документ — `CLAUDE.md` (v3).
> Если они расходятся — прав `CLAUDE.md`. Известные устаревшие места: `TIME_ZONE` должен быть
> `"Europe/Kyiv"` (грабля 27 в v3); состав в v3 — текстовое поле, а не справочник.

**Что это.** Техническое задание, по которому другая ИИ-модель (или разработчик)
может собрать оптовый B2B-каталог заново и получить работающий сайт, а не
приблизительную копию. Здесь описаны не только модели и экраны, но и внутренняя
механика: двуязычность, защита админки, работа с сервером, Telegram, порядок
переноса данных и грабли, на которых проект уже спотыкался.

**Оригинал.** Интернет-магазин оптовой продажи нижнего белья «АМИГО»
(Одесса, ФОП, гуртова торгівля). Автор кода — ISHOD, 2026.

**Как этим пользоваться, если вы ИИ.**

1. Прочитайте разделы 1–3 целиком — там продуктовые решения, без них остальное
   выглядит произвольным.
2. Стройте в порядке разделов 4 → 16, затем 22. Каждый раздел самодостаточен
   и содержит точные имена файлов, классов и настроек: держитесь их, иначе
   перекрёстные ссылки в этом документе перестанут работать.
3. Раздел 18 («Грабли») прочитайте ДО написания кода. Это список ошибок,
   которые уже были допущены и стоили времени. Каждая формулировка там —
   готовое правило, а не история.
4. Разделы, помеченные **[адаптировать]**, содержат данные конкретного магазина
   (телефон, домен, реквизиты). Их надо заменить, а не копировать.
5. Разделы 15.6–15.7 (домен, почта) и 22 (поисковые системы) — это то, что
   делается уже после того, как сайт заработал. Они написаны по итогам
   реального запуска, а не по документации, и содержат сроки и оговорки,
   которых в документации нет.

**Чего в этом документе нет намеренно:** секретов (`SECRET_KEY`, токен бота,
пароль почты), IP сервера, реквизитов ФОП. Всё это живёт в `.env` и никогда
не попадает ни в код, ни в архивы, ни в документацию.

---

## 1. Продукт и решения, из которых следует всё остальное

### 1.1 Кто покупатель

Не частное лицо, а владелец магазина или ФОП, который закупает партиями.
Ему не нужны лукбуки и эмоции — нужно за несколько секунд понять состав,
размерный ряд, остаток на складе и цену за штуку.

Отсюда главное решение интерфейса: **характеристики видны до открытия карточки
товара**. В плитке каталога уже стоят состав, размерный ряд, упаковка, остаток,
цена за штуку. Карточка нужна, только когда покупатель уже выбрал модель.

### 1.2 Оплаты на сайте нет

Покупатель собирает позиции в черновик, оставляет контакты, менеджер
перезванивает и подтверждает. Это не упрощение «на первое время», а бизнес-модель:
опт согласуют голосом (замены размеров, ростовки, сроки). Из этого следует:

- нет платёжных интеграций, нет корзины в базе, нет статусов оплаты;
- сущность называется **заявка** (`Request`), а не заказ;
- черновик живёт в сессии и исчезает после отправки.

### 1.3 Товар продаётся упаковкой

Ни цветов, ни размеров как отдельных сущностей. Товар — это артикул, у которого
есть `package_quantity` (штук в упаковке) и `size_range` (размерный ряд текстом,
как на упаковке: «XL, 2XL, 3XL, 4XL (ассорти в упаковке)»). Остаток — одно число.

Из этого следует, что любое введённое количество нормализуется:
округляется вверх до целой упаковки, поднимается до минимума и обрезается
по остатку. Единственное место, где это решается, — метод
`Product.normalize_quantity()`, и его зовут все: и счётчик в карточке,
и разбор списка артикулов, и форма без JavaScript. Дублировать это правило
где-то ещё — ошибка.

### 1.4 Цена простая

Одна цена за штуку (`price`) и необязательная старая цена (`old_price`).
Скидка НЕ хранится отдельным числом: она существует ровно тогда, когда
`old_price > price`, а процент вычисляется. Это делает невозможным
рассогласование «скидка 20 %, а цены прежние».

Ступенчатых цен («от 100 штук дешевле») в текущей версии нет.

### 1.5 Язык

Сайт двуязычный, **главный язык — украинский**. Русский остаётся как
второй для витрины и как единственный для админки.

Ключевое и неочевидное решение: **тексты в шаблонах и в коде написаны
по-русски, и русский текст сам является ключом перевода** (`msgid`).
Украинский лежит в `locale/uk/LC_MESSAGES/django.po`. Почему так, а не
английские ключи: владелец правит тексты сам и должен видеть в шаблоне
осмысленную фразу, а не `catalog.filter.reset`.

---

## 2. Стек и ограничения среды

| Что | Чем | Почему именно так |
| --- | --- | --- |
| Фреймворк | Django 5.x | |
| База | SQLite (файл `db.sqlite3`) | Нагрузка оптового каталога — десятки посетителей в день. PostgreSQL здесь только добавил бы работы по обслуживанию. |
| Веб-сервер | `waitress` | Кросс-платформенный, ставится как обычный пакет. `runserver` в публичном режиме не годится. |
| Статика | `whitenoise` | Перед Django стоит только туннель, отдавать css/js больше некому. |
| Картинки | `Pillow` | Для `ImageField`. |
| Внешний доступ | Cloudflare Tunnel (`cloudflared`) | Ни один порт наружу не открыт. Из этого следует вся модель защиты, см. раздел 13. |
| Автозапуск | systemd | |
| Фронтенд | Обычный JS без сборки, без фреймворков | Страница обязана работать с выключенным JavaScript. |

**Зависимости целиком** (`requirements.txt`):

```
Django>=5.0,<6.0
Pillow>=10.0
waitress>=3.0
whitenoise>=6.6
```

Больше ничего. Это осознанное ограничение: XLSX-прайс собирается вручную
из ZIP с XML, Telegram-запросы идут через `urllib` стандартной библиотеки,
`.po` компилируется своим кодом. Каждая новая зависимость — это ещё одна
вещь, которую владелец однажды не сможет обновить сам.

**Среда владельца:** Windows, работа через `.bat`-файлы. Из этого следуют
два неочевидных требования:

- `gettext` (утилита `msgfmt`) на Windows нет → нужна **своя команда
  компиляции переводов** (раздел 11.3);
- все служебные операции завёрнуты в `.bat` с человеческими названиями
  кириллицей, а не в команды.

---

## 3. Карта проекта

```
config/          settings.py, urls.py, wsgi.py
core/            фундамент: абстрактные модели, middleware, шлюз админки,
                 утилиты, шаблонные теги, служебные команды
catalog/         товары, справочники, фильтры, фасеты, представления, прайс
orders/          заявка: черновик в сессии, формы, уведомления, Telegram-бот
accounts/        кабинет покупателя: вход по почте, анкета, избранное
pages/           информационные страницы и подвал
templates/       шаблоны Django (общая папка, не по приложениям)
static/css/      base · catalog · product · request · account · page · error · admin
static/js/       core · catalog · product · request
locale/uk|ru/    переводы
deploy/          systemd-юниты, Caddyfile, скрипты бэкапа и сторожа, УСТАНОВКА.md
import/          подготовленные JSON и фотографии для загрузки каталога
media/products/  фотографии товаров
var/             служебное: смещение бота, отметка последней синхронизации
*.bat            операции для владельца
```

Правило: **шаблоны и статика лежат в общих папках, не внутри приложений.**
Владелец правит вёрстку и должен находить файл по имени экрана, а не по имени
приложения.

### 3.1 Адреса

| Метод | Адрес | Что |
| --- | --- | --- |
| GET | `/` | Каталог (весь) |
| GET | `/katalog/<slug>/` | Каталог раздела |
| GET | `/tovar/<slug>/` | Карточка товара |
| GET | `/price/xlsx/`, `/price/xml/` | Выгрузка прайса |
| GET/POST | `/zakaz/` | Заявка |
| GET | `/zakaz/prinyata/<pk>/` | Спасибо |
| POST | `/zakaz/api/dobavit|obnovit|udalit|ochistit|spiskom/` | Действия над черновиком |
| POST | `/zakaz/dobavit/` | То же без JavaScript |
| GET/POST | `/kabinet/...` | Кабинет покупателя |
| POST | `/kabinet/api/izbrannoe/` | Сердечко |
| GET | `/info/<slug>/` | Информационная страница |
| GET/POST | `/vhod-v-upravlenie/` | Шлюз админки (код из Telegram) |
| — | `/admin/` | Админка Django |
| POST | `/i18n/setlang/` | Переключатель языка (штатный Django) |

Адреса — кириллица в транслите (`zakaz`, `kabinet`, `tovar`). Это осознанно:
владелец диктует их по телефону.

---

## 4. Настройки (`config/settings.py`)

### 4.1 Чтение `.env` без библиотек

В начале файла — собственный разбор `.env` (строки `КЛЮЧ=значение`, `#` —
комментарий, кавычки снимаются). Никакого `python-dotenv`.

```python
ENV = read_env(BASE_DIR / ".env")

def env(name, default=""):      return os.environ.get(name) or ENV.get(name) or default
def env_flag(name, default=False):  # 1/true/yes/on/да
def env_list(name):             # через запятую
```

Переменная окружения имеет приоритет над файлом — это позволяет
переопределить настройку на один запуск, не трогая `.env`.

### 4.2 Два режима

```python
PUBLIC = env_flag("PUBLIC", False)
DEBUG = not PUBLIC
```

Один флаг вместо двух: невозможно случайно оставить `DEBUG=1` на боевом сайте.

`SECRET_KEY` берётся из `.env`; при `DEBUG` подставляется заглушка
`django-insecure-local-only`, в публичном режиме без `.env` генерируется
случайный (сессии слетят при перезапуске — это заметно и лечится
заполнением `.env`).

### 4.3 Публичный режим включает

```python
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
if PUBLIC:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    X_FRAME_OPTIONS = "DENY"
```

`CSRF_TRUSTED_ORIGINS` собирается из `ALLOWED_HOSTS`; запись, начинающаяся
с точки (`.trycloudflare.com`), превращается в `https://*.trycloudflare.com`.

### 4.4 Порядок middleware — не вкусовщина

```python
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "core.middleware.AdminAccessMiddleware",      # ← после сессий!
    "core.admin_gate.AdminGateMiddleware",        # ← после сессий!
    "core.middleware.DefaultLanguageMiddleware",  # ← до Locale!
    "django.middleware.locale.LocaleMiddleware",
    "core.middleware.AdminLanguageMiddleware",    # ← после Locale!
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
if DEBUG:
    MIDDLEWARE.append("core.middleware.NoCacheMiddleware")
```

Четыре правила, каждое из которых уже ломало сайт:

1. **Обе проверки админки — после `SessionMiddleware`.** `AdminAccessMiddleware`
   отказывает через `Http404`, а страница 404 у нас своя, с шапкой и счётчиком
   черновика. Черновик живёт в сессии. Если отказ случился раньше сессий,
   страница отказа падает сама, и посетитель получает 500 вместо 404.
2. **Шлюзу нужна сессия** — там хранится отметка о введённом коде.
3. **`DefaultLanguageMiddleware` строго до `LocaleMiddleware`** — она чистит
   заголовок, который тот читает.
4. **`AdminLanguageMiddleware` строго после `LocaleMiddleware`** — она
   перебивает уже выбранный язык.

Плюс защитное правило в контекстных процессорах: любой процессор, который
трогает `request.session`, обязан проверить `hasattr(request, "session")`.
Иначе он падает на странице ошибки, отрисованной до сессий.

### 4.5 Ключевые константы

```python
LANGUAGES = [("uk", "Українська"), ("ru", "Русский")]
LANGUAGE_CODE = "uk"
LOCALE_PATHS = [BASE_DIR / "locale"]
LANGUAGE_COOKIE_AGE = 60 * 60 * 24 * 365      # год: выбор языка не слетает
LANGUAGE_COOKIE_SAMESITE = "Lax"
TIME_ZONE = "Europe/Kyiv"                     # в исходном v2 было Europe/Kiev — это ошибка (грабля 27)

AUTHENTICATION_BACKENDS = ["accounts.backends.EmailBackend",
                           "django.contrib.auth.backends.ModelBackend"]
LOGIN_URL = "/kabinet/vhod/"
LOGIN_REDIRECT_URL = "/kabinet/"
LOGOUT_REDIRECT_URL = "/"
PASSWORD_RESET_TIMEOUT = 60 * 60 * 3          # 3 часа, не сутки

CART_SESSION_KEY = "amigo_draft"
CATALOG_PAGE_SIZE = 12

STORAGES = {"staticfiles": {"BACKEND":
    "whitenoise.storage.CompressedStaticFilesStorage"}}   # без хешей в именах!
```

Про `CompressedStaticFilesStorage` без манифеста: версии файлов проставляет
свой шаблонный тег `versioned` по времени изменения. Вариант с хешами
(`CompressedManifest...`) роняет страницу, если статику забыли собрать —
для проекта, который обновляет владелец, это неприемлемо.

### 4.6 Почта — деградирует, а не падает

```python
EMAIL_BACKEND = ("django.core.mail.backends.smtp.EmailBackend" if EMAIL_HOST
                 else "django.core.mail.backends.console.EmailBackend")
EMAIL_USE_SSL = EMAIL_PORT == 465
EMAIL_USE_TLS = not EMAIL_USE_SSL
EMAIL_TIMEOUT = 20
DEFAULT_FROM_EMAIL = env("EMAIL_FROM") or (
    f"АМИГО <{EMAIL_HOST_USER}>" if EMAIL_HOST_USER else "amigo@localhost")
```

Пока `EMAIL_HOST` пуст, письма печатаются в журнал и сайт работает.
Это важно: половина установок живёт без почты неделями.

### 4.7 Журнал

Логгер `amigo` уровня INFO пишет в stdout, systemd складывает в journald.
Отказы админки и события шлюза видны всегда: `journalctl -u amigo -f`.

### 4.8 `SHOP` — витринные данные **[адаптировать]**

Словарь с названием, телефоном, мессенджерами, складом, минимальной суммой,
временем отсечки и валютой. Ключи с суффиксом `_UK` подменяют основные на
украинской версии (`TAGLINE_UK`, `MANAGER_UK`, `WAREHOUSE_UK`).
Пустой `ADDRESS` означает «в подвале адрес не показывать».

---

## 5. Ядро (`core/`)

### 5.1 Абстрактные модели

```
models.Model
  └── TimeStampedModel      created_at (db_index), updated_at
        └── NamedModel      name, name_uk, slug, is_active, position
              ├── Category, Status, все справочники подбора
              └── Product, InfoPage
```

`TimeStampedQuerySet.recent(limit)`, `ActivatableQuerySet.active()/hidden()`.

**Автоматический slug.** В `NamedModel.save()`: если slug пуст — строится
из `build_slug()` (по умолчанию транслит имени), и коллизии разрешаются
суффиксом `-2`, `-3`. `Product` переопределяет `build_slug()` на
`transliterate(f"{article}-{name}")`.

**`NamedModel.title`** — свойство «название на языке посетителя»:

```python
@property
def title(self):
    if get_language() == "uk" and self.name_uk:
        return self.name_uk
    return self.name
```

Правило проекта: **в шаблонах всегда `obj.title`, никогда `obj.name`.**
Один забытый `product.name` в шаблоне — и украинская версия молча
показывает русское название (это уже случалось, см. 18.6).

### 5.2 `core/utils.py`

- `transliterate()` — своя таблица кириллица→латиница, включая украинские
  `ґ є і ї`. Двойные дефисы схлопываются, края обрезаются.
- `format_money(1008)` → `1 008` (пробел вместо запятой).
- `plural_ru(n, one, few, many)` — «1 модель / 2 модели / 5 моделей».

### 5.3 `core/mixins.py`

- `PageTitleMixin` — заголовок и хлебные крошки в контекст.
- `JsonRequestMixin` — разбор тела как JSON плюс `ok(**data)` / `fail(msg, status)`.
- `AjaxTemplateMixin` — если пришёл заголовок `X-Requested-With: fetch`,
  отдаём не страницу, а JSON `{ok, html, count, query}` с отрисованным
  фрагментом. Так работает каталог без перезагрузки.

### 5.4 Шаблонные теги (`core/templatetags/shop.py`)

- `{{ price|money }}` → `59 ₴`; `money_plain` — без валюты;
- `{{ n|plural:"модель,модели,моделей" }}`;
- `{{ dict|get_item:key }}` — в шаблонах Django нет доступа по ключу-переменной;
- `{% query_replace page=3 %}` — меняет параметры в текущем GET, остальные
  сохраняет;
- `{% versioned 'css/base.css' %}` → `/static/css/base.css?v=1788891442`.
  Время изменения файла кэшируется в словаре при первом обращении.

### 5.5 Дашборд админки (`core/templatetags/admin_dashboard.py`)

Тег `amigo_stats` собирает четыре плитки (заявок всего / новых / сумма
открытых / товаров), `recent_requests` — последние шесть заявок,
фильтр `status_pill` — класс плашки статуса. Шаблон `templates/admin/index.html`
переопределяет главную страницу админки.

---

## 6. Модель данных каталога (`catalog/models.py`)

### 6.1 Сущности

**`Category`** — раздел, `parent` на себя, **ровно один уровень вложенности**.
Верхний уровень попадает в меню. `get_absolute_url()` → `/katalog/<slug>/`.

**`Status`** — статус товара: `color` (HEX плашки), `is_orderable`
(снимите галку для «Снят с продажи»), `note`. Значения заводятся в админке.

**`AttributeModel`** — абстрактный справочник подбора. От него наследуются:
`ModelKind` (модель), `ProductType` (тип), `Quality` (качество),
`Manufacturer`, `Brand`, `Feature` (характеристики, many-to-many),
`Composition` (состав), `Density`, `Fit`, `Seam`, `Elastic`, `Care`, `Season`.

Важное решение: **свободного текста в характеристиках нет.** Состав — это
ссылка на справочник, а не строка. Иначе один товар получит
«95% хлопок, 5% эластан», другой «хлопок 95%», и отфильтровать каталог
станет невозможно. *(В v3 состав — текстовое поле и не фасет; это решение
опта белья, прав v3.)*

**`FacetGroup`** — настройка панели подбора: `code` (связь со справочником),
`name`/`name_uk` (подпись), `position`, `is_active` (показывать в подборе),
`has_search` (поле поиска внутри группы — нужно для брендов).

**`Product`** — артикул (уникальный), раздел, статус, `summary`,
`description`, `description_uk`, ссылки на все справочники, `feature_tags`
(M2M), упаковка (`size_range`, `package_quantity`, `min_order_quantity`,
`stock_quantity` (db_index), `box_packages`, `weight_kg`, `barcode`),
цена (`price`, `old_price`, `retail_price_hint`).

`Meta.ordering = ("position", "-created_at")`.

**`ProductImage`** — `product`, `image` (`upload_to="products/"`), `alt`,
`position`. Первая по порядку — обложка.

### 6.2 Свойства `Product`, которые несут логику

| Свойство | Что делает |
| --- | --- |
| `title` | **Всегда украинское**: `name_uk or name`. Отличается от `NamedModel.title`! |
| `description_text` | По языку страницы, с откатом на русский |
| `package_price`, `amount_for(n)` | Деньги |
| `has_discount` | `old_price and old_price > price` — строго «выше» |
| `discount_percent` | Целые проценты; 0, если разница меньше половины процента (плашка «−0 %» выглядит ошибкой) |
| `packages_in_stock` | `stock_quantity // package_quantity` |
| `order_step` | Шаг счётчика = упаковка |
| `minimum_quantity` | Минимум, округлённый **вверх** до целой упаковки |
| `max_quantity` | `(stock // step) * step` — хвост в 2 штуки при упаковке 10 продать нельзя |
| `normalize_quantity(q)` | Единственная точка правды: 0 остаётся 0; иначе округление вверх, подъём до минимума, обрезание по `max_quantity` |
| `is_orderable` | `status.is_orderable` И есть остаток |
| `stock_label` | Если статус запрещает заказ — название статуса; иначе «Нет в наличии» / «Статус · N уп.» |
| `stock_state` | `out` / `low` (<20 упаковок) / `ok` |
| `cover`, `has_photo` | Первая фотография |
| `specification_rows()` | Таблица характеристик: сначала справочники из реестра `FACETS`, потом числа |

**Почему `Product.title` не следует языку.** У справочников название идёт
за языком страницы, у товара — нет: магазин украинский, и товар должен
называться одинаково везде — в каталоге, в заявке, в накладной, в разговоре
с покупателем. Русское название остаётся в базе для админки.

### 6.3 Реестр справочников (`catalog/facets.py`) — центральный приём

Одна структура данных питает четыре подсистемы сразу:

```python
@dataclass(frozen=True)
class FacetSpec:
    code: str          # ключ в адресной строке: ?brand=amigo
    field: str         # поле товара
    model: type        # модель справочника
    label: str         # подпись
    multiple: bool = False    # M2M
    searchable: bool = False  # поле поиска внутри группы
    in_filter: bool = True    # показывать в подборе по умолчанию
    position: int = 100

    @property
    def lookup(self): return f"{self.field}__slug__in"

FACETS = [FacetSpec("type", "product_type", ProductType, "Тип", position=10), ...]
BY_CODE, BY_MODEL = ...
```

Добавили строку в `FACETS` — новая характеристика появилась одновременно:

- в панели подбора каталога,
- в фильтрации по адресной строке,
- в таблице «Характеристики» на странице товара,
- в колонках выгрузки прайса,
- в правилах снятия товаров с публикации при удалении справочника.

`visible_specs()` возвращает справочники, включённые в панель, в порядке
из админки (`FacetGroup`). `group_titles()` — настройки групп.

**Это самая ценная идея проекта. Воспроизводите её первой.**

### 6.4 Менеджеры (`catalog/managers.py`)

`ProductQuerySet(ActivatableQuerySet)`:

```python
published()                     # = active()
with_relations()                # select_related всех справочников + prefetch
in_category(slug)               # Q(category__slug=slug) | Q(category__parent__slug=slug)
in_stock()
with_status(slugs)
with_attribute(lookup, slugs, multiple)   # distinct() только для M2M
availability(values)            # {"in"} / {"out"} по stock_quantity
price_between(low, high)
search(term)                    # name, article, composition, brand, model_kind
```

`ProductManager.catalog()` = `published().with_relations()`.

**`in_category` учитывает подразделы.** У «Чоловічої білизни» своих товаров
нет вовсе, все лежат в «Боксерах» и «Трусах-сліпах». Без этого раздел
верхнего уровня был бы пустым.

---

## 7. Фильтры, сортировка, представления каталога

### 7.1 Фильтры (`catalog/filters.py`)

Каждый фильтр — класс с тремя обязанностями: `parse(params)`,
`apply(queryset, value)`, `chips(value)`.

| Класс | Формат |
| --- | --- |
| `MultiChoiceFilter` | `?brand=amigo&brand=nike` **или** `?brand=amigo,nike` — поддерживать оба |
| `AttributeFilter` | Один класс на все характеристики, строится из `FacetSpec` |
| `CategoryFilter` | `?category=slug` |
| `SearchFilter` | `?q=` |
| `PriceRangeFilter` | `?price_min=&price_max=`, чип снимает оба параметра сразу (`extra`) |
| `FlagFilter` | `?in_stock=1` |

`ProductFilterSet` собирает список: раздел, поиск, статус, затем **все
фильтры из `FACETS` автоматически**, затем наличие и цена. Свойство
`queryset` прогоняет их по очереди и запоминает применённые — из этого
строятся `chips`.

### 7.2 Сортировка

```python
OPTIONS = {
    "cheap":     ("сначала дешевле",     ("price",)),
    "expensive": ("сначала дороже",      ("-price",)),
    "new":       ("сначала новые",       ("-is_new", "-created_at")),
    "sale":      ("сначала со скидкой",  ("-discount", "price")),
}
DEFAULT = "cheap"
```

`order_by` всегда дописывает `-created_at` последним ключом: при равенстве
основного признака порядок должен быть предсказуемым, иначе SQLite выдаёт
строки как ей удобно и пагинация начинает дублировать товары.

`prepare(queryset)` досыпает то, чего нет в модели:

- **`new`** — аннотация `is_new`: 1, если статус «Новинка» (ищем и по slug
  `novinka`, и по названию без учёта регистра). Сортировать по одной дате
  бесполезно: весь каталог заливается пачкой и отличается миллисекундами.
- **`sale`** — аннотация `discount` = доля скидки:

```python
money = lambda field: Cast(F(field), FloatField())
ratio = ExpressionWrapper(
    (money("old_price") - money("price")) / money("old_price"),
    output_field=FloatField())
queryset.annotate(discount=Case(
    When(Q(old_price__isnull=False) & Q(old_price__gt=F("price")), then=ratio),
    default=Value(0.0), output_field=FloatField()))
```

Два обязательных решения здесь:
1. **Доля, а не разница в гривнах.** Иначе наверх уедут дорогие товары,
   у которых «минус 80 ₴» — те же пять процентов.
2. **`Cast(..., FloatField())`.** Деление двух `Decimal` SQLite отдаёт так,
   что Django возвращает `NULL`, сортировка молча вырождается в сортировку
   по цене. Проверено на живой выборке (см. 18.2).

### 7.3 Панель подбора (`CatalogFacetsMixin`)

Считаем количество значений **в пределах текущего раздела и без учёта уже
выбранных галок** — иначе цифры схлопнутся в нули после первого же клика.

```python
values = spec.model.objects.active().annotate(
    total=Count("products", filter=Q(products__in=base), distinct=True))
```

Значения с нулём тоже показываем: завели новый бренд в админке — он сразу
виден в подборе. Плюс отдельная псевдогруппа «Наличие» с двумя значениями,
посчитанными по `stock_quantity`.

Подписи справочников, выключенных из панели, всё равно собираются — иначе
чип над сеткой покажет slug вместо названия.

### 7.4 `CatalogView`

`ListView` + `PageTitleMixin` + `AjaxTemplateMixin` + `CatalogFacetsMixin`.
`paginate_by = settings.CATALOG_PAGE_SIZE`.

`get_params()` кладёт `category` из URL в параметры — так один и тот же
`ProductFilterSet` обслуживает и `/katalog/<slug>/`, и `?category=`.

`render_to_response()` при fetch-запросе отдаёт только фрагмент сетки.

### 7.5 Баннер новинок над каталогом

Правила:

- в разделе — три последних товара **этого раздела**;
- в общем каталоге — **по одной новинке из каждого раздела верхнего уровня**
  (не больше четырёх: пятая карточка становится с ноготь);
- внутри раздела порядок: сначала статус «Новинка», потом по дате добавления;
- только товары с фотографией.

```python
has_photo = Exists(ProductImage.objects.filter(product=OuterRef("pk")))
newest = (self.facet_base().filter(has_photo)
          .annotate(is_new=Case(When(Q(status__slug="novinka")
                                     | Q(status__name__iexact="Новинка"),
                                     then=Value(1)),
                                default=Value(0), output_field=IntegerField()))
          .order_by("-is_new", "-created_at").prefetch_related("images"))

if self.get_current_category():
    return list(newest[:3])

picked = []
for root in Category.objects.filter(parent__isnull=True, is_active=True)\
                            .order_by("position", "name")[:4]:
    item = newest.in_category(root.slug).first()
    if item is not None:
        picked.append(item)
return picked or list(newest[:3])
```

`Exists`, а не `JOIN` с `filter()`: JOIN размножил бы товар по числу
фотографий, пришлось бы звать `distinct()`, который в SQLite плохо дружит
с сортировкой.

Отдельный запрос на раздел, а не оконная функция: «первая строка внутри
группы» в SQLite делается через `ROW_NUMBER() OVER (PARTITION BY ...)`,
и это придётся объяснять тому, кто полезет в код после нас. Четыре
дешёвых запроса лучше.

**Вёрстка баннера — статическая, без слайд-шоу.** Причина конкретная:
фотографии в этом магазине — снимки упаковок с крупным печатным текстом.
Растянутые на всю ширину, они спорят с надписями баннера. Поэтому текст
слева на чистом фоне, три-четыре маленькие карточки справа, ничего не
двигается и JavaScript блоку не нужен. На телефоне (≤620px) заголовок
и подпись скрываются, остаётся строка «Новинки каталога» + ссылка,
а карточки превращаются в ленту с `scroll-snap`, где край следующей
карточки виден специально.

### 7.6 Карточка товара

`ProductDetailView` отдаёт `specification_rows()`, все фотографии,
хлебные крошки и три «похожих» товара из того же раздела.

### 7.7 Фронтенд каталога

`static/js/core.js` определяет глобальный объект `AMIGO`:
`api` (fetch с `X-CSRFToken` из `body[data-csrf]` и `X-Requested-With: fetch`),
`Money`, `Plural`, `DraftBadge`, `ProductCards`, `Favorites`, `debounce`.

`CatalogPage` перехватывает `change`/`input` формы фильтров (с задержкой
250 мс), клик по чипам и пагинации, изменение сортировки — и подменяет
сетку. При ошибке делает `form.submit()`, то есть честно откатывается
к обычной форме.

**Адрес обновляется через `replaceState`, и путь берётся из `form.action`,
а не из `window.location.pathname`.** Разбор этой ошибки — в 18.3.

---

## 8. Заявка (`orders/`)

### 8.1 Черновик в сессии (`orders/draft.py`)

Структура: `{"<id товара>": количество штук}` под ключом
`settings.CART_SESSION_KEY`. Размеров нет — позиция это просто количество.

`RequestDraft` умеет `add`, `set_quantity`, `remove`, `clear`, `totals`,
`as_dict` и поддерживает `len()`/`bool()`/итерацию. `DraftLine` считает
упаковки, сумму и признак «ниже минимума». `DraftTotals` вдобавок считает
прогресс до минимальной суммы заявки (`min_reached`, `min_gap`,
`min_progress`) — из него рисуется полоса «добавьте ещё на N ₴».

### 8.2 Модели

**`Request`** — заявка: `user` (nullable — заявку оставляют и без кабинета),
контакты (`name`, `phone`, `email`, `company`, `city`, `preferred_contact`,
`comment`), `status` (`new/work/confirmed/shipped/rejected`),
`manager_note`, `total_quantity`, `total_amount`.
`number` → `№00012`. `recalculate()` пересчитывает итоги по строкам.

**`RequestLine`** — `article`, `product_name`, `quantity`, `unit_price`
**копируются на момент подачи**. Через месяц должно быть видно, о чём
договаривались, даже если цена и название с тех пор изменились.
`product` — `SET_NULL`: удалённый товар не должен уносить заявку.

### 8.3 Отправка

```python
@transaction.atomic
def create_request(form, totals, user=None):
    order = form.save(commit=False)
    order.status = Request.Status.NEW
    if user is not None and user.is_authenticated:
        order.user = user
    order.save()
    for line in totals.lines:
        RequestLine.objects.create(..., product_name=line.product.title, ...)
    order.recalculate()
```

Дальше: уведомление в Telegram (в фоне), очистка черновика, запись
`request.session["last_request"] = order.pk` и редирект на «спасибо».

**Страницу «спасибо» видит только автор заявки:**
`RequestSuccessView.get_queryset()` фильтрует по номеру из сессии.
Иначе номера перебираются и чужие контакты утекают.

### 8.4 Форма и валидация

Подписи и подсказки полей задаются **в форме**, а не в модели: в модели
они по-русски и такими нужны в админке, а покупателю форма показывается
на языке страницы. Русский текст в форме — одновременно ключ перевода.

`clean_phone` требует не меньше 9 цифр после удаления всего нецифрового.
Обязательная галка `agree` — согласие на обработку данных.

### 8.5 Добавление списком

`QuickListParser` разбирает строки вида `9099 24`: **артикул — первое слово,
количество — последнее число в строке** (необязательное «шт» в конце
допускается, разделители `\s , ;`). Строка из одного числа считается
артикулом без количества, а не количеством. Парсер
сверяет с каталогом и остатками, каждую строку помечает валидной или нет
с объяснением. Количества прогоняются через `product.normalize_quantity()`.

### 8.6 API черновика

Все действия возвращают не только цифры, но и **готовую разметку таблицы
позиций** (`orders/_draft_lines.html`). Страница обновляет её на месте и
никогда не перезагружается: перезагрузка обрывает следующий запрос,
который пользователь уже успел отправить.

Есть резервный путь без JavaScript: `POST /zakaz/dobavit/` обычной формой.

---

## 9. Кабинет покупателя (`accounts/`)

### 9.1 Вход по почте, без своей модели пользователя

Стандартный `User` Django; при регистрации в `username` кладётся та же
почта. Сверяет `accounts/backends.EmailBackend`:

```python
class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        login = username or kwargs.get("email") or ""
        if not login or password is None:
            return None
        try:
            user = User.objects.get(email__iexact=login.strip())
        except (User.DoesNotExist, User.MultipleObjectsReturned):
            User().set_password(password)   # холостое хеширование
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
```

Три детали, каждая обязательна:

1. **`email__iexact`** — покупатель пишет почту как придётся.
2. **`MultipleObjectsReturned` → отказ всем.** Пустить «первого попавшегося»
   при дублирующейся почте — дыра.
3. **Холостое хеширование при промахе.** Иначе по времени ответа видно,
   есть такая почта в базе или нет.

`ModelBackend` остаётся вторым — им входит администратор по логину.

Отказ от своей модели пользователя сохраняет целыми админку, смену пароля
и восстановление доступа, которые Django уже умеет.

### 9.2 Модели

**`Profile`** (`OneToOne`) — `phone`, `company`, `city`, `preferred_contact`.
Метод `as_request_initial()` отдаёт словарь для предзаполнения формы заявки.

**`Favorite`** — `user` + `product`, `UniqueConstraint("user", "product")`.

### 9.3 Экраны

`/kabinet/` (сводка), `vhod/`, `vyhod/`, `registratsiya/`, `zakazy/`,
`zakazy/<pk>/`, `izbrannoe/`, `dannye/`, `api/izbrannoe/`.

После регистрации человек **сразу вошёл** (`login(request, user,
backend="accounts.backends.EmailBackend")`) — вводить те же данные второй
раз было бы издевательством. Явный `backend=` обязателен: их два, и Django
не угадает.

`order_detail` фильтрует по `user=request.user` — чужую заявку не открыть.

### 9.4 Избранное без N+1

Контекстный процессор `accounts.context_processors.cabinet` одним запросом
кладёт в контекст `favorite_ids` (frozenset) и `favorites_count`.
Иначе каждая из двенадцати карточек ходила бы в базу за своим сердечком.
Гостю не достаётся ничего.

### 9.5 Восстановление пароля

Штатные `PasswordResetView` и компания со своими шаблонами.
`PASSWORD_RESET_TIMEOUT = 3 часа`: письмо могло полежать, но сутки для
ссылки «войти без пароля» — слишком долго.

---

## 10. Информационные страницы (`pages/`)

**`InfoPage`** — `group` (`buyer` / `partner` / `hidden` — колонка в подвале),
`lead`/`lead_uk`, `body`/`body_uk`, `external_url`.

`body` — обычный текст с минимальной разметкой, которую владелец запомнит
с одного раза:

- пустая строка разделяет абзацы;
- строка, начинающаяся с `— ` или `- `, становится пунктом списка;
- строка `## Заголовок` — подзаголовком.

Метод `blocks()` разбирает это в список `{kind, text|items}`.

`external_url` позволяет пункту подвала вести не на страницу, а на адрес
вроде `/price/xlsx/`.

Подвал собирается контекстным процессором `pages.context_processors.footer_links`
из этой же таблицы: добавили страницу — она сама появилась в нужной колонке.

Наполнение — команда `seed_pages` (доставка, оплата, возврат, контакты,
политика конфиденциальности, партнёрские страницы).

---

## 11. Двуязычность — целиком

Это самая недооценённая часть проекта. Собрать её из четырёх независимых
механизмов, каждый из которых уже ломался.

### 11.1 Где какой язык

| Что | Язык |
| --- | --- |
| Витрина | Украинский по умолчанию, русский по выбору |
| Названия товаров | **Всегда украинские** (`name_uk or name`) |
| Названия справочников, разделов, страниц | По языку страницы |
| Админка | Всегда русская |

### 11.2 Русский текст как ключ перевода

В шаблонах `{% trans "Смотреть новинки" %}`, в коде `_("Нет в наличии")`.
Каталог `locale/uk/` содержит перевод, каталог `locale/ru/` —
**тождественные строки** (`msgid == msgstr`).

**Русский каталог обязателен, хотя выглядит бессмысленным.** Django при
`LANGUAGE_CODE = "uk"` подставляет украинский каталог как запасной; без
русского каталога русская версия сайта показывала бы украинские строки.

### 11.3 Своя компиляция `.po` → `.mo`

Штатная `compilemessages` вызывает `msgfmt` из GNU gettext, которого на
Windows нет. Поэтому — команда `core/management/commands/compilelocales.py`,
которая собирает `.mo` вручную:

- `parse_po(text)` — разбирает `msgid`/`msgstr` с продолжением строк
  (`msgid_plural` не поддерживается: склонения делает свой фильтр `plural`);
- `build_mo(entries)` — двоичный формат из документации GNU gettext:
  магическое число `0x950412DE`, две таблицы смещений, обязательная
  служебная запись с пустым `msgid` и заголовком
  `Content-Type: text/plain; charset=UTF-8`.

Запуск: `manage.py compilelocales`. Вызывается в `ЗАПУСТИТЬ-КОПИЮ.bat`
и на каждом деплое.

### 11.4 Украинский по умолчанию, несмотря на браузер

Django выбирает язык так: кука → `Accept-Language` → `LANGUAGE_CODE`.
Средний шаг вреден: у многих украинских покупателей браузер русский,
и они попадали на русскую версию, не зная, что украинская есть.

```python
class DefaultLanguageMiddleware(MiddlewareMixin):
    HEADER = "HTTP_ACCEPT_LANGUAGE"
    def process_request(self, request):
        if request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME):
            return None          # выбор сделан руками — не вмешиваемся
        request.META.pop(self.HEADER, None)
```

Выбор посетителя уважается полностью: нажал РУС — кука поставлена,
сайт русский, пока он сам не передумает. Кука живёт год.

### 11.5 Админка всегда русская

```python
class AdminLanguageMiddleware(MiddlewareMixin):
    LANGUAGE = "ru"
    def process_request(self, request):
        if request.path.startswith(settings.ADMIN_PATH):
            translation.activate(self.LANGUAGE)
            request.LANGUAGE_CODE = self.LANGUAGE
```

Иначе при украинском браузере служебные надписи Django перевелись бы,
а названия полей (они в моделях по-русски) остались русскими — каша.

### 11.6 Переключатель

Обычная POST-форма на штатный `{% url 'set_language' %}` со скрытым
`next = request.get_full_path`. Работает без JavaScript.

### 11.7 Правила, которые надо соблюдать всё время

1. В шаблонах — только `obj.title` / `product.title`, никогда `.name`.
2. Каждая новая строка в шаблоне или в коде оборачивается в `{% trans %}` / `_()`.
3. После добавления строк — дописать её в **оба** `.po` и пересобрать `.mo`
   (в v3 для этого есть `makelocales`).
4. Проверка полноты: выгрузить из базы все `name`/`name_uk` и убедиться,
   что `name_uk` заполнено везде; отдельно — прогнать шаблоны регуляркой,
   вырезав `{% trans %}`/`{% blocktrans %}`, и посмотреть, какая кириллица
   осталась голой.

### 11.8 Перевод содержимого базы

Названия товаров, разделов, справочников и текстов страниц переводятся
**миграциями данных**, а не руками в админке. Причина: миграция едет вместе
с кодом и применяется на сервере сама. Примеры в проекте:
`catalog/0003_ukrainian_names.py`, `catalog/0008_ukrainian_rest.py`,
`catalog/0009_product_names_uk.py`, `pages/0006_ukrainian_page_texts.py`.

---

## 12. Админка

### 12.1 Товары

`list_display`: миниатюра, артикул, название, раздел, статус, цена,
остаток, показывать-ли. `list_editable` — цена, статус, остаток и «показывать»:
массовая правка прямо в списке, без захода в карточку. `list_per_page = 30`,
`save_on_top = True`, `filter_horizontal` для характеристик.
`list_filter` по статусу, разделу и справочникам. `search_fields` по
артикулу, названию, составу, бренду. Инлайн фотографий с превью.
Действия «Показывать на сайте» / «Скрыть с сайта».

### 12.2 Единственный администратор

`core/admin.py` перерегистрирует `User` на `SingleAdminUserAdmin`:

- кнопка «Добавить» не показывается, пока суперпользователь существует;
- последнего администратора нельзя удалить;
- у последнего администратора поля `is_superuser`, `is_staff`, `is_active`
  становятся readonly — чекбокс нельзя снять даже случайно.

Плюс команда `ensure_single_admin`: лишних не удаляет, а **отключает** —
войти нельзя, история изменений цела.

### 12.3 Удаление справочника не стирает товары

`catalog/deletion.py` + `catalog/signals.py`:

```python
@receiver(pre_delete)
def unpublish_on_reference_delete(sender, instance, **kwargs):
    if is_reference(instance):
        unpublish_products(instance)
```

Правило: справочник удалить можно всегда, но товары, которые на него
ссылались, **снимаются с публикации** (`is_active = False`). Они пропадают
из каталога, поиска и выгрузок, но остаются в базе с фотографиями и ценами.
Вернуть — галкой в списке товаров.

Именно `pre_delete`: после удаления связь уже разорвана (`SET_NULL`),
и найти пострадавшие товары будет нельзя.

Плюс свои шаблоны подтверждения удаления
(`templates/admin/catalog/delete_confirmation.html` и
`delete_selected_confirmation.html`), которые показывают, сколько товаров
пострадает и какие артикулы.

### 12.4 Панель подбора настраивается из админки

`FacetGroup` — единственная модель, у которой запрещены добавление и
удаление: строки создаёт команда `seed_facets`, по одной на справочник.
Менеджер может только переименовать группу, включить поиск и поменять
порядок или спрятать её из панели.

### 12.5 Главная страница админки

`templates/admin/index.html` + `templates/admin/base_site.html` +
`static/css/admin.css`: четыре плитки со сводкой, последние шесть заявок,
карточки разделов. Владелец видит состояние дел сразу, не заходя в разделы.

---

## 13. Защита — по слоям

Модель угроз простая и честная: сайт маленький, целенаправленно его никто
не ломает; опасность — роботы, круглосуточно перебирающие пароли к `/admin/`,
и случайная утечка секретов.

### 13.1 Сеть

**Наружу не открыт ни один порт, кроме SSH.** `ufw` разрешает только
OpenSSH. Django слушает `127.0.0.1:8000`. Весь трафик приходит через
Cloudflare Tunnel — исходящее соединение с сервера наружу.

Из этого следует ключевое свойство: **заголовку `CF-Connecting-IP` можно
верить.** Обычно заголовок подделывается, но здесь единственный путь к
серверу — туннель, а Cloudflare переписывает этот заголовок своим значением,
что бы ни прислал клиент.

> **Если вы уходите от туннеля и открываете порт наружу — проверку по IP
> надо переделать на `REMOTE_ADDR` + `X-Forwarded-For` от вашего прокси.
> Это записано и в `deploy/Caddyfile`, и в докстринге middleware.**

### 13.2 Слой 1: доступ к `/admin/` по IP

`core/middleware.AdminAccessMiddleware`.

`client_ip()` — `CF-Connecting-IP` (первый адрес из списка), иначе `REMOTE_ADDR`.
`is_allowed()` — loopback проходит всегда; при `ADMIN_LOCAL_ONLY` список
адресов не смотрится вообще (чтобы забытая в `.env` строка не открыла
админку наружу); иначе — проверка вхождения в сети из `ADMIN_ALLOWED_IPS`
(поддерживаются подсети: `178.94.0.0/16`, `2a02:1810::/32`).

`guarding()` — таблица решений:

| Условие | Проверять IP? |
| --- | --- |
| `ADMIN_LOCAL_ONLY=1` | Да, всегда |
| `ADMIN_ACCESS_BY_IP=0` | Нет |
| Список `ADMIN_ALLOWED_IPS` заполнен | Да |
| Список пуст, шлюз Telegram включён | **Нет** — иначе до шлюза никто не дойдёт |
| Список пуст, шлюз выключен | Да (пускаем только с сервера) |

Последняя строка важна: нельзя оставить админку открытой интернету под
одним паролем «потому что настройки пустые».

Отказ — **`Http404`, а не 403**: пусть выглядит так, будто админки здесь нет.
Адрес пишется в журнал (`logger.warning`), чтобы владелец мог найти свой
новый IP после смены провайдера.

**Запасной вход, работающий всегда:**

```
ssh -L 8000:127.0.0.1:8000 amigo@СЕРВЕР
затем http://127.0.0.1:8000/admin/
```

### 13.3 Слой 2: одноразовый код из Telegram (`core/admin_gate.py`)

Пока в сессии нет отметки о пройденном коде, вместо админки показывается
страница «Пришлите код». Код уходит в Telegram владельцу. Получаются две
ступени: даже зная логин и пароль, войти нельзя без доступа к тому Telegram.

Ключи сессии: `admin_gate` (состояние кода), `admin_gate_passed`
(до какого времени пускаем), `admin_gate_next` (куда вернуть).

**Обязательные свойства реализации** — каждое закрывает конкретную атаку:

| Свойство | Зачем |
| --- | --- |
| Код хранится **хешем** `sha256(f"{SECRET_KEY}:{code}")` | Сессии лежат в базе; утёкшая база не должна отдавать действующие коды |
| Живёт 5 минут (`ADMIN_GATE_CODE_SECONDS = 300`) | |
| Сгорает после первой удачной проверки | |
| 5 неверных попыток — код аннулируется целиком | Шестизначное число подбирается перебором за вечер |
| Сравнение через `hmac.compare_digest` | Иначе по задержке ответа код угадывается посимвольно |
| Новый код не чаще раза в 45 с | Иначе шлюз — кнопка «завалить владельца сообщениями» |
| Отметка о проходе живёт 12 ч | Компромисс между удобством и риском |
| Сам код **никогда не пишется в журнал** | Журнал читают больше людей, чем кажется |
| Запросы с `127.0.0.1` шлюз не трогает | Запасной вход по SSH, если Telegram лежит. Отключается `ADMIN_GATE_ALLOW_LOCAL=0` для проверки шлюза на копии |

Middleware:

```python
def process_request(self, request):
    if not enabled(): return None
    path = request.path
    if not path.startswith(settings.ADMIN_PATH) and path != GATE_PATH:
        return None                     # дешёвая проверка ПЕРЕД reverse
    try:
        gate_url = reverse("admin-gate")
    except NoReverseMatch:
        logger.error("Шлюз админки: адрес admin-gate не найден, шлюз пропущен")
        return None                     # лучше пропустить, чем уронить сайт
    ...
```

Два защитных решения: проверка пути **до** `reverse` (он незачем на каждой
странице витрины) и `try/except NoReverseMatch` — если на сервер доехал
новый код со старым `urls.py`, сайт не должен падать целиком.

`enabled()` возвращает True только если включён флаг **и** заполнены токен
и chat_id: без Telegram шлюз молча выключается, иначе он запер бы владельца.

Адрес шлюза — `/vhod-v-upravlenie/`, зарегистрирован **выше** `/admin/`
в `config/urls.py`, иначе админка перехватит его.

### 13.4 Слой 3: ограничения systemd

У сервиса сайта и сервиса бота:

```
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/home/amigo/amigo
ProtectKernelTunables=true
ProtectControlGroups=true
RestrictSUIDSGID=true
```

Даже если в сайте найдут дыру, писать можно только в свою папку,
получить root из процесса нельзя.

### 13.5 Секреты

`.env` рядом с `manage.py`: `SECRET_KEY`, `TELEGRAM_BOT_TOKEN`,
`EMAIL_HOST_PASSWORD`, `ALLOWED_HOSTS`, `ADMIN_*`.

Правила, нарушение любого — инцидент:

- `.env` в `.gitignore`, **не входит в архив деплоя** (у сервера свой `.env`,
  и отправка кода его не трогает);
- `chmod 600 .env`;
- секреты вписываются **только редактором на сервере** (`nano`), никогда
  через `echo >>` — команда осядет в `~/.bash_history`;
- никогда не показывать содержимое `.env` в чате, скриншоте или логе.
  Безопасно посмотреть, какие ключи заполнены:
  `grep -o '^[A-Z_]*=' ~/amigo/.env`;
- если `SECRET_KEY` утёк — **менять немедленно**: им подделываются сессии,
  а значит и отметка о пройденном шлюзе, то есть двухступенчатая защита
  обходится целиком;
- если утёк токен бота — отозвать через `@BotFather` (`/revoke`).

### 13.6 Прикладные мелочи, которые тоже защита

- Страницу «спасибо» видит только автор заявки (номер в сессии).
- `order_detail` в кабинете фильтрует по `user=request.user`.
- `EmailBackend` не даёт определить существование почты по времени ответа.
- Шаблон `500.html` не должен зависеть от контекстных процессоров,
  которые могут упасть.
- Контекстные процессоры, читающие сессию, проверяют `hasattr(request, "session")`.

---

## 14. Telegram

### 14.1 Уведомление о заявке (`orders/notify.py`)

- Отправка в **фоновом потоке** (`threading.Thread(daemon=True)`).
  Покупатель не должен ждать Telegram и тем более видеть ошибку, если тот лежит:
  заявка уже сохранена, уведомление — дело второе.
- Ни одна ошибка не долетает до покупателя: всё в журнал.
- Стандартная библиотека, без `requests`.
- HTML-разметка, экранирование через `html.escape`, потолок 4000 символов,
  не больше 25 позиций в сообщении.
- В конце — прямая ссылка на заявку в админке (`SITE_URL` + путь).
- `send_raw(text)` — синхронная отправка, ею пользуются шлюз админки и
  команда проверки `telegram_test`.

Если токен или chat_id пусты — функция молча ничего не делает.

### 14.2 Бот-справочная (`orders/management/commands/telegram_bot.py`)

Зачем: админка закрыта наружу, а посмотреть с телефона, сколько пришло
заявок, хочется. Бот **только читает**, ничего не меняет.

Протокол — **длинные опросы** (`getUpdates` с `timeout=25`), не webhook:
не нужен внешний адрес и открытый порт.

Смещение последнего обработанного сообщения хранится в `var/bot-offset`.
Без него после перезапуска бот заново отвечал бы на старые команды.

**Отвечает строго одному человеку** — тому, чей id в `TELEGRAM_CHAT_ID`.
Сообщение с чужого id молча игнорируется и пишется в журнал: если кто-то
нашёл бота, это видно, но бот не подтверждает, что он живой.

Команды (латиницей и кириллицей): `/zakazy`, `/zakaz N`, `/novye`,
`/pokupateli`, `/svodka`, `/ostatki`, `/help`.

Обработка ошибок HTTP — по коду, а не «сеть недоступна»:

| Код | Что это | Реакция |
| --- | --- | --- |
| 401 | Токен не принят | `CommandError` с внятным текстом — работать бессмысленно |
| 409 | Тот же бот опрашивается ещё откуда-то | Предупреждение в журнал, пауза 15 с. Обычно бот забыт запущенным на своём компьютере |
| прочее | | Пауза 10 с и повтор |
| сетевые | | Пауза 5 с и повтор — это норма |

Запуск на сервере: сервис `amigo-bot` (`Restart=always`, `RestartSec=10` —
длинные опросы штатно рвут соединение, это не ошибка).

---

## 15. Сервер

### 15.1 Архитектура

```
интернет → Cloudflare → туннель (исходящее соединение с сервера)
                              ↓
                    cloudflared (сервис amigo-tunnel)
                              ↓
                 waitress 127.0.0.1:8000 (сервис amigo)
                              ↓
                  Django + WhiteNoise + SQLite
```

Ubuntu 24.04, отдельный пользователь `amigo`, проект в `/home/amigo/amigo`.
Панель управления (Hestia, cPanel, ISPmanager) **не ставить**: она поднимает
свой веб-сервер, который займёт порт.

### 15.2 Установка (сжатый порядок из `deploy/УСТАНОВКА.md`)

1. Сервер 1–2 ядра / 2 ГБ / 20 ГБ, чистая Ubuntu 24.04, вход по SSH-ключу.
2. `apt update && apt upgrade`; `adduser --disabled-password amigo`;
   ключ в `/home/amigo/.ssh/authorized_keys`; `usermod -aG sudo amigo`;
   `ufw allow OpenSSH && ufw --force enable`; `unattended-upgrades`.
   Только убедившись, что вход по ключу работает: `PasswordAuthentication no`,
   `PermitRootLogin no`, `systemctl restart ssh`.
3. `scp -r . amigo@СЕРВЕР:/home/amigo/amigo`;
   `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`.
4. `cp .env.example .env && nano .env`, сгенерировать ключ:
   `.venv/bin/python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"`.
5. `migrate` → `compilelocales` → `collectstatic --noinput` →
   `seed_facets` → `seed_pages` → (`seed_catalog` только если каталог пуст) →
   `createsuperuser`.
6. Туннель: положить файл ключей в `/home/amigo/.cloudflared/`, поставить
   `cloudflared` из `.deb`. **Пока сервер не заработал, туннель на компьютере
   не выключать** — один туннель может быть запущен в двух местах, Cloudflare
   распределит запросы.
7. Скопировать юниты в `/etc/systemd/system/`, `daemon-reload`,
   `enable --now amigo amigo-tunnel amigo-backup.timer amigo-bot`.
   Проверка: `curl -I http://127.0.0.1:8000/` → 200; `journalctl -u amigo -f`.
8. Доступ в админку: код из Telegram работает сразу. Жёстче — вписать свой
   IP (`https://ifconfig.me`) в `ADMIN_ALLOWED_IPS`. Сменился провайдер —
   `journalctl -u amigo -n 50 | grep Админка` покажет новый адрес.

### 15.3 Юниты

| Юнит | Что | Особенности |
| --- | --- | --- |
| `amigo.service` | `waitress-serve --host=127.0.0.1 --port=8000 --threads=6 config.wsgi:application` | `Restart=always`, песочница (13.4) |
| `amigo-tunnel.service` | `cloudflared tunnel --no-autoupdate --config deploy/cloudflared.yml run` | |
| `amigo-bot.service` | `manage.py telegram_bot` | `RestartSec=10` |
| `amigo-backup.service` + `.timer` | `deploy/backup.sh` в 04:00 | `Persistent=true` — если сервер был выключен, сделает копию после включения |
| `amigo-monitor.service` + `.timer` | `deploy/monitor.sh` каждые 5 мин | `OnBootSec=3min` |

### 15.4 Резервные копии (`deploy/backup.sh`)

```bash
sqlite3 db.sqlite3 ".backup '$DEST/db_$STAMP.sqlite3'"   # не cp!
gzip -f ...
tar -czf media_$STAMP.tar.gz -C "$PROJECT" media
# хранить последние 14 каждого вида
```

**Живую базу нельзя копировать через `cp`** — сайт в это время пишет,
копия может выйти битой. `.backup` делает согласованный снимок.

Копии лежат на том же сервере — от сбоя диска это не спасёт, раз в месяц
их надо забирать к себе (`СКАЧАТЬ-БЭКАПЫ.bat`).

### 15.5 Сторож (`deploy/monitor.sh`)

Проверяет **две точки**: публичный адрес (как его видит покупатель) и
`127.0.0.1:8000` (сам Django). Разница сразу говорит, где искать: если
локально живо, а снаружи нет — упал туннель, а не сайт.

Сообщение уходит **только в момент смены состояния**. Иначе при ночном
падении пришла бы сотня одинаковых сообщений, и их перестали бы читать —
а это ровно то, ради чего сторож ставится. Состояние в
`/home/amigo/.amigo-monitor-state`.

Один неудачный запрос не считается: перед выводом делается повтор через 20 с.

Токен берётся из того же `.env` — отдельно настраивать нечего.

### 15.6 Домен: покупка, делегирование, переезд

Порядок, в котором это делается один раз и больше не трогается.

1. **Купить домен** у любого регистратора. Для `.com.ua` торговая марка не
   нужна, регистрация свободная. Сразу включить двухфакторную защиту в
   кабинете регистратора и автопродление: домен — ключ ко всему остальному,
   его угон тяжелее угона сайта.
2. **Завести зону в Cloudflare** — тот же аккаунт, где живёт туннель.
   Add a site → тариф Free. Cloudflare выдаст два своих NS-сервера.
3. **Переделегировать** — в панели регистратора заменить ВСЕ NS на
   выданные Cloudflare. Оставлять старые нельзя: домен будет отвечать
   то так, то эдак.
4. **Записи туннеля** — в Cloudflare DNS две записи CNAME, обе
   **Proxied** (оранжевое облако, через серое туннель не работает):

   | Тип | Имя | Значение |
   | --- | --- | --- |
   | CNAME | `@` | `<идентификатор туннеля>.cfargotunnel.com` |
   | CNAME | `www` | `<идентификатор туннеля>.cfargotunnel.com` |

   Cloudflare показывает такие записи типом **Tunnel**; в колонке Content
   может стоять `[object Object]` — это косметический глюк их интерфейса,
   не ошибка.
5. **SSL/TLS: Full**, включить **Always Use HTTPS**.
6. **Выключить** тумблер «Block training in robots.txt», если планируете
   отдавать собственный `robots.txt` (см. раздел 22): иначе Cloudflare
   подмешивает свой блок и в файле оказываются две группы `User-agent: *`.
7. **На сервере**: `deploy/cloudflared.yml` — новые `hostname` в `ingress`;
   `.env` — `ALLOWED_HOSTS` с новым доменом **первым** (от первого элемента
   считается `SITE_URL`, а от него — ссылки в письмах, карта сайта и
   адрес, который проверяет сторож). Затем
   `sudo systemctl restart amigo amigo-tunnel`.

**Переезд со старого домена.** Пока не убедились, что новый работает,
старый оставить в `ingress` и в `ALLOWED_HOSTS`. Когда переехали — убрать
обе записи, и запросы на старый адрес начнут падать в заглушку
`http_status:404` внизу `ingress`. Зону старого домена в Cloudflare не
удалять: вернуть его обратно — две строки в конфиге, а заводить зону
заново долго.

**Сколько ждать.** Делегирование `.com.ua` расходится от получаса до
суток. Пока идёт, публичные резолверы могут отдавать `NXDOMAIN` — см.
граблю 18.14, там объяснено, почему это не значит «не работает».

### 15.7 Почта на домене

Задач две, и решаются они разными средствами: принимать письма от
покупателей и отправлять письма от сайта (восстановление пароля).

**Приём — Cloudflare Email Routing**, бесплатно, в той же панели.
Email → Email Routing → Onboard Domain. Cloudflare сам добавит три записи
MX (`route1/2/3.mx.cloudflare.net`), TXT с DKIM (`cf2024-1._domainkey`)
и SPF. Дальше:

1. **Destination Addresses** → добавить ящик, куда пересылать. На него
   придёт письмо с подтверждением — без него пересылка не включится.
   Пока адрес не добавлен, Cloudflare никому ничего не отправляет: список
   назначений пуст, и письма ждать неоткуда.
2. **Routing rules** → правило `info` → ваш ящик.
3. **Catch-all** — по умолчанию выключен и стоит на `Drop`. Включить и
   направить туда же: иначе письмо на `sales@` или с опечаткой в адресе
   исчезает молча, и отправитель считает, что его игнорируют.

**Отправка — SMTP.** Пять строк в серверном `.env`:

```
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=ящик@gmail.com
EMAIL_HOST_PASSWORD=пароль_приложения_16_символов
EMAIL_FROM=АМИГО <info@домен>
```

Пароль приложения создаётся в аккаунте Google при включённой
двухэтапной проверке и вписывается **руками на сервере**, через `nano`.
Не `echo >>` — команда осядет в `~/.bash_history`.

Чтобы в поле «От» стоял адрес на домене, а не gmail, в Gmail нужно
добавить его через «Отправлять письма как» (Настройки → Аккаунты и
импорт), SMTP `smtp.gmail.com:587`, TLS. Код подтверждения придёт через
пересылку из пункта 1.

**SPF и DMARC** — две записи в Cloudflare DNS:

| Тип | Имя | Значение |
| --- | --- | --- |
| TXT | `@` | `v=spf1 include:_spf.mx.cloudflare.net include:_spf.google.com ~all` |
| TXT | `_dmarc` | `v=DMARC1; p=none; rua=mailto:info@домен` |

SPF Cloudflare ставит сам, но только для приёма — Google в него надо
дописать, иначе письма сайта уходят в спам. `p=none` на старте
обязателен: `p=reject` до того, как убедились, что всё сходится,
зарежет собственную почту.

**Честное ограничение этой схемы.** Gmail подписывает письмо ключом
`gmail.com`, а в адресе стоит ваш домен — DKIM-выравнивание не проходит,
и часть писем всё равно попадает в спам. Полностью лечится только
сервисом, который подписывает письма вашим доменом (Brevo, SMTP2GO,
Resend — у всех есть бесплатные тарифы на сотни писем в день). Пока это
не сделано, на странице «письмо отправлено» должна стоять заметная
плашка «загляните в папку Спам» — не строкой в общем тексте, её не
читают.

---

## 16. Рабочий процесс: копия ↔ сервер

Это то, чего обычно нет в спецификациях и без чего проект разваливается
на второй неделе.

### 16.1 Две живые копии и правило владения

| Что | Где главное | Кто правит |
| --- | --- | --- |
| **Код** (python, шаблоны, css, js, миграции) | На компьютере, в папке копии | Разработчик |
| **Содержимое** (товары, цены, описания, страницы, фотографии) | Обычно на сервере, в админке | Владелец |
| **Заявки и учётные записи** | Только на сервере | Появляются сами |

Отсюда правило: **код едет только с компьютера на сервер, содержимое —
только с сервера на компьютер.** Всё остальное — способ затереть чужую работу.

### 16.2 `ОБНОВИТЬ-КОПИЮ.bat` — забрать с сервера

1. `ssh СЕРВЕР "sqlite3 ~/amigo/db.sqlite3 '.backup /tmp/amigo-copy.sqlite3'"`
2. `scp` снимка в `db.sqlite3`, удаление временного файла на сервере
3. `scp -r "СЕРВЕР:/home/amigo/amigo/media/*" "media"`
4. записать дату в `var/last-pull.txt`

**Код не трогает никогда.**

### 16.3 `ОТПРАВИТЬ-НА-СЕРВЕР.bat` — отправить

Шаг 1/5 — код всегда: `tar` из папок
`catalog config core orders pages accounts templates static locale deploy`
+ `manage.py requirements.txt`, `scp`, распаковка с `--overwrite
--no-same-permissions --no-same-owner`. **`.env`, `db.sqlite3` и `media`
в архив не входят.**

Шаг 2/5 — всегда: `pip install -q -r requirements.txt` → `migrate --noinput`
→ `compilelocales` → `collectstatic --noinput`.

Шаги 3–4/5 — **по вопросу Y/N**: переносить ли содержимое.

- Перед вопросом батник печатает дату из `var/last-pull.txt`
  («Копия обновлялась с сервера: …» или «НИ РАЗУ не обновляли»).
- **Локальный `migrate` выполняется до снимка базы** — иначе новые миграции
  уедут с кодом, сервер их применит, а локальная база про них не знает,
  и приём данных справедливо откажется работать.
- Снимок делается через `VACUUM INTO`, а не `cp`.
- Сайт останавливается (`systemctl stop amigo`), запускается
  `manage.py adopt_content db.incoming.sqlite3`, сайт запускается обратно.
  Менять файл SQLite под работающим процессом нельзя. Простой — пара секунд.

Шаг 5/5 — `systemctl restart amigo`.

**Правило ответа, которое надо записать на видном месте:** миграции едут
шагом 2 и применяются всегда, поэтому на вопрос про содержимое почти
всегда **N**. **Y** нужен только когда содержимое менялось вне админки
сервера: массовый импорт, `set_discount`, правки в админке копии.
Ответ **Y** затирает всё, что владелец наменял в админке сервера с момента
последнего `ОБНОВИТЬ-КОПИЮ`.

### 16.4 `adopt_content` — приём базы без потери заявок

Присланная база становится основной, но перед подменой в неё переносятся
таблицы из текущей:

```python
PRESERVE = ["orders_request", "orders_requestline", "auth_user",
            "accounts_profile", "django_session"]
CLEAR = ["django_admin_log"]     # ссылается на записи, которых может не быть
```

Четыре предохранителя, каждый спасал данные:

1. **Сверка миграций.** `SELECT app, name FROM django_migrations` в обеих
   базах; при расхождении — отказ с внятным объяснением, чего где не хватает.
2. **Отказ на пустой базе.** Ноль товаров в присланной — почти наверняка
   ошибка, а не намерение стереть каталог.
3. **Избранное переносится по артикулу, а не по `product_id`.** Номера
   записей в двух базах свои; копирование id отправило бы сердечки на чужие
   товары. Товар, которого в новом каталоге нет, из избранного выпадает.
4. **Прежняя база не удаляется**, а откладывается как
   `db.before-ГГГГ-ММ-ДД_ЧЧ-ММ.sqlite3`. Откат — одна команда.

Перенос идёт через `ATTACH DATABASE ... AS live` с `PRAGMA foreign_keys = OFF`.

### 16.5 Локальный запуск (`ЗАПУСТИТЬ-КОПИЮ.bat`)

Порт **8001**, чтобы копию нельзя было спутать с боевым сайтом.
Проверяет зависимости → `compilelocales` → `makemigrations` → `migrate`
→ `runserver 127.0.0.1:8001` → открывает браузер.
*(В v3: батник миграции только проверяет — `makemigrations --check --dry-run`, инвариант 23.)*

### 16.6 Служебные команды

| Команда | Что |
| --- | --- |
| `seed_catalog` | Демо-каталог |
| `seed_facets` | Строки `FacetGroup` — по одной на справочник |
| `seed_pages` | Информационные страницы |
| `import_supplier --data import/tovary.json --photos import/photos` | Загрузка каталога. **Идемпотентна**: товар ищется по артикулу, найденный обновляется; фото с тем же именем не добавляется дважды; справочники заводятся сами; позиции с `"found": false` создаются скрытыми и с нулевой ценой |
| `set_discount --percent 5 / --revert / --dry-run` | Скидка на весь каталог: текущая цена становится старой, продажная опускается |
| `adopt_content <файл>` | Приём базы |
| `compilelocales` | Сборка переводов |
| `ensure_single_admin` | Оставить одного администратора |
| `telegram_test` | Проверка связи с Telegram |
| `telegram_bot [--once]` | Бот |

### 16.7 Документы для владельца

Проект содержит текстовые инструкции кириллицей рядом с батниками:
`ЧИТАЙ-МЕНЯ.txt` (общая картина и правило «где править каталог»),
`АДМИНКА-как-заходить.txt`, `БОТ-как-включить.txt`,
`ПОЧТА-как-настроить.txt`, `AUTHORS.txt`, `служебные/ЧТО-ЗДЕСЬ.txt`.

Редкие батники вынесены в подпапку `служебные/` (каждый начинается с
`cd /d "%~dp0.."`), чтобы в корне остались только четыре ежедневных.

---

## 17. Проверки и тесты

### 17.1 Честно: в исходном АМИГО автотестов не было

Их отсутствие — не позиция, а долг. В ВОЛЬТ и МИСКА тесты уже есть (67 и 79).
Ниже — то, что реально применялось, и минимальный набор.

### 17.2 Как проверялось на самом деле

| Приём | Чем | Что ловит |
| --- | --- | --- |
| Синтаксис | `python -m py_compile файл.py` | Опечатки, когда Django под рукой нет |
| Данные | прямые запросы `sqlite3` к копии базы | Полноту переводов, пустые описания, конфликты статуса и остатка |
| Вёрстка | скриншот страницы на 1360 px и 430 px | Переполнение, обрезанный текст, сломанную сетку |
| Живой сайт | браузер против копии на 8001 | Всё остальное |
| Миграции данных | «сухой прогон» на копии базы: применить замены на копии файла и посчитать, сколько строк совпало и сколько маркеров осталось | Замены, которые не нашли текст |
| Скидки | `set_discount --dry-run` | Что получится, до того как менять |
| Telegram | `manage.py telegram_test`, `telegram_bot --once` | Токен, chat_id, разбор команд |
| Сервер | `curl -I http://127.0.0.1:8000/`, `journalctl -u amigo -f` | Живость и причину падения |

### 17.3 Проверки, которые надо делать при каждом изменении

1. **Языки.** Переключить УКР/РУС на каталоге, карточке, заявке, кабинете
   и информационной странице. Проверить, что названия товаров украинские
   в обоих режимах.
2. **Каталог без JavaScript.** Отключить JS: фильтры, сортировка,
   пагинация и добавление в заявку обязаны работать.
3. **Сортировка + раздел.** Выбрать раздел, затем сортировку. Убедиться,
   что раздел не потерялся ни в данных, ни в адресной строке.
4. **Нормализация количества.** Ввести 1, 7, 999999 при упаковке 12 и
   остатке 100 — получить 12, 12, 96.
5. **Шлюз админки.** С `ADMIN_GATE_ALLOW_LOCAL=0` на копии: запросить код,
   ввести неверный пять раз, убедиться, что код аннулирован.
6. **Заявка.** Отправить, проверить сообщение в Telegram, номер, письмо
   в журнале, очистку черновика, недоступность чужой страницы «спасибо».
7. **Телефон.** Каталог и баннер на ширине 375–430 px.

### 17.4 Минимальный набор автотестов

```
catalog/tests/test_normalize.py     округление вверх, минимум, потолок, ноль
catalog/tests/test_sorting.py       порядок при sale и new; NULL-ловушка Decimal
catalog/tests/test_filters.py       ?brand=a,b и ?brand=a&brand=b дают одно
catalog/tests/test_banner.py        в разделе 3 своих; в каталоге по одному из разделов
catalog/tests/test_language.py      title даёт name_uk; description_text откатывается
core/tests/test_admin_gate.py       хеш, срок, 5 попыток, пауза, compare_digest
core/tests/test_admin_access.py     таблица решений guarding()
accounts/tests/test_backend.py      iexact, дубль почты, отсутствие тайминг-утечки
orders/tests/test_draft.py          добавление, замена, очистка, итоги
orders/tests/test_request.py        чужая страница «спасибо» → 404
core/tests/test_adopt_content.py    отказ при расхождении миграций и на пустой базе
```

Отдельно — smoke-проверка развёртывания: после `migrate` и `collectstatic`
главная отвечает 200, а `/admin/` без кода — редирект на шлюз.

---

## 18. Грабли: ошибки, которые уже были допущены

Каждый пункт — реальная поломка. Читать до написания кода.

**18.1. `Http404` до сессий = 500 вместо 404.** `AdminAccessMiddleware`
стоял выше `SessionMiddleware`. Своя страница 404 наследует базовый шаблон,
а контекстный процессор черновика читает `request.session`. Итог: вместо
«страницы нет» посетитель получал ошибку сервера. Лечение: обе проверки
админки после сессий + `hasattr(request, "session")` в процессорах.

**18.2. Деление `Decimal` в SQLite даёт NULL.** Сортировка «сначала со
скидкой» молча выдавала 4 %, 6 %, 9 % — то есть сортировала по цене.
Аннотация возвращала NULL по всей колонке, и сортировка сваливалась на
вторичный ключ. Лечение: `Cast(F(...), FloatField())` перед делением.
Общее правило: **любое деление в аннотации SQLite приводить к float явно.**

**18.3. Сортировка теряла раздел.** `action` формы фильтров был жёстко
`{% url 'catalog:index' %}`, а раздел жил только в пути URL. Данные
приходили из корня каталога, но `replaceState` брал
`window.location.pathname` — и адрес выглядел правильным. Симптом:
«сортировка сбрасывает категорию», причём в адресной строке категория
на месте. Лечение: `action` = адрес текущего раздела, `replaceState`
берёт путь из `form.action`.

**18.4. Плейсхолдер внутри f-строки.** Строка
`f"{АМИГО} <{EMAIL_HOST_USER}>"` создала обращение к несуществующему имени.
Пока `EMAIL_HOST_USER` был пуст, ветка не исполнялась — и ошибка ждала
момента, когда владелец заполнит SMTP. Правило: **после любой
автоматической замены текста перечитать получившийся код**, особенно
внутри f-строк.

**18.5. `reverse()` на каждом запросе.** `AdminGateMiddleware` звал
`reverse("admin-gate")` до проверки пути. Отсутствие адреса в `urls.py`
уронило бы весь сайт, а не только админку. Лечение: сначала дешёвая
проверка пути, потом `reverse` в `try/except NoReverseMatch`.

**18.6. Шаблоны печатали `product.name`.** Языковое свойство `title`
существовало, но шаблоны обращались к полю напрямую — украинская версия
показывала русские названия. Лечение: сплошная замена и правило «в шаблонах
только `.title`».

**18.7. Украинский не был главным.** `LANGUAGE_CODE = "uk"` стоял верно,
но `LocaleMiddleware` читает `Accept-Language` раньше — русскоязычные
браузеры получали русскую версию. Лечение: `DefaultLanguageMiddleware`.

**18.8. Деплой падал с «Базы на разной структуре».** Сервер применил новые
миграции, локальная база — нет. Предохранитель сработал правильно.
Лечение: локальный `migrate` внутри батника отправки.

**18.9. Ловушки cmd.** `^` внутри `for /f` съедается; `"media\"` — это
экранированная кавычка, а не путь (`scp` получал `media"`); `%VAR%` внутри
блока `if (...)` подставляется на разборе, до присваивания — читать
переменную надо до блока. Плюс Рабочий стол может быть перенаправлен
в OneDrive, и путь `%USERPROFILE%\Desktop` не существует.

**18.10. Секреты на скриншоте.** `SECRET_KEY` и токен бота попали в чат
картинкой. Урок: не просить показывать `.env` и не открывать его при
демонстрации экрана; для проверки использовать
`grep -o '^[A-Z_]*=' ~/amigo/.env`.

**18.11. Статус и остаток — разные шкалы, и это надо доводить до конца.**
Товар со статусом «Снят с продажи» и остатком 384 шт. показывался в
каталоге как «В наличии»: свойство `stock_label` умело правильно, но
шаблон карточки писал собственное «если остаток есть — в наличии».
Правило: если в модели есть свойство, шаблон обязан звать его, а не
повторять логику.

**18.12. Двойная копия файла между машинами.** Любая правка через
«скачать → изменить → загрузить» создаёт две расходящиеся версии.
Всё, что можно сделать на месте, делается на месте.

**18.13. Django за туннелем не знает, что соединение по HTTPS.**
К Django приходит обычный http с `127.0.0.1`: заголовок о протоколе через
cloudflared не доезжает, и `request.is_secure()` возвращает False. Итог:
в карте сайта, в `canonical` и в `Sitemap:` внутри `robots.txt` оказались
адреса `http://`, а для поисковика `http` и `https` — разные сайты.
Лечение: строить внешние адреса от `settings.SITE_URL`, а не от запроса
(`core/context_processors.py`, функция `site_address`), и задать
`protocol = "https"` в классах карты сайта. `SECURE_PROXY_SSL_HEADER` сам
по себе эту дыру не закрывает.

**18.14. Отрицательный кэш DNS переживает делегирование.** После смены
NS публичный резолвер несколько часов отдавал `NXDOMAIN` — он запомнил
отсутствие домена ещё до регистрации. Запрос того же имени с другим типом
записи кэш обошёл и показал, что делегирование давно прошло. Правило: не
делать вывод «домен не работает» по одному отрицательному ответу —
проверять разные типы записей и разные резолверы.

**18.15. Карта сайта для доменного ресурса Search Console — полным
адресом.** У ресурса типа «домен» (подтверждённого через DNS) нет одного
главного адреса, и поле «Добавьте файл Sitemap» ничего не подставляет:
`sitemap.xml` отклоняется как «Недопустимый адрес», нужен
`https://домен/sitemap.xml` целиком. Статус «Не получено» сразу после
отправки — норма, обновляется в течение суток.

**18.16. Пример в поле ввода устаревает молча.** В блоке «Добавить
списком» placeholder был записан в коде тремя артикулами. Через месяц у
двух остаток обнулился, у третьего количество перестало делиться на
упаковку: человек вставлял подсказку как есть и получал две ошибки и
удвоенный заказ. Правило: если пример состоит из реальных данных, он
должен браться из базы, а не из строки в коде (`QuickListForm.example_text`).

**18.17. Пустой раздел в меню — обещание, которого витрина не выполняет.**
Разделы без товаров показывались в шапке, в подвале, в фильтрах и в
карте сайта; человек заходил и видел голую страницу. Прятать галочкой в
админке — значит не забыть вернуть её, когда товар приедет. Лечение:
`CategoryQuerySet.nonempty()` через `Exists` (и по самому разделу, и по
его подразделам — у родителя своих товаров может не быть), вызывается
везде, где раздел показывается.

**18.18. Одинаковое описание на десятке карточек — тот же дубль, что и
фильтры.** Двенадцать женских товаров получили три текста на всех.
Поисковик считает такие страницы копиями и понижает их вместе. Описание
должно опираться на то, чем товары действительно отличаются: рисунок и
расцветки видно на фотографии, состав и размерный ряд есть в
справочниках. Где фактов не хватает на уникальный текст — честнее
короткое описание, чем размноженная вода.

---

## 19. Порядок сборки с нуля

1. `django-admin startproject config .`, приложения
   `core catalog orders pages accounts`.
2. `core`: `TimeStampedModel`, `NamedModel` со слугами и `title`,
   `utils`, `mixins`, шаблонные теги.
3. `catalog/models.py` целиком, `facets.py` с реестром, `managers.py`.
   Миграции. `seed_facets`, `seed_catalog`.
4. `settings.py` по разделу 4 — **сразу с правильным порядком middleware**.
5. Каталог: `filters.py`, `views.py`, шаблоны, `base.css` + `catalog.css`,
   `core.js` + `catalog.js`.
6. Карточка товара, прайс (`exports.py`).
7. `orders`: черновик, модели, формы, представления, шаблоны, `notify.py`.
8. `accounts`: backend, модели, формы, представления, шаблоны,
   контекстный процессор, восстановление пароля.
9. `pages` + подвал + `seed_pages`.
10. Админка: товары, справочники, `SingleAdminUserAdmin`, `deletion.py`
    + `signals.py`, дашборд, свои шаблоны удаления.
11. Двуязычность: `compilelocales`, `.po` для `uk` и `ru`,
    `DefaultLanguageMiddleware`, `AdminLanguageMiddleware`, переключатель,
    миграции данных с переводами.
12. Защита: `AdminAccessMiddleware`, `admin_gate.py`, страница шлюза,
    404/500.
13. Telegram: уведомления, бот.
14. Деплой: `deploy/*`, `.env.example`, `УСТАНОВКА.md`.
15. Поисковики: `core/sitemaps.py`, `robots_txt`, `canonical` в
    контекстном процессоре и в `base.html` (раздел 22).
16. Батники и текстовые инструкции для владельца.
17. Тесты из 17.4.
18. После первого запуска: домен и почта по разделам 15.6–15.7,
    Search Console по 22.4.

---

## 20. Что намеренно не сделано

Чтобы новая версия не «доделывала» то, от чего отказались осознанно:

- **Оплата на сайте** — бизнес-модель этого не требует.
- **Ступенчатые цены** — были в первом макете, убраны: у магазина одна
  оптовая цена.
- **Размеры и цвета как сущности** — товар продаётся упаковкой-ассорти.
- **PostgreSQL** — нагрузка не требует, обслуживание требует.
- **Сборка фронтенда (webpack/vite)** — владелец должен уметь править CSS.
- **Сторонние библиотеки для XLSX, Telegram, gettext** — см. раздел 2.
- **Вкладка «Характеристики» на карточке** — убрана по требованию владельца
  вместе с частью справочников (`Density`, `Fit`, `Seam`, `Elastic`
  остались в моделях, но выключены из панели подбора).

---

## 21. Что нужно заменить при повторе **[адаптировать]**

| Где | Что |
| --- | --- |
| `settings.SHOP` | Название, телефон, мессенджеры, город склада, минимальная сумма, отсечка |
| `.env` | `SECRET_KEY`, `ALLOWED_HOSTS`, `SITE_URL`, почта, Telegram |
| `deploy/cloudflared.yml` | Идентификатор туннеля и домены |
| `deploy/Caddyfile` | Домены (если без туннеля) |
| `*.bat` | Адрес сервера, имя пользователя |
| `catalog/management/commands/import_supplier.py` | `CATEGORY_TREE` под своё дерево разделов |
| `pages` (миграции/`seed_pages`) | Тексты доставки, оплаты, возврата, политики, реквизиты продавца |
| `locale/uk`, `locale/ru` | Переводы новых строк |
| Шаблон письма восстановления | Подпись магазина |
| Cloudflare | Зона домена, две записи CNAME на туннель, SPF и DMARC |
| Email Routing | Адрес вида `info@`, ящик назначения, catch-all |
| Search Console | Ресурс-домен, карта сайта полным адресом |

---

## 22. Поисковые системы: `robots.txt`, карта сайта, canonical

Три файла-невидимки, без которых каталог для поиска не существует.
Делаются один раз, живут в `core/`.

### 22.1 `canonical` — важнее двух остальных

Каталог с фильтрами открывается по десяткам адресов: `?sort=`, `?q=`,
галки фильтров в произвольном порядке. Товары одни и те же, адрес каждый
раз новый — поисковик видит полсотни страниц-близнецов и понижает их
вместе.

`core/context_processors.py`:

```python
def site_address(request) -> str:
    """Начало всех внешних ссылок. Из SITE_URL, а не из запроса — см. 18.13.
    Заодно склеивает www и адрес без www."""
    return settings.SITE_URL or f"{request.scheme}://{request.get_host()}"


def canonical(request) -> dict:
    page = request.GET.get("page", "")
    suffix = f"?page={page}" if page.isdigit() and page != "1" else ""
    return {"site_url": site_address(request),
            "canonical_url": f"{site_address(request)}{request.path}{suffix}"}
```

В `base.html`: `<link rel="canonical" href="{{ canonical_url }}">`,
`<meta property="og:url" content="{{ canonical_url }}">`, и `og:image`
через `{{ site_url }}`, а не через `request.scheme`.

**Номер страницы в адресе сохраняется намеренно.** Вторая страница
списка — это другие товары; склеив её с первой, вы прячете полкаталога.

### 22.2 Карта сайта

`core/sitemaps.py`. Базовый класс задаёт протокол, четыре наследника —
главная, разделы, товары, информационные страницы:

```python
class HttpsSitemap(Sitemap):
    @property
    def protocol(self) -> str | None:
        return None if settings.DEBUG else "https"
```

Разделы и товары фильтруются через `active()` / `published()`, разделы —
ещё и `nonempty()` (грабля 18.17). `lastmod` берётся из `updated_at`.

В `config/urls.py` — **оглавление**, а не одна карта:

```python
path("sitemap.xml", sitemap_index,
     {"sitemaps": SITEMAPS, "sitemap_url_name": "sitemap-section"}, name="sitemap"),
path("sitemap-<section>.xml", sitemap, {"sitemaps": SITEMAPS}, name="sitemap-section"),
```

Лишний слой нужен на вырост: в одну карту помещается ограниченное число
адресов, и когда товаров станет больше предела, обычная карта молча
разобьётся на страницы — поисковик увидит первую и о новых товарах не
узнает.

`django.contrib.sitemaps` добавляется в `INSTALLED_APPS` ради шаблонов;
своих таблиц он не создаёт. `django.contrib.sites` **не нужен**: без него
домен берётся из запроса, и карта переезжает вместе с сайтом.

### 22.3 `robots.txt`

Отдаётся представлением (`core/views.py`), а не лежит в статике: в нём
должен быть полный адрес карты сайта, а он строится от `SITE_URL`.

Закрывать только служебное: `/admin/`, шлюз перед админкой, `/kabinet/`,
`/zakaz/`, `/price/`, `/i18n/`. **Страницы каталога с фильтрами не
закрывать** — запрет помешает роботу дойти до самих карточек, а дубли
уже решены через `canonical`.

### 22.4 Search Console

1. Добавить ресурс типа **«Домен»** и подтвердить DNS-записью — так один
   ресурс покрывает `www`, без `www` и оба протокола.
2. Отправить карту сайта **полным адресом** (грабля 18.15).
3. Проверка URL → главная → «Запросить индексирование». Повторно жать
   бесполезно: очередь от этого не движется.

Сроки, которые надо назвать владельцу заранее: сканирование — часы,
индексация главной — от суток до недели, остальные страницы — недели.
По конкурентным запросам («білизна оптом») новый домен не поднимется
месяцами; первыми приходят запросы по артикулам и длинные точные.

---

*Составлено по рабочему коду проекта АМИГО. Автор кода и решений — ISHOD, 2026.*
