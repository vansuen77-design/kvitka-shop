"""Settings for KVITKA — a flower shop with delivery.

Two modes:

* local — the site is available only on this computer (start.bat);
* public — the site is reachable from the internet through the tunnel
  (PUBLIC=1 on the server).

The second is enabled by the .env file next to manage.py. It must never
end up in archives or git: it holds the secret key.

Code by ISHOD, 2026. All rights to the source code belong to the author.
"""

import ipaddress
import os
import secrets
import string
import warnings
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def read_env(path: Path) -> dict:
    """Simple .env parsing — no third-party libraries.

    Lines of the form KEY=value; empty lines and lines starting with # are skipped.
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
    """A key for a local run when .env does not exist yet."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*(-_=+)"
    return "".join(secrets.choice(alphabet) for _ in range(50))


# --- operating mode -------------------------------------------------------
# PUBLIC=1 in .env — the site faces the internet: debug off, cookies over
# HTTPS only, domains listed explicitly.
PUBLIC = env_flag("PUBLIC", False)
DEBUG = not PUBLIC

SECRET_KEY = env("SECRET_KEY") or (
    "django-insecure-local-only" if DEBUG else make_secret_key()
)

# Domains Django accepts requests for.
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS") or (
    ["*"] if DEBUG else ["localhost", "127.0.0.1"]
)

# Cloudflare serves the site over HTTPS but talks to us over HTTP —
# without this line Django would think the connection is insecure.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

def _origin(host: str) -> str:
    # an entry like .trycloudflare.com means "any subdomain"
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
    # needed only for the sitemap templates; creates no tables of its own
    "django.contrib.sitemaps",
    "core.apps.CoreConfig",
    "catalog.apps.CatalogConfig",
    "orders.apps.OrdersConfig",
    "pages.apps.PagesConfig",
    "accounts.apps.AccountsConfig",
]

# --- admin panel ----------------------------------------------------------
# Who reaches /admin/. Everyone else gets a 404 from the server, as if the
# page did not exist (see core/middleware.AdminAccessMiddleware).
#
# ADMIN_ALLOWED_IPS in .env — your addresses, comma-separated. Subnets are
# allowed too: 91.203.10.55, 178.94.0.0/16, 2a02:1810::/32
# Empty list — no admin from outside for anyone; the SSH tunnel entrance
# remains and always works.
ADMIN_PATH = "/admin"

# Absolute site address — needed where there is no request to build a link
# from: e.g. in the order notification sent to Telegram.
SITE_URL = env("SITE_URL") or (
    f"https://{ALLOWED_HOSTS[0]}" if ALLOWED_HOSTS and ALLOWED_HOSTS[0] not in ("*", "localhost", "127.0.0.1") else ""
)

# Order notifications. Empty — notifications are simply not sent, the site
# does not suffer. The token lives in .env and never in the code.
TELEGRAM = {
    "TOKEN": env("TELEGRAM_BOT_TOKEN"),
    "CHAT_ID": env("TELEGRAM_CHAT_ID"),
}
# Admin from the server only. When enabled, /admin/ does not exist for
# anyone outside; the single entrance is the SSH tunnel
#
#     ssh -L 8000:127.0.0.1:8000 kvitka@SERVER
#     then http://127.0.0.1:8000/admin/
#
# The admin password then plays no part in the protection at all: the
# login form cannot be reached from the internet. ADMIN_ALLOWED_IPS is
# ignored entirely in this mode — an address left there opens nothing.
#
# Need browser access — ADMIN_LOCAL_ONLY=0 in .env and addresses in
# ADMIN_ALLOWED_IPS.
ADMIN_LOCAL_ONLY = env_flag("ADMIN_LOCAL_ONLY", False)
ADMIN_ACCESS_BY_IP = env_flag("ADMIN_ACCESS_BY_IP", True)

