"""Customer account URLs."""

from django.conf import settings
from django.contrib.auth import views as auth_views
from django.urls import path

from accounts import views

app_name = "accounts"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("vhod/", views.Login.as_view(), name="login"),
    path("vyhod/", views.Logout.as_view(), name="logout"),
    path("registratsiya/", views.Register.as_view(), name="register"),
    path("zakazy/", views.order_history, name="orders"),
    path("zakazy/<int:pk>/", views.order_detail, name="order"),
    path("izbrannoe/", views.favorites, name="favorites"),
    path("dannye/", views.profile_edit, name="profile"),
    path("api/izbrannoe/", views.FavoriteToggle.as_view(), name="favorite-toggle"),

    # --- password reset: Django views, our templates ----------------------
    path("parol/", auth_views.PasswordResetView.as_view(
        template_name="accounts/password_reset.html",
        email_template_name="accounts/password_reset_email.txt",
        subject_template_name="accounts/password_reset_subject.txt",
        # the e-mail is rendered without context processors — the shop name
        # is passed explicitly rather than hard-coded in the template
        extra_email_context={"shop": settings.SHOP},
        success_url="/kabinet/parol/otpravleno/",
    ), name="password_reset"),
    path("parol/otpravleno/", auth_views.PasswordResetDoneView.as_view(
        template_name="accounts/password_reset_done.html",
    ), name="password_reset_done"),
    path("parol/novyy/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="accounts/password_reset_confirm.html",
        success_url="/kabinet/parol/gotovo/",
    ), name="password_reset_confirm"),
    path("parol/gotovo/", auth_views.PasswordResetCompleteView.as_view(
        template_name="accounts/password_reset_complete.html",
    ), name="password_reset_complete"),
]
