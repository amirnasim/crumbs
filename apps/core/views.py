from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.services import get_checkout_initial
from cart.exceptions import InvalidQuantityError, ProductUnavailableError
from cart.services import add_item, get_or_create_cart, remove_item, set_item_quantity
from core.checkout_access import grant_checkout_order_access
from core.table_session import get_checkout_table_initial, sync_table_from_pickup_note
from core.forms import CheckoutForm, ContactForm, NewsletterForm
from core.performance import cache_get_or_set
from delivery.services import process_checkout
from orders.exceptions import CheckoutError, EmptyCartError
from orders.models import Order
from orders.services.counter_checkout import process_counter_checkout
from products.models import Category, Product

COUNTER_PAYMENT_MESSAGE = "سفارش ثبت شد. لطفاً برای پرداخت به صندوق مراجعه کنید."
COUNTER_CASH_MESSAGE = COUNTER_PAYMENT_MESSAGE
COUNTER_CARD_MESSAGE = COUNTER_PAYMENT_MESSAGE


def _get_cart(request):
    if not request.session.session_key:
        request.session.create()

    if request.user.is_authenticated:
        return get_or_create_cart(user=request.user)[0]

    return get_or_create_cart(session_key=request.session.session_key)[0]


def _track_conversion(event_type, request, **kwargs):
    from growth.conversion_service import ConversionService
    from growth.models import GrowthEvent

    session_key = request.session.session_key or ""
    if not session_key:
        request.session.create()
        session_key = request.session.session_key or ""
    ConversionService.track(
        event_type,
        user=request.user if request.user.is_authenticated else None,
        session_key=session_key,
        **kwargs,
    )


def home(request):
    newsletter_form = NewsletterForm()
    if request.method == "POST" and request.POST.get("form_type") == "newsletter":
        newsletter_form = NewsletterForm(request.POST)
        if newsletter_form.is_valid():
            messages.success(request, "به حلقه کرامبز خوش آمدید. به‌زودی با شما در تماس خواهیم بود.")
            return redirect("core:home")

    featured_products = cache_get_or_set(
        "crumbs:home:featured",
        lambda: list(
            Product.objects.filter(
                is_featured=True,
                availability_status=Product.AvailabilityStatus.AVAILABLE,
            ).select_related("category")[:4]
        ),
    )

    from intelligence.recommendation_service import RecommendationService

    best_sellers = RecommendationService.for_home(
        user=request.user if request.user.is_authenticated else None,
        limit=8,
    )

    return render(
        request,
        "pages/home.html",
        {
            "featured_products": featured_products,
            "best_sellers": best_sellers,
            "newsletter_form": newsletter_form,
        },
    )


def about(request):
    return render(request, "pages/about.html")


def contact(request):
    form = ContactForm()
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            messages.success(request, "پیام شما دریافت شد. ظرف ۲۴ ساعت پاسخ می‌دهیم.")
            return redirect("core:contact")

    return render(request, "pages/contact.html", {"form": form})


def product_list(request, category_slug=None):
    categories = cache_get_or_set(
        "crumbs:categories:all",
        lambda: list(Category.objects.all()),
    )
    cache_key = f"crumbs:catalog:products:{category_slug or 'all'}"
    products = cache_get_or_set(
        cache_key,
        lambda: list(
            Product.objects.filter(
                availability_status=Product.AvailabilityStatus.AVAILABLE,
                **({"category__slug": category_slug} if category_slug else {}),
            ).select_related("category")
        ),
    )

    active_category = None
    if category_slug:
        active_category = get_object_or_404(Category, slug=category_slug)

    return render(
        request,
        "shop/product_list.html",
        {
            "products": products,
            "categories": categories,
            "active_category": active_category,
        },
    )


def product_detail(request, category_slug, slug):
    from growth.models import GrowthEvent

    product = get_object_or_404(
        Product.objects.select_related("category"),
        category__slug=category_slug,
        slug=slug,
    )
    _track_conversion(GrowthEvent.EventType.PRODUCT_VIEW, request, product=product)

    from intelligence.recommendation_service import RecommendationService
    from intelligence.models import UpsellImpression
    from intelligence.upsell_service import UpsellService

    related_products = RecommendationService.for_product(
        product,
        user=request.user if request.user.is_authenticated else None,
        limit=4,
    )
    UpsellService.log_impression(
        UpsellImpression.Slot.PRODUCT,
        related_products,
        user=request.user if request.user.is_authenticated else None,
        session_key=request.session.session_key or "",
    )
    return render(
        request,
        "shop/product_detail.html",
        {
            "product": product,
            "related_products": related_products,
        },
    )


@require_POST
def add_to_cart(request):
    product = get_object_or_404(Product, pk=request.POST.get("product_id"))
    quantity = int(request.POST.get("quantity", 1))
    cart = _get_cart(request)

    try:
        from growth.models import GrowthEvent

        add_item(cart, product, quantity)
        _track_conversion(GrowthEvent.EventType.ADD_TO_CART, request, product=product, cart=cart)
        messages.success(request, f"«{product.name}» به سبد خرید اضافه شد.")
    except (ProductUnavailableError, InvalidQuantityError) as exc:
        messages.error(request, str(exc))

    next_url = request.POST.get("next") or product.get_absolute_url()
    return HttpResponseRedirect(next_url)


