"""Представления корзины и оформления заказа."""

from __future__ import annotations

from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.utils.translation import gettext as _
from django.views.generic import DetailView, TemplateView, View

from catalog.models import Product
from core.mixins import JsonRequestMixin, PageTitleMixin
from orders.cart import Cart
from orders.forms import OrderForm
from orders.models import Order
from orders.notify import notify_new_order
from orders.services import create_order


class CartMixin:
    """Даёт представлению готовую корзину."""

    @property
    def cart(self) -> Cart:
        if not hasattr(self, "_cart"):
            self._cart = Cart(self.request)
        return self._cart


class CartView(PageTitleMixin, CartMixin, TemplateView):
    """Страница «Корзина»: собранные позиции и форма заказа."""

    template_name = "orders/cart.html"
    page_title = "Корзина"

    def get_page_title(self) -> str:
        return _("Корзина")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("form", OrderForm(initial=self.profile_initial()))
        context.update({
            "cart": self.cart,
            "totals": self.cart.totals,
            "breadcrumbs": [
                {"title": _("Каталог"), "url": "/"},
                {"title": _("Корзина"), "url": None},
            ],
        })
        return context

    def profile_initial(self) -> dict:
        """Данные вошедшего покупателя — чтобы не вводить их каждый раз.

        Анкеты может не быть: администратора завели командой, а не через
        регистрацию. Тогда берём хотя бы имя и почту из учётной записи.
        """
        user = self.request.user
        if not user.is_authenticated:
            return {}
        profile = getattr(user, "profile", None)
        if profile is not None:
            return profile.as_order_initial()
        return {"name": user.first_name, "email": user.email}

    def post(self, request, *args, **kwargs):
        """Оформление. Оплаты нет — сохраняем и показываем «спасибо»."""
        totals = self.cart.totals
        form = OrderForm(request.POST)

        if not totals.lines:
            form.add_error(None, _("Сначала добавьте букеты из каталога."))
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))

        order = create_order(form, totals, request.user)
        # уведомление уходит в фоне: если Telegram недоступен,
        # покупатель об этом не узнает и заказ не потеряет
        notify_new_order(order)
        self.cart.clear()
        # чтобы страницу «спасибо» не мог открыть кто-то посторонний,
        # перебирая номера — запоминаем свой заказ в сессии
        request.session["last_order"] = order.pk
        return redirect("orders:success", pk=order.pk)


class OrderSuccessView(PageTitleMixin, DetailView):
    """Спасибо за заказ — номер и что будет дальше."""

    model = Order
    template_name = "orders/success.html"
    context_object_name = "order"

    def get_page_title(self) -> str:
        return _("Заказ принят")

    def get_queryset(self):
        """Только свой заказ — тот, что запомнили в сессии при отправке."""
        own = self.request.session.get("last_order")
        return Order.objects.filter(pk=own) if own else Order.objects.none()


# --- действия над корзиной -----------------------------------------------
class CartActionView(JsonRequestMixin, CartMixin, View):
    """Общее для всех действий над корзиной.

    В ответ кладём не только цифры, но и готовую разметку таблицы позиций:
    страница обновляет её на месте и никогда не перезагружается — иначе
    перезагрузка обрывает следующий запрос, который пользователь уже успел
    отправить.
    """

    def lines_html(self) -> str:
        return render_to_string(
            "orders/_cart_lines.html",
            {"totals": self.cart.totals, "request": self.request},
            request=self.request,
        )

    def respond(self):
        return self.ok(cart=self.cart.as_dict(), html=self.lines_html())

    def get_product(self, payload) -> Product | None:
        product_id = payload.get("product")
        if not product_id:
            return None
        return Product.objects.filter(pk=product_id, is_active=True).first()

    @staticmethod
    def asked_quantity(payload):
        try:
            return max(int(payload.get("quantity", 0)), 0)
        except (TypeError, ValueError):
            return None


class CartAddView(CartActionView):
    """Добавить количество по товару."""

    def post(self, request, *args, **kwargs):
        payload = self.get_payload()
        product = self.get_product(payload)
        if product is None:
            return self.fail(_("Товар не найден"))
        if not product.is_orderable:
            return self.fail(_("Этот букет сейчас нельзя добавить в корзину"))

        asked = self.asked_quantity(payload)
        if asked is None:
            return self.fail(_("Не понял количество"))
        if asked <= 0:
            return self.fail(_("Укажите количество"))

        # остаток — одним методом товара
        quantity = product.normalize_quantity(asked)
        if quantity <= 0:
            return self.fail(_("Этого букета не осталось"))

        self.cart.add(product, quantity)
        return self.respond()


class CartUpdateView(CartActionView):
    """Заменить количество позиции."""

    def post(self, request, *args, **kwargs):
        payload = self.get_payload()
        product = self.get_product(payload)
        if product is None:
            return self.fail(_("Товар не найден"))
        asked = self.asked_quantity(payload)
        if asked is None:
            return self.fail(_("Не понял количество"))
        self.cart.set_quantity(product.pk, product.normalize_quantity(asked))
        return self.respond()


class CartRemoveView(CartActionView):
    def post(self, request, *args, **kwargs):
        payload = self.get_payload()
        product_id = payload.get("product")
        if not product_id:
            return self.fail(_("Не указана позиция"))
        self.cart.remove(int(product_id))
        return self.respond()


class CartClearView(CartActionView):
    def post(self, request, *args, **kwargs):
        self.cart.clear()
        return self.respond()


class CartFormAddView(CartMixin, View):
    """Резервный путь без JavaScript: обычная форма с перезагрузкой."""

    def post(self, request, *args, **kwargs):
        product = get_object_or_404(
            Product, pk=request.POST.get("product"), is_active=True
        )
        try:
            quantity = max(int(request.POST.get("quantity") or 0), 0)
        except (TypeError, ValueError):
            quantity = 0
        quantity = product.normalize_quantity(quantity)
        if quantity and product.is_orderable:
            self.cart.add(product, quantity)
        return redirect("orders:cart")


class CartFormUpdateView(CartMixin, View):
    """Без JavaScript: кнопки «Обновить» и «Убрать» в строке корзины.

    Одна форма на строку, две кнопки: «remove» обнуляет позицию, иначе
    берём количество из поля. Количество приводит сам товар.
    """

    def post(self, request, *args, **kwargs):
        product = get_object_or_404(Product, pk=request.POST.get("product"))
        if "remove" in request.POST:
            self.cart.remove(product.pk)
        else:
            try:
                asked = max(int(request.POST.get("quantity") or 0), 0)
            except (TypeError, ValueError):
                asked = 0
            self.cart.set_quantity(product.pk, product.normalize_quantity(asked))
        return redirect("orders:cart")
