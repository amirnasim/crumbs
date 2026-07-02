from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from orders.models import Order

from .forms import AddressForm, LoginForm, ProfileForm, RegisterForm, SMS_LOGIN_LABELS
from .models import Address, CustomerProfile
from .services import merge_session_cart_on_login


def register(request):
    if request.user.is_authenticated:
        return redirect("accounts:profile")

    form = RegisterForm()
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            merge_session_cart_on_login(request, user)
            messages.success(request, "حساب کاربری شما با موفقیت ایجاد شد.")
            return redirect("accounts:profile")

    return render(request, "accounts/register.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("accounts:profile")

    form = LoginForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        login(request, user)
        merge_session_cart_on_login(request, user)
        messages.success(request, "خوش آمدید.")
        next_url = request.GET.get("next")
        if next_url:
            return redirect(next_url)
        return redirect("accounts:profile")

    return render(
        request,
        "accounts/login.html",
        {
            "form": form,
            "sms_login_labels": SMS_LOGIN_LABELS,
        },
    )


@require_POST
@login_required
def logout_view(request):
    logout(request)
    messages.info(request, "با موفقیت خارج شدید.")
    return redirect("core:home")


@login_required
def profile(request):
    profile_obj, _ = CustomerProfile.objects.get_or_create(user=request.user)
    form = ProfileForm(instance=profile_obj, user=request.user)
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=profile_obj, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "پروفایل بروزرسانی شد.")
            return redirect("accounts:profile")

    return render(
        request,
        "accounts/profile.html",
        {
            "form": form,
            "order_count": request.user.orders.count(),
            "address_count": request.user.addresses.count(),
        },
    )


@login_required
def order_list(request):
    orders = (
        Order.objects.filter(user=request.user)
        .prefetch_related("items")
        .order_by("-created_at")
    )
    return render(request, "accounts/order_list.html", {"orders": orders})


def order_detail(request, order_number):
    from core.checkout_access import can_view_checkout_order

    order_qs = Order.objects.prefetch_related("items", "payments")
    order = get_object_or_404(order_qs, order_number=order_number)

    if not can_view_checkout_order(request, order):
        messages.warning(request, "برای مشاهده این سفارش وارد شوید.")
        return redirect(f"{reverse('accounts:login')}?next={reverse('accounts:order_detail', args=[order_number])}")

    return render(request, "accounts/order_detail.html", {"order": order})


@login_required
def address_list(request):
    addresses = request.user.addresses.all()
    return render(request, "accounts/address_list.html", {"addresses": addresses})


@login_required
def address_create(request):
    form = AddressForm()
    if request.method == "POST":
        form = AddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.user = request.user
            address.save()
            messages.success(request, "آدرس جدید ذخیره شد.")
            return redirect("accounts:address_list")

    return render(request, "accounts/address_form.html", {"form": form, "title": "افزودن آدرس"})


@login_required
def address_edit(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    form = AddressForm(instance=address)
    if request.method == "POST":
        form = AddressForm(request.POST, instance=address)
        if form.is_valid():
            form.save()
            messages.success(request, "آدرس بروزرسانی شد.")
            return redirect("accounts:address_list")

    return render(
        request,
        "accounts/address_form.html",
        {"form": form, "title": "ویرایش آدرس", "address": address},
    )


@login_required
@require_POST
def address_delete(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    address.delete()
    messages.info(request, "آدرس حذف شد.")
    return redirect("accounts:address_list")


@login_required
@require_POST
def address_set_default(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    address.is_default = True
    address.save()
    messages.success(request, "آدرس پیش‌فرض تنظیم شد.")
    return redirect("accounts:address_list")
