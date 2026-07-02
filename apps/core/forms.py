from django import forms

from orders.models import Order


class CheckoutForm(forms.Form):
    PAYMENT_ONLINE = Order.PaymentMethod.ONLINE
    PAYMENT_COUNTER_CARD = Order.PaymentMethod.COUNTER_CARD
    PAYMENT_CASH = Order.PaymentMethod.CASH

    PAYMENT_CHOICES = (
        (PAYMENT_ONLINE, "پرداخت آنلاین"),
        (PAYMENT_COUNTER_CARD, "پرداخت با کارت در صندوق"),
        (PAYMENT_CASH, "پرداخت نقدی در صندوق"),
    )

    first_name = forms.CharField(
        label="نام",
        max_length=100,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "نام شما"}),
    )
    last_name = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
    )
    phone = forms.CharField(
        label="تلفن",
        max_length=30,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "شماره تماس", "dir": "ltr"}
        ),
    )
    email = forms.EmailField(
        label="ایمیل",
        required=False,
        widget=forms.EmailInput(
            attrs={"class": "form-control", "placeholder": "ایمیل (اختیاری)", "dir": "ltr"}
        ),
    )
    pickup_note = forms.CharField(
        label="شماره میز یا یادداشت",
        required=False,
        max_length=255,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "مثلاً میز ۱۲ (اختیاری)"}
        ),
    )
    payment_method = forms.ChoiceField(
        label="روش پرداخت",
        choices=PAYMENT_CHOICES,
        initial=PAYMENT_ONLINE,
        widget=forms.RadioSelect(attrs={"class": "choice-card__input"}),
    )
    address_line1 = forms.CharField(required=False, widget=forms.HiddenInput())
    address_line2 = forms.CharField(required=False, widget=forms.HiddenInput())
    city = forms.CharField(required=False, widget=forms.HiddenInput())
    state = forms.CharField(required=False, widget=forms.HiddenInput())
    postal_code = forms.CharField(required=False, widget=forms.HiddenInput())
    country = forms.CharField(required=False, initial="Iran", widget=forms.HiddenInput())
    notes = forms.CharField(required=False, widget=forms.HiddenInput())

    def clean_email(self):
        return (self.cleaned_data.get("email") or "").strip()

    def clean(self):
        cleaned = super().clean()
        phone = (cleaned.get("phone") or "").strip()
        if not phone:
            self.add_error("phone", "شماره تماس الزامی است.")
            return cleaned

        first_name = (cleaned.get("first_name") or "").strip()
        if not first_name:
            self.add_error("first_name", "نام الزامی است.")
            return cleaned

        cleaned["first_name"] = first_name
        cleaned["phone"] = phone
        cleaned["last_name"] = (cleaned.get("last_name") or "").strip() or first_name

        email = cleaned.get("email") or ""
        if not email:
            cleaned["email"] = f"guest+{phone.replace('+', '')}@crumbs.local"

        pickup_note = (cleaned.get("pickup_note") or "").strip()
        cleaned["notes"] = pickup_note
        cleaned["pickup_note"] = pickup_note

        for field in ("address_line1", "city", "postal_code", "address_line2", "state"):
            cleaned.setdefault(field, "")

        cleaned.setdefault("country", "Iran")
        return cleaned


class ContactForm(forms.Form):
    name = forms.CharField(
        label="نام",
        max_length=120,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "نام شما"}),
    )
    email = forms.EmailField(
        label="ایمیل",
        widget=forms.EmailInput(
            attrs={"class": "form-control", "placeholder": "آدرس ایمیل", "dir": "ltr"}
        ),
    )
    message = forms.CharField(
        label="پیام",
        widget=forms.Textarea(
            attrs={"class": "form-control", "rows": 5, "placeholder": "پیام خود را بنویسید..."}
        ),
    )


class NewsletterForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={"class": "form-control", "placeholder": "ایمیل خود را وارد کنید", "dir": "ltr"}
        ),
    )
