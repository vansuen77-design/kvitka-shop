"""Cart and checkout views."""

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
    """Gives the view a ready cart."""

    @property
    def cart(self) -> Cart:
        if not hasattr(self, "_cart"):
            self._cart = Cart(self.request)
        return self._cart


class CartView(PageTitleMixin, CartMixin, TemplateView):
    """The "Cart" page: collected lines and the order form."""

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
        """Data of the logged-in customer — so they need not type it every time.

        There may be no profile: the administrator was created by a command,
        not through registration. Then at least the name and e-mail are
        taken from the account.
        """
        user = self.request.user
        if not user.is_authenticated:
            return {}
        profile = getattr(user, "profile", None)
        if profile is not None:
            return profile.as_order_initial()
        return {"name": user.first_name, "email": user.email}

    def post(self, request, *args, **kwargs):
        """Checkout. No payment — save and show "thank you"."""
        totals = self.cart.totals
        form = OrderForm(request.POST)

        if not totals.lines:
            form.add_error(None, _("Сначала добавьте букеты из каталога."))
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))

        order = create_order(form, totals, request.user)
        # the notification goes in the background: if Telegram is down the
        # customer will not know and will not lose the order
        notify_new_order(order)
        self.cart.clear()
        # so that a stranger cannot open the "thank you" page by guessing
        # numbers — remember the own order in the session
        request.session["last_order"] = order.pk
        return redirect("orders:success", pk=order.pk)


class OrderSuccessView(PageTitleMixin, DetailView):
    """Thank you for the order — the number and what happens next."""

    model = Order
    template_name = "orders/success.html"
    context_object_name = "order"

    def get_page_title(self) -> str:
        return _("Заказ принят")

    def get_queryset(self):
        """Only the own order — the one remembered in the session on submit."""
        own = self.request.session.get("last_order")
        return Order.objects.filter(pk=own) if own else Order.objects.none()


# --- cart actions --------------------------------------------------------
class CartActionView(JsonRequestMixin, CartMixin, View):
    """Common base for all cart actions.

    The response carries not only the numbers but the ready markup of the
    lines table: the page updates it in place and never reloads — otherwise
    a reload would cut off the next request the user has already sent.
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
    """Add a quantity of a product."""

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

        # stock — via the product's single method
        quantity = product.normalize_quantity(asked)
        if quantity <= 0:
            return self.fail(_("Этого букета не осталось"))

        self.cart.add(product, quantity)
        return self.respond()


class CartUpdateView(CartActionView):
    """Replace the quantity of a line."""

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
    """Fallback without JavaScript: a plain form with a reload."""

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
    """Without JavaScript: the "Update" and "Remove" buttons in a cart line.

    One form per line, two buttons: "remove" zeroes the line, otherwise the
    quantity is taken from the field. The product normalises the quantity.
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
