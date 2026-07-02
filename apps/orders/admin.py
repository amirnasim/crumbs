from django.contrib import admin, messages
from django.urls import reverse
from django.utils.html import format_html

from core.admin_labels import (
    ORDER_PAYMENT_METHOD_FA,
    ORDER_PAYMENT_STATUS_FA,
    STATUS_LABELS_FA,
    fa_label,
)
from core.admin_mixins import NoBulkDeleteMixin
from inventory.models import StockReservation
from orders.models import Order
from orders.services.order_service import OrderService
from payments.exceptions import PaymentConfigurationError, PaymentError
from payments.models import Payment
from payments.services import PaymentService

from .models import OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = (
        "product",
        "product_name",
        "unit_price",
        "quantity",
        "line_total",
        "fulfillment_date",
    )
    can_delete = False
    verbose_name = "قلم سفارش"
    verbose_name_plural = "اقلام سفارش"

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(NoBulkDeleteMixin, admin.ModelAdmin):
    actions = (
        "advance_to_preparing",
        "advance_to_packaged",
        "mark_delivered",
        "cancel_orders",
        "advance_to_out_for_delivery",
        "create_stripe_checkout",
        "mark_cash_received",
        "mark_card_received",
        "confirm_cod",
        "mark_cod_cash_received",
        "request_refund",
        "process_refund",
    )
    list_display = (
        "order_number",
        "customer_name",
        "phone",
        "status_fa",
        "payment_method_fa",
        "total",
        "created_at",
    )
    list_filter = ("status", "payment_method", "delivery_type", "created_at")
    search_fields = (
        "order_number",
        "daily_sequence",
        "email",
        "phone",
        "first_name",
        "last_name",
        "city",
        "notes",
    )
    readonly_fields = (
        "order_number",
        "daily_sequence",
        "daily_sequence_date",
        "receipt_link",
        "subtotal",
        "delivery_fee",
        "discount_amount",
        "promotion_discount_amount",
        "coupon",
        "referral_code_applied",
        "total",
        "payment_status",
        "created_at",
        "updated_at",
    )
    autocomplete_fields = ("user", "delivery_zone")
    inlines = (OrderItemInline,)
    fieldsets = (
        (
            "سفارش",
            {
                "fields": (
                    "order_number",
                    "daily_sequence",
                    "daily_sequence_date",
                    "receipt_link",
                    "user",
                    "status",
                    "payment_status",
                    "payment_method",
                    "fulfillment_date",
                    "notes",
                )
            },
        ),
        ("مشتری", {"fields": ("email", "phone", "first_name", "last_name")}),
        (
            "مبالغ",
            {
                "fields": (
                    "subtotal",
                    "discount_amount",
                    "promotion_discount_amount",
                    "coupon",
                    "referral_code_applied",
                    "total",
                    "created_at",
                    "updated_at",
                )
            },
        ),
        (
            "دریافت / تحویل (قدیمی)",
            {
                "classes": ("collapse",),
                "description": "سوابق پیک و COD قدیمی. سفارش‌های فعال کافه از نوع دریافت در محل هستند.",
                "fields": (
                    "delivery_type",
                    "delivery_zone",
                    "address_line1",
                    "address_line2",
                    "city",
                    "state",
                    "postal_code",
                    "country",
                    "delivery_fee",
                ),
            },
        ),
    )

    @admin.display(description="مشتری", ordering="first_name")
    def customer_name(self, obj):
        return obj.full_name or "—"

    @admin.display(description="وضعیت", ordering="status")
    def status_fa(self, obj):
        return fa_label(STATUS_LABELS_FA, obj.status)

    @admin.display(description="روش پرداخت", ordering="payment_method")
    def payment_method_fa(self, obj):
        return fa_label(ORDER_PAYMENT_METHOD_FA, obj.payment_method)

    @admin.display(description="وضعیت پرداخت", ordering="payment_status")
    def payment_status_fa(self, obj):
        return fa_label(ORDER_PAYMENT_STATUS_FA, obj.payment_status)

    @admin.display(description="شماره روزانه", ordering="daily_sequence")
    def daily_display_number(self, obj):
        return obj.display_number or "—"

    @admin.display(description="رسید")
    def receipt_link(self, obj):
        if not obj.pk:
            return "—"
        url = reverse("core:order_receipt", args=[obj.order_number])
        return format_html('<a href="{}" target="_blank">مشاهده رسید</a>', url)

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == "delivery_type":
            formfield.label = "نوع دریافت / تحویل"
        elif db_field.name == "delivery_fee":
            formfield.label = "هزینه ارسال (قدیمی)"
        elif db_field.name == "delivery_zone":
            formfield.label = "منطقه ارسال (قدیمی)"
        elif db_field.name == "order_number":
            formfield.label = "شماره سفارش"
        elif db_field.name == "payment_status":
            formfield.label = "وضعیت پرداخت"
        elif db_field.name == "payment_method":
            formfield.label = "روش پرداخت"
        elif db_field.name == "fulfillment_date":
            formfield.label = "تاریخ تحویل"
        return formfield

    def _cod_order_needs_finalization(self, order: Order) -> bool:
        payment = order.payments.filter(provider=Payment.Provider.COD).order_by("-created_at").first()
        if payment and payment.status != Payment.Status.SUCCEEDED:
            return True
        return StockReservation.objects.filter(
            order=order,
            status__in=[
                StockReservation.Status.ACTIVE,
                StockReservation.Status.CONFIRMED,
            ],
        ).exists()

    def save_model(self, request, obj, form, change):
        previous_payment_status = None
        if change and obj.pk:
            previous_payment_status = (
                Order.objects.filter(pk=obj.pk).values_list("payment_status", flat=True).first()
            )

        super().save_model(request, obj, form, change)

        if (
            obj.is_cod
            and obj.payment_status == Order.PaymentStatus.CASH_RECEIVED
            and (
                previous_payment_status != Order.PaymentStatus.CASH_RECEIVED
                or self._cod_order_needs_finalization(obj)
            )
        ):
            try:
                PaymentService.ensure_cod_cash_finalized(obj, actor=request.user.username)
            except Exception as exc:
                self.message_user(
                    request,
                    f"{obj.order_number}: {exc}",
                    level=messages.ERROR,
                )

    @admin.action(description="ایجاد جلسه پرداخت Stripe")
    def create_stripe_checkout(self, request, queryset):
        for order in queryset:
            try:
                payment = PaymentService.initiate_online(order)
            except (PaymentError, PaymentConfigurationError) as exc:
                self.message_user(request, f"{order.order_number}: {exc}", level=messages.ERROR)
                continue
            self.message_user(
                request,
                format_html("{}: <a href='{}' target='_blank'>Stripe</a>", order.order_number, payment.checkout_url),
                messages.SUCCESS,
            )

    @admin.action(description="ثبت دریافت نقد (صندوق)")
    def mark_cash_received(self, request, queryset):
        self._mark_counter_payment_received(
            request,
            queryset.filter(payment_method=Order.PaymentMethod.CASH),
            mark_fn=PaymentService.mark_counter_cash_received,
            action_label="cash received",
        )

    @admin.action(description="ثبت دریافت کارت (صندوق)")
    def mark_card_received(self, request, queryset):
        self._mark_counter_payment_received(
            request,
            queryset.filter(payment_method=Order.PaymentMethod.COUNTER_CARD),
            mark_fn=PaymentService.mark_counter_card_received,
            action_label="card received",
        )

    def _mark_counter_payment_received(self, request, queryset, *, mark_fn, action_label: str):
        finalized = 0
        skipped = 0
        for order in queryset:
            payment = (
                order.payments.filter(
                    provider__in=(Payment.Provider.CASH, Payment.Provider.COUNTER_CARD),
                    status__in=(Payment.Status.PENDING, Payment.Status.SUCCEEDED),
                )
                .order_by("-created_at")
                .first()
            )
            if payment is None:
                self.message_user(
                    request,
                    f"{order.order_number}: No counter payment record found.",
                    level=messages.ERROR,
                )
                continue

            payment_was_succeeded = payment.status == Payment.Status.SUCCEEDED
            order_was_preparing = order.status == Order.Status.PREPARING
            try:
                mark_fn(order, payment, actor=request.user.username)
            except Exception as exc:
                self.message_user(request, f"{order.order_number}: {exc}", level=messages.ERROR)
                continue

            payment.refresh_from_db()
            order.refresh_from_db()
            if payment_was_succeeded and order_was_preparing:
                skipped += 1
                self.message_user(
                    request,
                    f"{order.order_number}: Counter payment already recorded.",
                    level=messages.INFO,
                )
            else:
                finalized += 1

        if finalized:
            self.message_user(
                request,
                f"Recorded {action_label} for {finalized} order(s).",
                messages.SUCCESS,
            )
        elif not skipped:
            self.message_user(request, "No counter payment orders were updated.", level=messages.WARNING)

    @admin.action(description="تأیید سفارش COD قدیمی")
    def confirm_cod(self, request, queryset):
        count = 0
        for order in queryset.filter(payment_method=Order.PaymentMethod.COD):
            try:
                OrderService.confirm_cod(order, actor=request.user.username)
                count += 1
            except Exception as exc:
                self.message_user(request, f"{order.order_number}: {exc}", level=messages.ERROR)
        self.message_user(request, f"Confirmed {count} COD order(s).", messages.SUCCESS)

    @admin.action(description="ثبت دریافت نقد COD قدیمی")
    def mark_cod_cash_received(self, request, queryset):
        finalized = 0
        skipped = 0
        for order in queryset.filter(payment_method=Order.PaymentMethod.COD):
            payment = (
                order.payments.filter(provider=Payment.Provider.COD)
                .order_by("-created_at")
                .first()
            )
            if payment is None:
                self.message_user(
                    request,
                    f"{order.order_number}: No COD payment record found.",
                    level=messages.ERROR,
                )
                continue

            payment_was_succeeded = payment.status == Payment.Status.SUCCEEDED
            order_was_delivered = order.status == Order.Status.DELIVERED
            try:
                PaymentService.mark_cod_cash_received(order, payment, actor=request.user.username)
            except Exception as exc:
                self.message_user(request, f"{order.order_number}: {exc}", level=messages.ERROR)
                continue

            payment.refresh_from_db()
            order.refresh_from_db()
            if payment_was_succeeded and order_was_delivered:
                skipped += 1
                self.message_user(
                    request,
                    f"{order.order_number}: COD cash already recorded.",
                    level=messages.INFO,
                )
            else:
                finalized += 1

        if finalized:
            self.message_user(
                request,
                f"Recorded COD cash for {finalized} order(s).",
                messages.SUCCESS,
            )
        elif not skipped:
            self.message_user(request, "No COD orders were updated.", level=messages.WARNING)

    def _transition(self, request, queryset, new_status, *, action_label: str):
        updated = 0
        skipped = 0
        for order in queryset:
            previous_status = order.status
            try:
                OrderService.transition(order, new_status, actor=request.user.username)
            except Exception as exc:
                self.message_user(request, f"{order.order_number}: {exc}", level=messages.ERROR)
                continue

            order.refresh_from_db()
            if order.status == previous_status == new_status:
                skipped += 1
                self.message_user(
                    request,
                    f"{order.order_number}: already {action_label}.",
                    level=messages.INFO,
                )
            else:
                updated += 1

        if updated:
            self.message_user(
                request,
                f"Marked {updated} order(s) as {action_label}.",
                messages.SUCCESS,
            )
        elif not skipped:
            self.message_user(request, "No orders were updated.", level=messages.WARNING)

    @admin.action(description="علامت‌گذاری به عنوان در حال آماده‌سازی")
    def advance_to_preparing(self, request, queryset):
        self._transition(request, queryset, Order.Status.PREPARING, action_label="preparing")

    @admin.action(description="علامت‌گذاری به عنوان آماده تحویل")
    def advance_to_packaged(self, request, queryset):
        self._transition(request, queryset, Order.Status.PACKAGED, action_label="packaged")

    @admin.action(description="آماده دریافت در صندوق (گذار قدیمی)")
    def advance_to_out_for_delivery(self, request, queryset):
        self._transition(
            request,
            queryset,
            Order.Status.OUT_FOR_DELIVERY,
            action_label="ready for counter pickup",
        )

    @admin.action(description="علامت‌گذاری به عنوان تحویل‌شده")
    def mark_delivered(self, request, queryset):
        delivered = 0
        skipped = 0
        for order in queryset:
            previous_status = order.status
            try:
                OrderService.complete_delivery(order, actor=request.user.username)
            except Exception as exc:
                self.message_user(request, f"{order.order_number}: {exc}", level=messages.ERROR)
                continue

            order.refresh_from_db()
            if order.status == previous_status == Order.Status.DELIVERED:
                skipped += 1
                self.message_user(
                    request,
                    f"{order.order_number}: already picked up.",
                    level=messages.INFO,
                )
            else:
                delivered += 1

        if delivered:
            self.message_user(
                request,
                f"Marked {delivered} order(s) as picked up.",
                messages.SUCCESS,
            )
        elif not skipped:
            self.message_user(request, "No orders were picked up.", level=messages.WARNING)

    @admin.action(description="لغو سفارش")
    def cancel_orders(self, request, queryset):
        for order in queryset:
            OrderService.cancel(order, reason="Cancelled via admin", actor=request.user.username)
        self.message_user(request, "Orders cancelled.", messages.SUCCESS)

    @admin.action(description="درخواست استرداد")
    def request_refund(self, request, queryset):
        for order in queryset:
            OrderService.request_refund(order, actor=request.user.username)
        self.message_user(request, "Refund requested.", messages.SUCCESS)

    @admin.action(description="پردازش استرداد")
    def process_refund(self, request, queryset):
        for order in queryset:
            OrderService.process_refund(order, actor=request.user.username)
        self.message_user(request, "Refunds processed.", messages.SUCCESS)