# --- admin login with a code from Telegram --------------------------------
# The admin is open from the internet, but a gate stands before the login
# form: until the session carries a "code entered" mark, a "send me the
# code" page is shown instead of the admin. The code goes to the owner's
# Telegram.
#
# Two steps as a result: an attacker knows the password — the code still
# does not reach them. Details and the reasoning behind the timings —
# core/admin_gate.py
ADMIN_TELEGRAM_GATE = env_flag("ADMIN_TELEGRAM_GATE", True)
ADMIN_GATE_CODE_SECONDS = 300      # how long a code lives
ADMIN_GATE_HOURS = 12              # how long we do not ask again afterwards
ADMIN_GATE_RESEND_SECONDS = 45     # a new code no more often than this
# Requests from the server itself need no code — that is the SSH tunnel
# entrance. On the local copy set 0 in .env to test the gate.
ADMIN_GATE_ALLOW_LOCAL = env_flag("ADMIN_GATE_ALLOW_LOCAL", True)
ADMIN_ALLOWED_IPS = env_list("ADMIN_ALLOWED_IPS")



def parse_networks(values: list[str]) -> list:
    """"91.203.10.55, 10.0.0.0/8" → a list of networks. Garbage is skipped.

    Parsed once at startup, not on every request. Here rather than in the
    middleware so that settings do not pull in application code.
    """
    networks = []
    for raw in values:
        try:
            networks.append(ipaddress.ip_network(raw.strip(), strict=False))
        except ValueError:
            warnings.warn(f"ADMIN_ALLOWED_IPS: cannot parse address {raw!r}")
    return networks


ADMIN_ALLOWED_NETWORKS = parse_networks(ADMIN_ALLOWED_IPS)

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # serves css and js itself, with caching and compression: on the server
    # only the tunnel stands in front of Django, nobody else serves static
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    # Both admin checks come AFTER sessions, and that is not a matter of taste.
    # AdminAccess refuses via Http404, and our 404 page is custom, with the
    # header and the cart. The cart lives in the session — and if the refusal
    # happened before SessionMiddleware, the refusal page itself would crash
    # and the visitor would get a 500 instead of a 404. That is what happened.
    "core.middleware.AdminAccessMiddleware",
    # the Telegram code gate — right here, it needs the session
    "core.admin_gate.AdminGateMiddleware",
    # visitor language: cookie -> LANGUAGE_CODE (Ukrainian).
    # The browser language is deliberately ignored — why is explained in
    # DefaultLanguageMiddleware. It must come before Locale.
    "core.middleware.DefaultLanguageMiddleware",
    # Position matters: after sessions and necessarily before CommonMiddleware.
    "django.middleware.locale.LocaleMiddleware",
    # the storefront is bilingual, the admin is always Russian
    "core.middleware.AdminLanguageMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

if DEBUG:
    # so that the browser does not show a stale page after edits
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

# --- customer account -----------------------------------------------------
# The login is the e-mail. No custom user model: username is simply filled
# with the same e-mail, and EmailBackend checks them. The standard
# ModelBackend stays second — the administrator logs in with it by username.
AUTHENTICATION_BACKENDS = [
    "accounts.backends.EmailBackend",
    "django.contrib.auth.backends.ModelBackend",
]

LOGIN_URL = "/kabinet/vhod/"
LOGIN_REDIRECT_URL = "/kabinet/"
LOGOUT_REDIRECT_URL = "/"

# The password reset link lives three hours: the e-mail may sit in the
# inbox for a while, but a day for a "log in without a password" link is
# too long.
PASSWORD_RESET_TIMEOUT = 60 * 60 * 3

