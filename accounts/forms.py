"""Account forms: registration, login, profile."""

from __future__ import annotations

import re

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _, gettext_noop

from accounts.models import Profile

User = get_user_model()

INPUT = {"class": "input"}


def clean_phone_value(phone: str) -> str:
    phone = (phone or "").strip()
    if len(re.sub(r"\D", "", phone)) < 9:
        raise ValidationError(
            _("Похоже, в номере не хватает цифр — проверьте, пожалуйста.")
        )
    return phone


class RegisterForm(forms.Form):
    """Registration. The e-mail serves both as login and as the reset address."""

    name = forms.CharField(max_length=120, widget=forms.TextInput(attrs=INPUT))
    email = forms.EmailField(widget=forms.EmailInput(attrs={**INPUT, "autocomplete": "email"}))
    phone = forms.CharField(max_length=40, widget=forms.TextInput(
        attrs={**INPUT, "autocomplete": "tel", "inputmode": "tel"}))
    address = forms.CharField(max_length=300, required=False,
                              widget=forms.TextInput(attrs=INPUT))
    password1 = forms.CharField(widget=forms.PasswordInput(
        attrs={**INPUT, "autocomplete": "new-password"}))
    password2 = forms.CharField(widget=forms.PasswordInput(
        attrs={**INPUT, "autocomplete": "new-password"}))
    agree = forms.BooleanField(required=True)

    LABELS = {
        "name": gettext_noop("Имя"),
        "email": gettext_noop("Почта"),
        "phone": gettext_noop("Телефон"),
        "address": gettext_noop("Адрес доставки"),
        "password1": gettext_noop("Пароль"),
        "password2": gettext_noop("Пароль ещё раз"),
        "agree": gettext_noop("Согласен на обработку данных"),
    }
    PLACEHOLDERS = {
        "name": gettext_noop("Как к вам обращаться"),
        "email": gettext_noop("почта для входа"),
        "phone": "+38 0__ ___-__-__",
        "address": gettext_noop("необязательно — подставится в заказ"),
        "password1": gettext_noop("не короче 8 символов"),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.label = _(self.LABELS[name])
            if name in self.PLACEHOLDERS:
                field.widget.attrs["placeholder"] = _(self.PLACEHOLDERS[name])

    def clean_email(self) -> str:
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError(
                _("На эту почту уже есть кабинет. Войдите или восстановите пароль.")
            )
        return email

    def clean_phone(self) -> str:
        return clean_phone_value(self.cleaned_data.get("phone"))

    def clean(self):
        data = super().clean()
        first, second = data.get("password1"), data.get("password2")
        if first and second and first != second:
            self.add_error("password2", _("Пароли не совпадают."))
        elif first:
            # Django checks: length, not all digits, not in the common list
            validate_password(first)
        return data

    def save(self) -> User:
        data = self.cleaned_data
        user = User.objects.create_user(
            username=data["email"],
            email=data["email"],
            password=data["password1"],
            first_name=data["name"],
        )
        Profile.objects.create(
            user=user,
            phone=data["phone"],
            address=data.get("address", ""),
        )
        return user


class LoginForm(AuthenticationForm):
    """Login by e-mail. The field label changes, Django's mechanics stay."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = _("Почта")
        self.fields["username"].widget = forms.EmailInput(
            attrs={**INPUT, "autocomplete": "email", "autofocus": True})
        self.fields["password"].label = _("Пароль")
        self.fields["password"].widget = forms.PasswordInput(
            attrs={**INPUT, "autocomplete": "current-password"})
        self.error_messages["invalid_login"] = _(
            "Неверная почта или пароль."
        )


class ProfileForm(forms.ModelForm):
    """Profile in the account. Name and e-mail live in the user record itself."""

    name = forms.CharField(max_length=120, widget=forms.TextInput(attrs=INPUT))

    class Meta:
        model = Profile
        fields = ("phone", "address", "preferred_contact")
        widgets = {
            "phone": forms.TextInput(attrs={**INPUT, "inputmode": "tel"}),
            "address": forms.TextInput(attrs=INPUT),
            "preferred_contact": forms.RadioSelect(),
        }

    LABELS = {
        "name": gettext_noop("Имя"),
        "phone": gettext_noop("Телефон"),
        "address": gettext_noop("Адрес доставки"),
        "preferred_contact": gettext_noop("Удобная связь"),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].initial = self.instance.user.first_name
        for name, field in self.fields.items():
            if name in self.LABELS:
                field.label = _(self.LABELS[name])
        self.fields["preferred_contact"].choices = [
            (value, _(label)) for value, label in Profile.Contact.choices
        ]

    def clean_phone(self) -> str:
        return clean_phone_value(self.cleaned_data.get("phone"))

    def save(self, commit=True):
        profile = super().save(commit=False)
        profile.user.first_name = self.cleaned_data["name"]
        if commit:
            profile.user.save(update_fields=["first_name"])
            profile.save()
        return profile
