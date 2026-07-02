from decimal import Decimal

from django.conf import settings
from django.db import models


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING_PAYMENT = "pending_payment", "Pending Payment"
        AWAITING_PAYMENT = "awaiting_payment", "Awaiting Payment"
        PAID = "paid", "Paid"
        CONFIRMED_BY_SHOP = "confirmed_by_shop", "Confirmed by Shop"
        PREPARING = "preparing", "Preparing"
        PACKAGED = "packaged", "Packaged"
        OUT_FOR_DELIVERY = "out_for_delivery", "Out for Delivery"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"
        REFUNDED = "refunded", "Refunded"

    class PaymentStatus(models.TextChoices):
        PENDING_PAYMENT = "pending_payment", "Pending Payment"
        PAID = "paid", "Paid"
        COD_PENDING = "cod_pending", "COD Pending"
        COD_CONFIRMED = "cod_confirmed", "COD Confirmed"
        CASH_RECEIVED = "cash_received", "Cash Received"
        FAILED = "failed", "Failed"
        REFUND_REQUESTED = "refund_requested", "Refund Requested"
        REFUND_PROCESSED = "refund_processed", "Refund Processed"

    class PaymentMethod(models.TextChoices):
        COD = "cod", "Cash on Delivery"
        ONLINE = "online", "Online Payment"
        CASH = "cash", "Cash at Counter"
        COUNTER_CARD = "counter_card", "Card at Counter"

    class FulfillmentType(models.TextChoices):
        PICKUP = "pickup", "In-cafe pickup"
        COURIER = "courier", "Courier (legacy)"
        EXPRESS = "express", "Express (legacy)"
        COD = "cod", "COD (legacy)"

    DeliveryType = FulfillmentType

    order_number = models.CharField("شماره سفارش", max_length=32, unique=True, db_index=True)
    daily_sequence = models.PositiveIntegerField("شماره روزانه", null=True, blank=True, db_index=True)
    daily_sequence_date = models.DateField("تاریخ شماره روزانه", null=True, blank=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="orders",
    )

    status = models.CharField(
        "وضعیت",
        max_length=30,
        choices=Status.choices,
        default=Status.PENDING_PAYMENT,
        db_index=True,
    )
    payment_status = models.CharField(
        "وضعیت پرداخت",
        max_length=30,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING_PAYMENT,
        db_index=True,
    )
    payment_method = models.CharField(
        "روش پرداخت",
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.ONLINE,
        db_index=True,
    )
    delivery_type = models.CharField(
        "نوع دریافت",
        max_length=20,
        choices=FulfillmentType.choices,
        default=FulfillmentType.PICKUP,
        db_index=True,
        help_text="Active in-cafe orders use pickup. Legacy courier/COD values are retained for history.",
    )

    email = models.EmailField("ایمیل")
    phone = models.CharField("شماره تماس", max_length=30, blank=True)
    first_name = models.CharField("نام", max_length=100)
    last_name = models.CharField("نام خانوادگی", max_length=100)

    address_line1 = models.CharField(max_length=255, blank=True, default="")
    address_line2 = models.CharField(max_length=255, blank=True, default="")
    city = models.CharField(max_length=100, blank=True, default="")
    state = models.CharField(max_length=100, blank=True, default="")
    postal_code = models.CharField(max_length=20, blank=True, default="")
    country = models.CharField(max_length=100, default="Iran")

    delivery_zone = models.ForeignKey(
        "fulfillment.DeliveryZone",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="orders",
        verbose_name="منطقه ارسال (قدیمی)",
    )
    delivery_fee = models.DecimalField(
        "هزینه ارسال (قدیمی)",
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    fulfillment_date = models.DateField("تاریخ تحویل", null=True, blank=True, db_index=True)

    subtotal = models.DecimalField("جمع جزء", max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField("تخفیف", max_digits=10, decimal_places=2, default=Decimal("0.00"))
    promotion_discount_amount = models.DecimalField(
        "تخفیف پروموشن",
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    total = models.DecimalField("مبلغ نهایی", max_digits=10, decimal_places=2)
    coupon = models.ForeignKey(
        "growth.Coupon",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="orders",
    )
    referral_code_applied = models.CharField(max_length=16, blank=True, db_index=True)
    notes = models.TextField("یادداشت", blank=True)

    created_at = models.DateTimeField("تاریخ ثبت", auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField("آخرین بروزرسانی", auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "سفارش"
        verbose_name_plural = "سفارش‌ها"
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["payment_status", "created_at"]),
            models.Index(fields=["payment_method", "status"]),
            models.Index(fields=["fulfillment_date", "status"]),
            models.Index(fields=["daily_sequence_date", "daily_sequence"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["daily_sequence_date", "daily_sequence"],
                condition=models.Q(daily_sequence__isnull=False),
                name="orders_unique_daily_sequence_per_date",
            ),
        ]

    def __str__(self):
        return self.order_number

    @property
    def display_number(self) -> str:
        if self.daily_sequence:
            return f"#{self.daily_sequence}"
        return ""

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def total_items(self) -> int:
        return sum(item.quantity for item in self.items.all())

    @property
    def is_cod(self) -> bool:
        return self.payment_method == self.PaymentMethod.COD

    @property
    def is_counter_payment(self) -> bool:
        return self.payment_method in {
            self.PaymentMethod.CASH,
            self.PaymentMethod.COUNTER_CARD,
        }

    @property
    def is_in_cafe_pickup_order(self) -> bool:
        return self.delivery_type == self.FulfillmentType.PICKUP

    @property
    def fulfillment_type(self) -> str:
        return self.delivery_type

    def get_fulfillment_type_display(self) -> str:
        return self.get_delivery_type_display()

    @property
    def has_legacy_delivery_details(self) -> bool:
        return (
            self.delivery_type
            in {
                self.FulfillmentType.COURIER,
                self.FulfillmentType.EXPRESS,
                self.FulfillmentType.COD,
            }
            or self.delivery_zone_id is not None
            or bool((self.address_line1 or "").strip())
            or self.delivery_fee > 0
        )


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.PROTECT,
        related_name="order_items",
    )
    product_name = models.CharField("نام محصول", max_length=200)
    unit_price = models.DecimalField("قیمت واحد", max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField("تعداد")
    line_total = models.DecimalField("جمع خط", max_digits=10, decimal_places=2)
    fulfillment_date = models.DateField("تاریخ تحویل", null=True, blank=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "قلم سفارش"
        verbose_name_plural = "اقلام سفارش"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1),
                name="order_item_quantity_positive",
            ),
        ]

    def __str__(self):
        return f"{self.quantity} x {self.product_name}"