# --- e-mail ---------------------------------------------------------------
# Needed for password reset e-mails and order confirmations.
#
# While EMAIL_HOST in .env is empty, e-mails are printed to the log
# (journalctl -u kvitka) and go nowhere — the site keeps working.
# Filled in — they are really sent. The app password lives only in .env,
# never in the code.
EMAIL_HOST = env("EMAIL_HOST")
EMAIL_PORT = int(env("EMAIL_PORT", "587") or 587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")
# 465 is SSL from the first byte, 587 is a plain connection upgraded to TLS
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

# --- site languages -------------------------------------------------------
# The site is bilingual. Template texts are written in Russian — that is
# the msgid, and the Ukrainian translation lives in
# locale/uk/LC_MESSAGES/django.po (compiled by manage.py compilelocales).
#
# Which language the visitor sees is decided by LocaleMiddleware in this order:
#   1. the django_language cookie — if the person used the switcher;
#   2. the Accept-Language header — i.e. the browser language;
#   3. LANGUAGE_CODE below — for everyone else.
LANGUAGES = [
    ("uk", "Українська"),
    ("ru", "Русский"),
]
# The main site language. Everyone who never used the switcher sees it:
# the Accept-Language header is deliberately not read (see MIDDLEWARE).
LANGUAGE_CODE = "uk"
LOCALE_PATHS = [BASE_DIR / "locale"]

# a year: the language choice must not reset the next day
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
        # compresses css and js at collection time. File versions are set by
        # our versioned tag from the modification time, so the hashed-names
        # variant is not used: it breaks the page if a file was not collected
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# --- logging --------------------------------------------------------------
# Written to standard output: systemd picks it up and stores it in journalctl.
# View with:  journalctl -u kvitka -f
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
        # admin refusals are always visible: they show that a new address
        # needs adding to ADMIN_ALLOWED_IPS
        "kvitka": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "django.request": {"handlers": ["console"], "level": "WARNING",
                           "propagate": False},
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- shop settings --------------------------------------------------------
# Keys with the _UK suffix replace the main ones on the Ukrainian version
# of the site (see orders/context_processors.shop_settings).
# Demo values: the owner changes the name, phone and address here, and the
# domain and e-mail in .env.
SHOP = {
    "NAME": "КВІТКА",
    "TAGLINE": "цветы с доставкой по Одессе",
    "TAGLINE_UK": "квіти з доставкою по Одесі",
    "PHONE": "+38 (0XX) XXX-XX-XX",
    "MANAGER": "Оксана",
    "MANAGER_UK": "Оксана",
    "CITY": "Одесса",
    "CITY_UK": "Одеса",
    # opening hours: shown in the top bar and the footer.
    # A string, not a schedule: parsing "Mon–Sun 8–21" in code would be
    # work for its own sake.
    "HOURS": "ежедневно 8:00–21:00",
    "HOURS_UK": "щодня 8:00–21:00",
    "ADDRESS": "ул. Дерибасовская, 1",
    "ADDRESS_UK": "вул. Дерибасівська, 1",
    "EMAIL": "hello@kvitka.example",
    "TELEGRAM": "https://t.me/",
    "VIBER": "viber://chat?number=380000000000",
    "WHATSAPP": "https://wa.me/380000000000",
    "INSTAGRAM": "https://instagram.com/",
    "DELIVERY_COST": 150,           # courier within the city, ₴
    "FREE_DELIVERY_FROM": 1500,     # free delivery from, ₴
    "DELIVERY_HOURS": "2–3 часа",   # how soon we deliver after confirmation
    "DELIVERY_HOURS_UK": "2–3 години",
    "CURRENCY": "₴",
}

# --- authorship -----------------------------------------------------------
# Code author mark. Kept in settings rather than a template because from
# here it is visible both in code and anywhere it needs to be output:
#     from django.conf import settings; settings.BUILT_BY
# Does not affect the site's appearance in any way.
BUILT_BY = "ISHOD"
BUILT_YEAR = "2026"
CODE_NOTICE = "KVITKA shop engine — code by ISHOD, 2026. All rights reserved."

CART_SESSION_KEY = "kvitka_cart"
CATALOG_PAGE_SIZE = 12
