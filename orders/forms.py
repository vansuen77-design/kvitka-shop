"""Order form: contacts, delivery, recipient, gift card."""

from __future__ import annotations

import datetime
import re

from django import forms
from django.utils import timezone
from django.utils.translation import gettext as _, gettext_noop

from orders.models import Order


class OrderForm(forms.ModelForm):
    """Contacts and delivery. No payment — the florist calls back and confirms.

    Labels and placeholders are set here rather than taken from the model:
    in the model they are Russian and needed so in the admin, while the
    customer must see the form in the page language. The Russian text here
    doubles as the translation key: gettext_noop marks it for makelocales,
    and __init__ translates it when the form is built.
    """

    agree = forms.BooleanField(required=True)

    LABELS = {
        "name": gettext_noop("Ваше имя"),
        "phone": gettext_noop("Телефон"),
        "email": gettext_noop("Почта"),
        "delivery": gettext_noop("Как получить"),
        "address": gettext_noop("Адрес доставки"),
        "delivery_date": gettext_noop("Дата"),
        "delivery_time": gettext_noop("Время"),
        "recipient_name": gettext_noop("Имя получателя"),
        "recipient_phone": gettext_noop("Телефон получателя"),
        "card_text": gettext_noop("Текст открытки"),
        "payment": gettext_noop("Оплата"),
        "comment": gettext_noop("Комментарий"),
        "agree": gettext_noop("Согласен на обработку данных для связи по заказу"),
    }

    PLACEHOLDERS = {
        "name": gettext_noop("Как к вам обращаться"),
        "phone": "+38 0__ ___-__-__",
        "email": gettext_noop("необязательно"),
        "address": gettext_noop("Улица, дом, квартира, этаж"),
        "recipient_name": gettext_noop("если букет получает другой человек"),
        "recipient_phone": gettext_noop("курьер позвонит перед доставкой"),
        "card_text": gettext_noop("несколько слов — напишем от руки"),
        "comment": gettext_noop("Что учесть: код домофона, время звонка, замена цветов"),
    }

    # selectable from today up to this many days ahead
    MAX_DAYS_AHEAD = 30

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name in self.LABELS:
                field.label = _(self.LABELS[name])
            if name in self.PLACEHOLDERS:
                field.widget.attrs["placeholder"] = _(self.PLACEHOLDERS[name])
        # choice labels are stored in the model in Russian
        self.fields["delivery"].choices = [
            (value, _(label)) for value, label in Order.Delivery.choices
        ]
        self.fields["payment"].choices = [
            (value, _(label)) for value, label in Order.Payment.choices
        ]
        self.fields["delivery_time"].choices = [
            ("", _("любое время")),
            *Order.TimeSlot.choices,
        ]
        today = timezone.localdate()
        self.fields["delivery_date"].widget.attrs.update({
            "min": today.isoformat(),
            "max": (today + datetime.timedelta(days=self.MAX_DAYS_AHEAD)).isoformat(),
        })
        if not self.is_bound and not self.initial.get("delivery_date"):
            self.initial["delivery_date"] = today

    class Meta:
        model = Order
        fields = (
            "name", "phone", "email",
            "delivery", "address", "delivery_date", "delivery_time",
            "recipient_name", "recipient_phone", "card_text",
            "payment", "comment",
        )
        widgets = {
            "name": forms.TextInput(attrs={"class": "input", "autocomplete": "name"}),
            "phone": forms.TextInput(attrs={
                "class": "input", "autocomplete": "tel", "inputmode": "tel",
            }),
            "email": forms.EmailInput(attrs={"class": "input", "autocomplete": "email"}),
            "delivery": forms.RadioSelect(),
            "address": forms.TextInput(attrs={
                "class": "input", "autocomplete": "street-address",
            }),
            "delivery_date": forms.DateInput(attrs={"class": "input", "type": "date"},
                                             format="%Y-%m-%d"),
            "delivery_time": forms.Select(attrs={"class": "input"}),
            "recipient_name": forms.TextInput(attrs={"class": "input"}),
            "recipient_phone": forms.TextInput(attrs={
                "class": "input", "inputmode": "tel",
            }),
            "card_text": forms.TextInput(attrs={"class": "input", "maxlength": 300}),
            "payment": forms.RadioSelect(),
            "comment": forms.Textarea(attrs={"class": "textarea", "rows": 3}),
        }

    @staticmethod
    def clean_phone_value(phone: str) -> str:
        phone = (phone or "").strip()
        digits = re.sub(r"\D", "", phone)
        if len(digits) < 9:
            raise forms.ValidationError(
                _("Похоже, в номере не хватает цифр — проверьте, пожалуйста.")
            )
        return phone

    def clean_phone(self) -> str:
        return self.clean_phone_value(self.cleaned_data.get("phone"))

    def clean_recipient_phone(self) -> str:
        phone = (self.cleaned_data.get("recipient_phone") or "").strip()
        return self.clean_phone_value(phone) if phone else ""

    def clean_delivery_date(self):
        """The date is not in the past and not further than a month.

        Checked by the server, not only by the field's min/max attributes:
        the browser may not support them, and without JavaScript even less so.
        """
        value = self.cleaned_data.get("delivery_date")
        if value is None:
            return value
        today = timezone.localdate()
        if value < today:
            raise forms.ValidationError(_("Эта дата уже прошла."))
        if value > today + datetime.timedelta(days=self.MAX_DAYS_AHEAD):
            raise forms.ValidationError(
                _("Так далеко вперёд не планируем — выберите дату ближе.")
            )
        return value

    def clean(self):
        data = super().clean()
        delivery = data.get("delivery")
        if delivery == Order.Delivery.COURIER:
            if not (data.get("address") or "").strip():
                self.add_error("address", _("Куда везти? Укажите адрес."))
            if not data.get("delivery_date"):
                self.add_error("delivery_date", _("Выберите дату доставки."))
        else:
            # pickup: no address needed, whatever is left in the field
            data["address"] = ""
        return data
