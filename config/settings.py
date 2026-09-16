"""Настройки проекта «КВІТКА» — магазин цветов с доставкой.

Два режима:

* обычный — сайт открыт только на этом компьютере (ЗАПУСТИТЬ.bat);
* публичный — сайт виден в интернете через туннель (ОТКРЫТЬ-В-ИНТЕРНЕТ.bat).

Второй включается файлом .env рядом с manage.py. Он не должен попадать
ни в архивы, ни в git: в нём секретный ключ.

Автор кода: ISHOD, 2026. Все права на исходный код принадлежат автору.
"""

import ipaddress
import os
import secrets
import string
import warnings
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def read_env(path: Path) -> dict:
    """Простой разбор .env — без сторонних библиотек.

    Строки вида КЛЮЧ=значение, пустые и начинающиеся с # пропускаются.
    """
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


ENV = read_env(BASE_DIR / ".env")


def env(name: str, default: str = "") -> str:
    return os.environ.get(name) or ENV.get(name) or default


def env_flag(name: str, default: bool = False) -> bool:
    raw = env(name, "1" if default else "0").lower()
    return raw in ("1", "true", "yes", "on", "да")


def env_list(name: str) -> list[str]:
    return [item.strip() for item in env(name).split(",") if item.strip()]


def make_secret_key() -> str:
    """Ключ для локального запуска, если .env ещё не создан."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*(-_=+)"
    return "".join(secrets.choice(alphabet) for _ in range(50))


# --- режим работы --------------------------------------------------------
# PUBLIC=1 в .env — сайт смотрит в интернет: отладка выключена,
# куки только по HTTPS, домены перечислены явно.
PUBLIC = env_flag("PUBLIC", False)
DEBUG = not PUBLIC

SECRET_KEY = env("SECRET_KEY") or (
    "django-insecure-local-only" if DEBUG else make_secret_key()
)

# Домены, с которых Django принимает запросы.
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS") or (
    ["*"] if DEBUG else ["localhost", "127.0.0.1"]
)

# Cloudflare отдаёт сайт по HTTPS, а к нам стучится по HTTP —
# без этой строки Django будет думать, что соединение незащищённое.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

def _origin(host: str) -> str:
    # запись вида .trycloudflare.com означает «любой поддомен»
    return f"https://*{host}" if host.startswith(".") else f"https://{host}"


CSRF_TRUSTED_ORIGINS = [
    _origin(host) for host in ALLOWED_HOSTS
    if host not in ("*", "localhost", "127.0.0.1")
]

if PUBLIC:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    X_FRAME_OPTIONS = "DENY"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # нужен только ради шаблонов карты сайта; своих таблиц не создаёт
    "django.contrib.sitemaps",
    "core.apps.CoreConfig",
    "catalog.apps.CatalogConfig",
    "orders.apps.OrdersConfig",
    "pages.apps.PagesConfig",
    "accounts.apps.AccountsConfig",
]

# --- админка ------------------------------------------------------------
# Кто попадёт на /admin/. Всем остальным сервер отвечает 404, будто такой
# страницы нет (см. core/middleware.AdminAccessMiddleware).
#
# ADMIN_ALLOWED_IPS в .env — ваши адреса через запятую. Можно указывать
# и подсети: 91.203.10.55, 178.94.0.0/16, 2a02:1810::/32
# Пустой список — снаружи админки нет ни для кого; остаётся вход через
# SSH-туннель, он работает всегда.
ADMIN_PATH = "/admin"

# Полный адрес сайта — нужен там, где ссылку некому построить из запроса:
# например в уведомлении о заказе, которое уходит в Telegram.
SITE_URL = env("SITE_URL") or (
    f"https://{ALLOWED_HOSTS[0]}" if ALLOWED_HOSTS and ALLOWED_HOSTS[0] not in ("*", "localhost", "127.0.0.1") else ""
)

# Уведомления о заказах. Пусто — уведомления просто не отправляются,
# сайт от этого не страдает. Токен живёт в .env и в код не попадает.
TELEGRAM = {
    "TOKEN": env("TELEGRAM_BOT_TOKEN"),
    "CHAT_ID": env("TELEGRAM_CHAT_ID"),
}
# Админка только с самого сервера. По умолчанию включено: снаружи
# /admin/ не существует ни для кого, вход остаётся один — SSH-туннель
#
#     ssh -L 8000:127.0.0.1:8000 kvitka@СЕРВЕР
#     затем http://127.0.0.1:8000/admin/
#
# Так пароль от админки вообще не участвует в защите: до формы входа
# из интернета не дойти. Список ADMIN_ALLOWED_IPS в этом режиме не
# смотрится совсем — случайно оставленный там адрес ничего не откроет.
#
# Понадобится заходить из браузера — ADMIN_LOCAL_ONLY=0 в .env и адреса
# в ADMIN_ALLOWED_IPS.
ADMIN_LOCAL_ONLY = env_flag("ADMIN_LOCAL_ONLY", False)
ADMIN_ACCESS_BY_IP = env_flag("ADMIN_ACCESS_BY_IP", True)

# --- вход в админку по коду из Telegram ---------------------------------
# Админка открыта из интернета, но перед формой входа стоит шлюз: пока
# в сессии нет отметки о введённом коде, вместо админки показывается
# страница «пришлите код». Код уходит в Telegram владельцу.
#
# Получается две ступени: пароль знает злоумышленник — код всё равно
# приходит не ему. Подробности и обоснование сроков — core/admin_gate.py
ADMIN_TELEGRAM_GATE = env_flag("ADMIN_TELEGRAM_GATE", True)
ADMIN_GATE_CODE_SECONDS = 300      # сколько живёт код
ADMIN_GATE_HOURS = 12              # сколько потом не спрашиваем заново
ADMIN_GATE_RESEND_SECONDS = 45     # не чаще, чем раз в столько, шлём новый
# Запросы с самого сервера кода не требуют — это вход по SSH-туннелю.
# На копии поставьте 0 в .env, чтобы проверить шлюз у себя.
ADMIN_GATE_ALLOW_LOCAL = env_flag("ADMIN_GATE_ALLOW_LOCAL", True)
ADMIN_ALLOWED_IPS = env_list("ADMIN_ALLOWED_IPS")



def parse_networks(values: list[str]) -> list:
    """«91.203.10.55, 10.0.0.0/8» → список сетей. Мусор пропускаем.

    Разбираем один раз при старте, а не на каждом запросе. Здесь, а не
    в middleware, чтобы настройки не тянули за собой код приложения.
    """
    networks = []
    for raw in values:
        try:
            networks.append(ipaddress.ip_network(raw.strip(), strict=False))
        except ValueError:
            warnings.warn(f"ADMIN_ALLOWED_IPS: не понял адрес {raw!r}")
    return networks


ADMIN_ALLOWED_NETWORKS = parse_networks(ADMIN_ALLOWED_IPS)

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # раздаёт css и js сам, с кэшированием и сжатием: на сервере перед
    # Django стоит только туннель, отдавать статику больше некому
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    # Обе проверки админки — ПОСЛЕ сессий, и это не вкусовщина.
    # AdminAccess отказывает через Http404, а страница 404 у нас своя,
    # с шапкой и корзиной. Корзина живёт в сессии — и если отказ
    # случился раньше SessionMiddleware, страница отказа падает сама,
    # и посетитель получает 500 вместо 404. Так и было.
    "core.middleware.AdminAccessMiddleware",
    # шлюз с кодом из Telegram — здесь же, ему сессия нужна прямо
    "core.admin_gate.AdminGateMiddleware",
    # язык посетителя: кука -> LANGUAGE_CODE (украинский).
    # Язык браузера намеренно не смотрим — почему, написано
    # в DefaultLanguageMiddleware. Она обязана стоять до Locale.
    "core.middleware.DefaultLanguageMiddleware",
    # Место важно: после сессий и обязательно до CommonMiddleware.
    "django.middleware.locale.LocaleMiddleware",
    # витрина двуязычная, а админка всегда русская
    "core.middleware.AdminLanguageMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

if DEBUG:
    # чтобы браузер не показывал старую версию страницы после правок
    MIDDLEWARE.append("core.middleware.NoCacheMiddleware")

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.template.context_processors.i18n",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.navigation",
                "core.context_processors.canonical",
                "orders.context_processors.cart_summary",
                "pages.context_processors.footer_links",
                "accounts.context_processors.cabinet",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- кабинет покупателя -------------------------------------------------
# Логин — это почта. Своей модели пользователя нет: username мы просто
# заполняем той же почтой, а сверяет их EmailBackend. Стандартный
# ModelBackend оставляем вторым — им входит администратор по логину.
AUTHENTICATION_BACKENDS = [
    "accounts.backends.EmailBackend",
    "django.contrib.auth.backends.ModelBackend",
]

LOGIN_URL = "/kabinet/vhod/"
LOGIN_REDIRECT_URL = "/kabinet/"
LOGOUT_REDIRECT_URL = "/"

# Ссылка на смену пароля живёт три часа: письмо могло полежать в почте,
# но сутки для ссылки «войти без пароля» — это слишком долго.
PASSWORD_RESET_TIMEOUT = 60 * 60 * 3

# --- почта ---------------------------------------------------------------
# Нужна ровно для одного: письма «восстановить пароль».
#
# Пока EMAIL_HOST в .env не заполнен, письма печатаются в журнал
# (journalctl -u kvitka) и никуда не уходят — сайт при этом работает.
# Заполнили — уходят по-настоящему. Пароль приложения хранится только
# в .env, в коде его нет.
EMAIL_HOST = env("EMAIL_HOST")
EMAIL_PORT = int(env("EMAIL_PORT", "587") or 587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")
# 465 — это SSL с первого байта, 587 — обычное соединение с переходом на TLS
EMAIL_USE_SSL = EMAIL_PORT == 465
EMAIL_USE_TLS = not EMAIL_USE_SSL
EMAIL_TIMEOUT = 20
DEFAULT_FROM_EMAIL = env("EMAIL_FROM") or (
    f"КВІТКА <{EMAIL_HOST_USER}>" if EMAIL_HOST_USER else "kvitka@localhost"
)
EMAIL_BACKEND = (
    "django.core.mail.backends.smtp.EmailBackend" if EMAIL_HOST
    else "django.core.mail.backends.console.EmailBackend"
)

# --- языки сайта --------------------------------------------------------
# Сайт двуязычный. Тексты в шаблонах написаны по-русски — это msgid,
# а перевод на украинский лежит в locale/uk/LC_MESSAGES/django.po
# (собирается командой manage.py compilelocales).
#
# Какой язык увидит посетитель, решает LocaleMiddleware в таком порядке:
#   1. кука django_language — если человек нажимал переключатель;
#   2. заголовок Accept-Language — то есть язык его браузера;
#   3. LANGUAGE_CODE ниже — для всех остальных.
LANGUAGES = [
    ("uk", "Українська"),
    ("ru", "Русский"),
]
# Главный язык сайта. Его же видят все, кто не нажимал переключатель:
# заголовок Accept-Language мы намеренно не читаем (см. MIDDLEWARE).
LANGUAGE_CODE = "uk"
LOCALE_PATHS = [BASE_DIR / "locale"]

# год: выбор языка не должен слетать на следующий день
LANGUAGE_COOKIE_AGE = 60 * 60 * 24 * 365
LANGUAGE_COOKIE_SAMESITE = "Lax"

TIME_ZONE = "Europe/Kyiv"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        # сжимает css и js при сборке. Версии файлов проставляет наш
        # тег versioned по времени изменения, поэтому вариант с хешами
        # в именах не берём: он ломает страницу, если файл забыли собрать
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# --- журнал --------------------------------------------------------------
# Пишем в стандартный вывод: systemd подхватит и сложит в journalctl.
# Смотреть так:  journalctl -u kvitka -f
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "{asctime} {levelname} {name}: {message}",
                   "style": "{", "datefmt": "%d.%m %H:%M:%S"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": "WARNING"},
    "loggers": {
        # отказы в админке видно всегда: по ним понятно, что нужно
        # добавить новый адрес в ADMIN_ALLOWED_IPS
        "kvitka": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "django.request": {"handlers": ["console"], "level": "WARNING",
                           "propagate": False},
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Настройки магазина -------------------------------------------------
# Ключи с суффиксом _UK подменяют основные на украинской версии сайта
# (см. orders/context_processors.shop_settings).
# Значения демонстрационные: название, телефон и адрес владелец меняет
# здесь, а домен и почту — в .env.
SHOP = {
    "NAME": "КВІТКА",
    "TAGLINE": "цветы с доставкой по Одессе",
    "TAGLINE_UK": "квіти з доставкою по Одесі",
    "PHONE": "+38 (0XX) XXX-XX-XX",
    "MANAGER": "Оксана",
    "MANAGER_UK": "Оксана",
    "CITY": "Одесса",
    "CITY_UK": "Одеса",
    # часы работы: показываются в верхней полосе и в подвале.
    # Строкой, а не расписанием: разбирать «пн–вс 8–21» в коде —
    # работа ради работы.
    "HOURS": "ежедневно 8:00–21:00",
    "HOURS_UK": "щодня 8:00–21:00",
    "ADDRESS": "ул. Дерибасовская, 1",
    "ADDRESS_UK": "вул. Дерибасівська, 1",
    "EMAIL": "hello@kvitka.example",
    "TELEGRAM": "https://t.me/",
    "VIBER": "viber://chat?number=380000000000",
    "WHATSAPP": "https://wa.me/380000000000",
    "INSTAGRAM": "https://instagram.com/",
    "DELIVERY_COST": 150,           # курьер по городу, ₴
    "FREE_DELIVERY_FROM": 1500,     # бесплатная доставка от, ₴
    "DELIVERY_HOURS": "2–3 часа",   # сколько везём после подтверждения
    "DELIVERY_HOURS_UK": "2–3 години",
    "CURRENCY": "₴",
}

# --- авторство -----------------------------------------------------------
# Метка автора кода. Лежит в настройках, а не в шаблоне, потому что
# отсюда её видно и в коде, и в любом месте, где понадобится вывести:
#     from django.conf import settings; settings.BUILT_BY
# На внешний вид сайта не влияет никак.
BUILT_BY = "ISHOD"
BUILT_YEAR = "2026"
CODE_NOTICE = "KVITKA shop engine — code by ISHOD, 2026. All rights reserved."

CART_SESSION_KEY = "kvitka_cart"
CATALOG_PAGE_SIZE = 12