def cart_view(request):
    cart = _get_cart(request)
    items = cart.items.select_related("product", "product__category")

    if request.method == "POST":
        action = request.POST.get("action")
        product_id = request.POST.get("product_id")

        if action == "remove" and product_id:
            product = get_object_or_404(Product, pk=product_id)
            remove_item(cart, product)
            messages.info(request, f"«{product.name}» از سبد خرید حذف شد.")
            return redirect("core:cart")

        if action == "update":
            for item in items:
                quantity = request.POST.get(f"quantity_{item.pk}")
                if quantity is None:
                    continue
                try:
                    qty = int(quantity)
                    if qty <= 0:
                        remove_item(cart, item.product)
                    else:
                        set_item_quantity(cart, item.product, qty)
                except (ValueError, ProductUnavailableError, InvalidQuantityError) as exc:
                    messages.error(request, str(exc))
            messages.success(request, "سبد خرید بروزرسانی شد.")
            return redirect("core:cart")

    items = cart.items.select_related("product", "product__category")

    from intelligence.upsell_service import UpsellService

    upsell_products = UpsellService.for_cart(
        cart,
        user=request.user if request.user.is_authenticated else None,
    )

    return render(
        request,
        "pages/cart.html",
        {
            "cart": cart,
            "items": items,
            "upsell_products": upsell_products,
        },
    )


def checkout(request):
    cart = _get_cart(request)
    items = cart.items.select_related("product", "product__category")

    if cart.is_empty:
        messages.warning(request, "سبد خرید شما خالی است.")
        return redirect("core:cart")

    from growth.models import GrowthEvent

    _track_conversion(GrowthEvent.EventType.CHECKOUT_START, request, cart=cart)

    initial = {}
    if request.user.is_authenticated:
        initial.update(get_checkout_initial(request.user))
    initial.update(get_checkout_table_initial(request))
    form = CheckoutForm(initial=initial or None)

    from intelligence.upsell_service import UpsellService

    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if form.is_valid():
            sync_table_from_pickup_note(request, form.cleaned_data.get("pickup_note", ""))
            customer = {
                key: form.cleaned_data[key]
                for key in (
                    "email",
                    "first_name",
                    "last_name",
                    "phone",
                    "address_line1",
                    "address_line2",
                    "city",
                    "state",
                    "postal_code",
                    "country",
                    "notes",
                )
            }
            payment_method = form.cleaned_data["payment_method"]
            user = request.user if request.user.is_authenticated else None

            try:
                if payment_method == Order.PaymentMethod.ONLINE:
                    result = process_checkout(cart, customer, user=user)
                elif payment_method in {
                    Order.PaymentMethod.CASH,
                    Order.PaymentMethod.COUNTER_CARD,
                }:
                    result = process_counter_checkout(
                        cart,
                        customer,
                        payment_method=payment_method,
                        user=user,
                    )
                else:
                    raise CheckoutError("روش پرداخت انتخاب‌شده پشتیبانی نمی‌شود.")
            except (CheckoutError, EmptyCartError) as exc:
                messages.error(request, str(exc))
                return redirect("core:cart")

            _track_conversion(
                GrowthEvent.EventType.CHECKOUT_COMPLETE,
                request,
                cart=cart,
                order=result.order,
            )

            if payment_method == Order.PaymentMethod.ONLINE:
                if not result.checkout_url:
                    messages.error(
                        request,
                        "پرداخت آنلاین در حال حاضر در دسترس نیست. لطفاً دوباره تلاش کنید.",
                    )
                    return redirect("core:cart")

                return render(
                    request,
                    "pages/checkout_redirect.html",
                    {
                        "order": result.order,
                        "payment": result.payment,
                        "checkout_url": result.checkout_url,
                    },
                )

            grant_checkout_order_access(request, result.order.order_number)
            counter_message = (
                COUNTER_CASH_MESSAGE
                if payment_method == Order.PaymentMethod.CASH
                else COUNTER_CARD_MESSAGE
            )
            messages.success(request, counter_message)

            if user:
                return redirect("accounts:order_detail", order_number=result.order.order_number)

            return redirect("core:order_confirmation", order_number=result.order.order_number)

    return render(
        request,
        "pages/checkout.html",
        {
            "cart": cart,
            "items": items,
            "form": form,
            "checkout_upsell_products": UpsellService.for_checkout(
                cart,
                user=request.user if request.user.is_authenticated else None,
            ),
        },
    )


def order_confirmation(request, order_number):
    order = get_object_or_404(
        Order.objects.prefetch_related("items", "payments"),
        order_number=order_number,
    )

    from core.checkout_access import can_view_checkout_order

    if not can_view_checkout_order(request, order):
        messages.warning(request, "برای مشاهده این سفارش وارد شوید.")
        return redirect(f"{reverse('accounts:login')}?next={reverse('core:order_confirmation', args=[order_number])}")

    return render(
        request,
        "pages/order_confirmation.html",
        {"order": order},
    )


def order_receipt(request, order_number):
    order = get_object_or_404(
        Order.objects.prefetch_related("items", "payments"),
        order_number=order_number,
    )

    from core.checkout_access import can_view_checkout_order

    if not can_view_checkout_order(request, order):
        messages.warning(request, "برای مشاهده این رسید وارد شوید.")
        return redirect(f"{reverse('accounts:login')}?next={reverse('core:order_receipt', args=[order_number])}")

    return render(
        request,
        "pages/order_receipt.html",
        {"order": order},
    )


def checkout_redirect_info(request):
    return render(request, "pages/checkout_redirect.html", {"checkout_url": None})
