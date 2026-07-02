from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import Address, CustomerProfile
from .services import resolve_login_identifier

SMS_LOGIN_LABELS = {
    "send_code": "ارسال کد تأیید",
    "otp_code": "کد تأیید پیامکی",
    "login_with_sms": "ورود با پیامک",
}

User = get_user_model()


class RegisterForm(UserCreationForm):
    email = forms.EmailField(
        label="ایمیل",
        widget=forms.EmailInput(attrs={"class": "form-control", "dir": "ltr"}),
    )
    first_name = forms.CharField(
        label="نام",
        max_length=150,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    last_name = forms.CharField(
        label="نام خانوادگی",
        max_length=150,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name", "password1", "password2")
        labels = {
            "username": "نام کاربری",
        }
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control", "dir": "ltr"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].label = "رمز عبور"
        self.fields["password2"].label = "تکرار رمز عبور"
        self.fields["password1"].widget.attrs.update({"class": "form-control"})
        self.fields["password2"].widget.attrs.update({"class": "form-control"})

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label="شماره تلفن همراه",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "dir": "ltr",
                "placeholder": "مثلاً 09123456789",
                "autocomplete": "tel",
            }
        ),
    )
    password = forms.CharField(
        label="رمز عبور",
        widget=forms.PasswordInput(attrs={"class": "form-control", "autocomplete": "current-password"}),
    )

    def clean_username(self):
        identifier = self.cleaned_data["username"]
        return resolve_login_identifier(identifier)


class ProfileForm(forms.ModelForm):
    email = forms.EmailField(
        label="ایمیل",
        widget=forms.EmailInput(attrs={"class": "form-control", "dir": "ltr"}),
    )
    first_name = forms.CharField(
        label="نام",
        max_length=150,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    last_name = forms.CharField(
        label="نام خانوادگی",
        max_length=150,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    class Meta:
        model = CustomerProfile
        fields = ("phone", "notes")
        labels = {
            "phone": "تلفن",
            "notes": "یادداشت",
        }
        widgets = {
            "phone": forms.TextInput(attrs={"class": "form-control", "dir": "ltr"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user")
        super().__init__(*args, **kwargs)
        self.fields["email"].initial = self.user.email
        self.fields["first_name"].initial = self.user.first_name
        self.fields["last_name"].initial = self.user.last_name

    def save(self, commit=True):
        profile = super().save(commit=commit)
        self.user.email = self.cleaned_data["email"]
        self.user.first_name = self.cleaned_data["first_name"]
        self.user.last_name = self.cleaned_data["last_name"]
        self.user.save(update_fields=["email", "first_name", "last_name"])
        return profile


class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = (
            "label",
            "first_name",
            "last_name",
            "phone",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "postal_code",
            "country",
            "is_default",
        )
        labels = {
            "label": "برچسب (مثلاً منزل)",
            "first_name": "نام",
            "last_name": "نام خانوادگی",
            "phone": "تلفن",
            "address_line1": "آدرس",
            "address_line2": "جزئیات آدرس",
            "city": "شهر",
            "state": "استان",
            "postal_code": "کد پستی",
            "country": "کشور",
            "is_default": "آدرس پیش‌فرض",
        }
        widgets = {
            "label": forms.TextInput(attrs={"class": "form-control"}),
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control", "dir": "ltr"}),
            "address_line1": forms.TextInput(attrs={"class": "form-control"}),
            "address_line2": forms.TextInput(attrs={"class": "form-control"}),
            "city": forms.TextInput(attrs={"class": "form-control"}),
            "state": forms.TextInput(attrs={"class": "form-control"}),
            "postal_code": forms.TextInput(attrs={"class": "form-control", "dir": "ltr"}),
            "country": forms.TextInput(attrs={"class": "form-control"}),
            "is_default": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
