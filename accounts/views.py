"""Customer account."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views.decorators.cache import never_cache
from django.views.generic import View

from accounts.forms import LoginForm, ProfileForm, RegisterForm
from accounts.models import Favorite, Profile
from catalog.models import Product
from core.mixins import JsonRequestMixin
from orders.models import Order


def crumbs(title):
    return [{"title": _("Каталог"), "url": "/"}, {"title": title, "url": None}]


class Login(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumbs"] = crumbs(_("Вход"))
        return context


class Logout(LogoutView):
    next_page = reverse_lazy("catalog:index")


@method_decorator(never_cache, name="dispatch")
class Register(View):
    """Registration. Right after it the person is logged in — typing the
    same data a second time would be cruel."""

    template_name = "accounts/register.html"

    def get(self, request):
        if request.user.is_authenticated:
            return redirect("accounts:dashboard")
        return self.render(request, RegisterForm())

    def post(self, request):
        form = RegisterForm(request.POST)
        if not form.is_valid():
            return self.render(request, form)
        user = form.save()
        login(request, user, backend="accounts.backends.EmailBackend")
        messages.success(request, _("Кабинет создан. Данные теперь подставляются в заказ сами."))
        return redirect("accounts:dashboard")

    def render(self, request, form):
        return render(request, self.template_name,
                      {"form": form, "breadcrumbs": crumbs(_("Регистрация"))})


@login_required
def dashboard(request):
    profile = Profile.objects.filter(user=request.user).first()
    orders = Order.objects.filter(user=request.user).prefetch_related("lines")[:5]
    favorites = (
        Favorite.objects.filter(user=request.user)
        .select_related("product")
        .prefetch_related("product__images")[:4]
    )
    return render(request, "accounts/dashboard.html", {
        "profile": profile,
        "orders": orders,
        "orders_total": Order.objects.filter(user=request.user).count(),
        "favorites": favorites,
        "favorites_total": Favorite.objects.filter(user=request.user).count(),
        "breadcrumbs": crumbs(_("Кабинет")),
        "section": "dashboard",
    })


@login_required
def order_history(request):
    orders = (
        Order.objects.filter(user=request.user)
        .prefetch_related("lines", "lines__product__images")
    )
    return render(request, "accounts/orders.html", {
        "orders": orders,
        "breadcrumbs": crumbs(_("Мои заказы")),
        "section": "orders",
    })


@login_required
def order_detail(request, pk):
    order = get_object_or_404(
        Order.objects.prefetch_related("lines"), pk=pk, user=request.user
    )
    return render(request, "accounts/order_detail.html", {
        "order": order,
        "breadcrumbs": crumbs(_("Заказ №%(number)s") % {"number": order.pk}),
        "section": "orders",
    })


@login_required
def favorites(request):
    items = (
        Favorite.objects.filter(user=request.user)
        .select_related("product", "product__status")
        .prefetch_related("product__images")
    )
    return render(request, "accounts/favorites.html", {
        "favorites": items,
        "breadcrumbs": crumbs(_("Избранное")),
        "section": "favorites",
    })


@login_required
def profile_edit(request):
    profile, _created = Profile.objects.get_or_create(user=request.user)
    form = ProfileForm(request.POST or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Сохранено."))
        return redirect("accounts:dashboard")
    return render(request, "accounts/profile.html", {
        "form": form,
        "breadcrumbs": crumbs(_("Мои данные")),
        "section": "profile",
    })


class FavoriteToggle(JsonRequestMixin, View):
    """The heart on a product tile. Answers with its new state."""

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.fail(_("Войдите в кабинет, чтобы сохранять товары"))
        payload = self.get_payload()
        product = Product.objects.filter(pk=payload.get("product"), is_active=True).first()
        if product is None:
            return self.fail(_("Товар не найден"))
        favorite = Favorite.objects.filter(user=request.user, product=product).first()
        if favorite:
            favorite.delete()
            active = False
        else:
            Favorite.objects.create(user=request.user, product=product)
            active = True
        return self.ok(active=active,
                       total=Favorite.objects.filter(user=request.user).count())
