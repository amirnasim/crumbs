"""Test data factories — lightweight helpers (no DB coupling in business code)."""

from decimal import Decimal

from django.contrib.auth import get_user_model

from accounts.models import CustomerProfile
from cart.models import Cart, CartItem
from cart.services import add_item
from delivery.models import DeliveryZone
from growth.models import Coupon, ReferralCode
from inventory.models import ProductInventory
from notifications.models import SMSTemplate
from orders.models import Order, OrderItem
from products.models import Category, Product

User = get_user_model()

CUSTOMER = {
    "email": "buyer@example.com",
    "first_name": "Ali",
    "last_name": "Rezaei",
    "phone": "09121234567",
}

LEGACY_DELIVERY_CUSTOMER = {
    **CUSTOMER,
    "address_line1": "Valiasr St 1",
    "city": "Tehran",
    "state": "Tehran",
    "postal_code": "1234567890",
    "country": "Iran",
}


def create_user(*, username="buyer", email="buyer@example.com", password="pass12345", phone="09121234567"):
    user = User.objects.create_user(username=username, email=email, password=password, first_name="Ali")
    CustomerProfile.objects.update_or_create(user=user, defaults={"phone": phone})
    return user


def create_delivery_zone():
    zone, _ = DeliveryZone.objects.get_or_create(
        code=DeliveryZone.ZoneCode.TEHRAN,
        defaults={
            "name": "Tehran",
            "cities": ["Tehran", "تهران"],
            "states": ["Tehran"],
            "delivery_fee": Decimal("50000"),
            "min_order_amount": Decimal("0"),
            "is_active": True,
        },
    )
    return zone


def create_category(*, name="Cookies", slug="cookies"):
    return Category.objects.get_or_create(slug=slug, defaults={"name": name})[0]


def create_product(
    *,
    name="Chocolate Cookie",
    price=Decimal("150000"),
    stock_quantity=50,
    category=None,
):
    category = category or create_category()
    product, _ = Product.objects.get_or_create(
        category=category,
        slug=name.lower().replace(" ", "-"),
        defaults={
            "name": name,
            "description": "Test product",
            "price": price,
            "availability_status": Product.AvailabilityStatus.AVAILABLE,
            "is_featured": True,
        },
    )
    inventory, _ = ProductInventory.objects.get_or_create(
        product=product,
        defaults={"track_stock": True, "stock_quantity": stock_quantity, "low_stock_threshold": 2},
    )
    if inventory.stock_quantity != stock_quantity:
        inventory.stock_quantity = stock_quantity
        inventory.reserved_quantity = 0
        inventory.save(update_fields=["stock_quantity", "reserved_quantity", "updated_at"])
    return product


def create_cart_with_item(user, product, *, quantity=1):
    cart, _ = Cart.objects.get_or_create(user=user)
    add_item(cart, product, quantity)
    return cart


def create_coupon(
    *,
    code="TEST10",
    discount_value=10,
    discount_type=Coupon.DiscountType.PERCENTAGE,
    campaign_type=Coupon.CampaignType.GENERAL,
    usage_limit_per_user=1,
    usage_limit_global=None,
    stackable=False,
):
    return Coupon.objects.create(
        code=code,
        name=f"Coupon {code}",
        discount_type=discount_type,
        discount_value=Decimal(str(discount_value)),
        campaign_type=campaign_type,
        usage_limit_per_user=usage_limit_per_user,
        usage_limit_global=usage_limit_global,
        stackable=stackable,
        is_active=True,
    )


def create_order(
    user,
    product,
    *,
    payment_status=Order.PaymentStatus.PAID,
    status=Order.Status.PAID,
    payment_method=Order.PaymentMethod.ONLINE,
    delivery_type=Order.DeliveryType.PICKUP,
    delivery_fee=Decimal("0"),
    delivery_zone=None,
    discount_amount=Decimal("0"),
):
    zone = delivery_zone
    if zone is None and (delivery_fee > 0 or payment_method == Order.PaymentMethod.COD):
        zone = create_delivery_zone()
    subtotal = product.price
    order = Order.objects.create(
        order_number=f"CR-TEST-{Order.objects.count() + 1:04d}",
        user=user,
        email=user.email,
        phone="09121234567",
        first_name="Ali",
        last_name="Rezaei",
        address_line1="Valiasr" if zone else "",
        city="Tehran" if zone else "",
        state="Tehran" if zone else "",
        postal_code="1234567890" if zone else "",
        payment_method=payment_method,
        delivery_type=delivery_type,
        payment_status=payment_status,
        status=status,
        delivery_zone=zone,
        delivery_fee=delivery_fee,
        subtotal=subtotal,
        discount_amount=discount_amount,
        total=subtotal + delivery_fee - discount_amount,
    )
    OrderItem.objects.create(
        order=order,
        product=product,
        product_name=product.name,
        unit_price=product.price,
        quantity=1,
        line_total=product.price,
    )
    from orders.daily_sequence import assign_daily_sequence

    assign_daily_sequence(order)
    return order


def create_referral_code(user):
    from growth.referral_service import ReferralService

    return ReferralService.get_or_create_code(user)


def seed_sms_templates():
    templates = [
        ("order_created", "order", "Order {{ order_number }} created"),
        ("payment_success", "payment", "Payment success {{ order_number }}"),
        ("payment_failed", "payment", "Payment failed"),
        ("order_preparing", "order", "Order {{ order_number }} is preparing"),
    ]
    created = []
    for code, category, body in templates:
        obj, _ = SMSTemplate.objects.update_or_create(
            code=code,
            defaults={"name": code, "category": category, "body": body, "is_active": True},
        )
        created.append(obj)
    return created
