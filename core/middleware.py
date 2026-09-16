"""Служебные middleware.
Автор кода: ISHOD, 2026. Все права на исходный код принадлежат автору.
"""

import ipaddress
import logging

from django.conf import settings
from django.http import Http404
from django.utils import translation
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger("kvitka")


class NoCacheMiddleware(MiddlewareMixin):
    """Запрещает браузеру кэшировать страницы.

    При разработке браузер охотно показывает страницу из своего кэша —
    и после обновления сайта видна старая вёрстка, пока не нажмёшь
    Ctrl+F5. Включается только при DEBUG (см. config/settings.py).
    """

    def process_response(self, request, response):
        response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"
        return response


class AdminAccessMiddleware(MiddlewareMixin):
    """Пускает в админку только с разрешённых IP-адресов.

    Сайт открыт всему интернету, а значит адрес /admin/ виден всем и
    пароль остаётся единственной защитой. Подбирать его будут роботы,
    круглосуточно. Поэтому до формы входа доходят только свои.

    ОТКУДА БЕРЁТСЯ IP. Сайт стоит за туннелем Cloudflare, поэтому
    соединение до Django всегда приходит с 127.0.0.1 — по нему отличить
    посетителей невозможно. Настоящий адрес Cloudflare кладёт в заголовок
    CF-Connecting-IP, его и проверяем.

    ПОЧЕМУ ЗАГОЛОВКУ МОЖНО ВЕРИТЬ. Обычно заголовок можно подделать, но
    здесь нет: сервер слушает только 127.0.0.1, наружу не торчит ни один
    порт, и единственный путь к нему — туннель. А в туннеле Cloudflare
    переписывает CF-Connecting-IP своим значением, что бы ни прислал
    клиент. Если вы уйдёте от туннеля и откроете порт наружу, эту
    проверку нужно будет переделать — см. deploy/УСТАНОВКА.md.

    ЗАПАСНОЙ ВХОД. Запросы с самого сервера (127.0.0.1) проходят всегда.
    Это не дыра: попасть на loopback снаружи нельзя, зато можно пробросить
    порт по SSH и открыть админку так, даже если ваш IP сменился:

        ssh -L 8000:127.0.0.1:8000 kvitka@СЕРВЕР
        затем http://127.0.0.1:8000/admin/ в браузере

    НАСТРОЙКА. Обычный режим: адрес не проверяем, но перед админкой
    стоит шлюз с одноразовым кодом из Telegram (core/admin_gate.py).
    Пароль плюс код — две ступени, и вторая приходит только владельцу.

    Можно и жёстче, через .env:

        ADMIN_ALLOWED_IPS=91.203.10.55, 2a02:1810::/32
            пускаем только с этих адресов, и там ещё спросят код

        ADMIN_LOCAL_ONLY=1
            снаружи админки нет вовсе, вход только по SSH-туннелю
    """

    HEADER = "HTTP_CF_CONNECTING_IP"

    def client_ip(self, request) -> str:
        """Адрес посетителя: из заголовка Cloudflare, иначе — самого соединения."""
        header = request.META.get(self.HEADER, "")
        if header:
            # заголовок бывает списком: первый адрес — исходный клиент
            return header.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "")

    def is_allowed(self, address: str) -> bool:
        if not address:
            return False
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            return False
        if ip.is_loopback:
            return True
        # режим «только локально»: список адресов не смотрим вообще,
        # чтобы забытая в .env строка не открыла админку наружу
        if settings.ADMIN_LOCAL_ONLY:
            return False
        return any(ip in network for network in settings.ADMIN_ALLOWED_NETWORKS)

    def guarding(self) -> bool:
        """Стоит ли вообще проверять адрес.

        Три случая:

        * ADMIN_LOCAL_ONLY — проверяем всегда, снаружи админки нет;
        * список ADMIN_ALLOWED_IPS заполнен — проверяем по нему;
        * список пуст и включён шлюз с кодом из Telegram — не проверяем.
          Иначе получилось бы, что до шлюза никто не доходит: адрес
          отсекается раньше, и код спросить не у кого.

        Если же и списка нет, и шлюз выключен — админка осталась бы
        открытой всему интернету под одним паролем. Так не делаем:
        в этом случае пускаем только с самого сервера.
        """
        if settings.ADMIN_LOCAL_ONLY:
            return True
        if not settings.ADMIN_ACCESS_BY_IP:
            return False
        if settings.ADMIN_ALLOWED_NETWORKS:
            return True
        from core.admin_gate import enabled as gate_enabled
        return not gate_enabled()

    def process_request(self, request):
        if not self.guarding():
            return None
        if not request.path.startswith(settings.ADMIN_PATH):
            return None

        address = self.client_ip(request)
        if self.is_allowed(address):
            return None

        # адрес пишем в журнал: сменился провайдер или вы из другого места —
        # посмотрите строку в логе и добавьте адрес в .env
        logger.warning("Админка: отказано адресу %s (%s)", address or "неизвестен",
                       request.path)
        # 404, а не 403: пусть выглядит так, будто админки здесь нет
        raise Http404


class DefaultLanguageMiddleware(MiddlewareMixin):
    """Украинский по умолчанию, что бы ни стояло в браузере.

    Django сам выбирает язык так: кука → заголовок Accept-Language →
    LANGUAGE_CODE. Средний шаг для украинского магазина вреден: у многих
    покупателей браузер русский, и они попадали на русскую версию, даже
    не зная, что украинская есть.

    Поэтому Accept-Language выключаем: язык берётся из куки, а если
    человек переключателем не пользовался — украинский.

    Выбор посетителя при этом уважаем полностью: нажал РУС — кука
    поставлена, и дальше сайт русский, пока он сам не передумает.

    Стоит ДО LocaleMiddleware — тот читает уже подчищенный заголовок.
    """

    HEADER = "HTTP_ACCEPT_LANGUAGE"

    def process_request(self, request):
        if request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME):
            return None      # выбор сделан руками — не вмешиваемся
        request.META.pop(self.HEADER, None)
        return None


class AdminLanguageMiddleware(MiddlewareMixin):
    """Держит админку на русском, что бы ни стояло в браузере.

    Витрина двуязычная, и язык выбирает посетитель. Но админка — рабочее
    место владельца: если браузер украинский, служебные надписи Django
    перевелись бы, а названия полей остались русскими — вышла бы каша.

    Стоит после LocaleMiddleware, чтобы перебивать выбранный им язык.
    """

    LANGUAGE = "ru"

    def process_request(self, request):
        if request.path.startswith(settings.ADMIN_PATH):
            translation.activate(self.LANGUAGE)
            request.LANGUAGE_CODE = self.LANGUAGE
        return None
