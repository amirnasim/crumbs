from django.db import transaction

from core.observability import log_order_event
from delivery.exceptions import InvalidTransitionError
from delivery.models import OrderStatusLog
from delivery.state_machine import STATUS_TO_SMS_EVENT, validate_transition
from orders.exceptions import CheckoutError
from orders.models import Order
from products.services.stock_service import StockService


class OrderService:
    """Single entry point for all order lifecycle mutations."""

    @staticmethod
    @transaction.atomic
    def transition(
        order: Order,
        new_status: str,
        *,
        note: str = "",
        actor: str = "system",
    ) -> Order:
        order = Order.objects.select_for_update().get(pk=order.pk)
        previous = order.status
        validate_transition(order, new_status)

        if previous == new_status:
            return order

        order.status = new_status
        order.save(update_fields=["status", "updated_at"])
        OrderStatusLog.objects.create(
            order=order,
            from_status=previous,
            to_status=new_status,
            note=note,
            actor=actor,
        )
        return order

    @staticmethod
    @transaction.atomic
    def cancel(order: Order, *, reason: str = "", actor: str = "admin") -> Order:
        order = Order.objects.select_for_update().get(pk=order.pk)
        if order.status in {Order.Status.CANCELLED, Order.Status.REFUNDED}:
            return order

        StockService.release_reservations(order)
        log_order_event("stock_reservations_released", order_id=order.pk, status=order.status)
        if order.payment_status == Order.PaymentStatus.PENDING_PAYMENT:
            order.payment_status = Order.PaymentStatus.FAILED
            order.save(update_fields=["payment_status", "updated_at"])
        OrderService.transition(order, Order.Status.CANCELLED, note=reason, actor=actor)
        return order

    @staticmethod
    @transaction.atomic
    def mark_payment_failed(order: Order, *, reason: str = "", actor: str = "system") -> Order:
        order = Order.objects.select_for_update().get(pk=order.pk)
        if order.payment_status in {
            Order.PaymentStatus.PAID,
            Order.PaymentStatus.CASH_RECEIVED,
        }:
            return order
        if order.status in {Order.Status.CANCELLED, Order.Status.REFUNDED}:
            return order

        StockService.release_reservations(order)
        log_order_event("stock_reservations_released", order_id=order.pk, status=order.status)
        order.payment_status = Order.PaymentStatus.FAILED
        order.save(update_fields=["payment_status", "updated_at"])
        OrderService.transition(order, Order.Status.CANCELLED, note=reason, actor=actor)
        log_order_event(
            "order_payment_failed",
            order_id=order.pk,
            status=order.status,
            outcome="cancelled",
        )
        return order

    @staticmethod
    @transaction.atomic
    def request_refund(order: Order, *, reason: str = "", actor: str = "admin") -> Order:
        order = Order.objects.select_for_update().get(pk=order.pk)
        order.payment_status = Order.PaymentStatus.REFUND_REQUESTED
        order.save(update_fields=["payment_status", "updated_at"])
        OrderStatusLog.objects.create(
            order=order,
            from_status=order.status,
            to_status=order.status,
            note=f"Refund requested: {reason}",
            actor=actor,
        )
        return order

    @staticmethod
    @transaction.atomic
    def process_refund(order: Order, *, reason: str = "", actor: str = "admin") -> Order:
        from payments.services import PaymentService

        order = Order.objects.select_for_update().get(pk=order.pk)
        if order.status == Order.Status.REFUNDED:
            return order

        PaymentService.process_refund(order)
        StockService.release_reservations(order)
        order.payment_status = Order.PaymentStatus.REFUND_PROCESSED
        order.save(update_fields=["payment_status", "updated_at"])
        OrderService.transition(order, Order.Status.REFUNDED, note=reason, actor=actor)
        return order

    @staticmethod
    @transaction.atomic
    def complete_delivery(order: Order, *, actor: str = "admin") -> Order:
        order = Order.objects.select_for_update().get(pk=order.pk)
        if order.is_cod:
            if order.payment_status != Order.PaymentStatus.CASH_RECEIVED:
                raise CheckoutError("COD orders require cash received before delivery completion.")
        else:
            StockService.fulfill_reservations(order)
        return OrderService.transition(order, Order.Status.DELIVERED, actor=actor)

    @staticmethod
    @transaction.atomic
    def reserve_stock(order: Order) -> None:
        StockService.reserve_for_order(order)

    @staticmethod
    @transaction.atomic
    def confirm_stock(order: Order) -> None:
        StockService.confirm_reservations(order)

    @staticmethod
    @transaction.atomic
    def release_stock(order: Order) -> None:
        StockService.release_reservations(order)

    @staticmethod
    def sms_event_for_status(status: str) -> str | None:
        return STATUS_TO_SMS_EVENT.get(status)

    @staticmethod
    def assert_transition(order: Order, new_status: str) -> None:
        validate_transition(order, new_status)

    @staticmethod
    @transaction.atomic
    def finalize_counter_payment(order: Order, *, actor: str = "admin") -> Order:
        order = Order.objects.select_for_update().get(pk=order.pk)
        if order.payment_status == Order.PaymentStatus.PAID and order.status == Order.Status.PREPARING:
            return order

        order.payment_status = Order.PaymentStatus.PAID
        order.save(update_fields=["payment_status", "updated_at"])
        StockService.confirm_reservations(order)
        log_order_event("stock_reservations_confirmed", order_id=order.pk, status=order.status)
        return OrderService.transition(
            order,
            Order.Status.PREPARING,
            note="Counter payment received",
            actor=actor,
        )

    @staticmethod
    @transaction.atomic
    def finalize_online_payment(order: Order) -> Order:
        order = Order.objects.select_for_update().get(pk=order.pk)
        if (
            order.payment_status == Order.PaymentStatus.PAID
            and order.status
            in {
                Order.Status.PAID,
                Order.Status.CONFIRMED_BY_SHOP,
                Order.Status.PREPARING,
                Order.Status.PACKAGED,
                Order.Status.OUT_FOR_DELIVERY,
                Order.Status.DELIVERED,
            }
        ):
            return order

        order.payment_status = Order.PaymentStatus.PAID
        order.save(update_fields=["payment_status", "updated_at"])
        StockService.confirm_reservations(order)
        log_order_event("stock_reservations_confirmed", order_id=order.pk, status=order.status)
        OrderService.transition(order, Order.Status.PAID, note="Online payment received")
        order = OrderService.transition(order, Order.Status.CONFIRMED_BY_SHOP, note="Auto-confirmed after payment")
        log_order_event("order_finalized", order_id=order.pk, status=order.status, outcome="online_payment")
        return order

    @staticmethod
    @transaction.atomic
    def finalize_cod_placement(order: Order) -> Order:
        order = Order.objects.select_for_update().get(pk=order.pk)
        order.payment_status = Order.PaymentStatus.COD_PENDING
        order.status = Order.Status.CONFIRMED_BY_SHOP
        order.save(update_fields=["payment_status", "status", "updated_at"])
        OrderStatusLog.objects.create(
            order=order,
            from_status=Order.Status.PENDING_PAYMENT,
            to_status=Order.Status.CONFIRMED_BY_SHOP,
            note="COD order placed — awaiting shop confirmation",
            actor="system",
        )
        return order

    @staticmethod
    @transaction.atomic
    def confirm_cod(order: Order, *, actor: str = "admin") -> Order:
        order = Order.objects.select_for_update().get(pk=order.pk)
        if order.payment_status != Order.PaymentStatus.COD_PENDING:
            raise CheckoutError("Order is not in COD pending state.")
        order.payment_status = Order.PaymentStatus.COD_CONFIRMED
        order.save(update_fields=["payment_status", "updated_at"])
        OrderStatusLog.objects.create(
            order=order,
            from_status=order.status,
            to_status=order.status,
            note="COD confirmed by shop",
            actor=actor,
        )
        return order

    @staticmethod
    @transaction.atomic
    def record_cash_received(order: Order, *, actor: str = "admin") -> Order:
        order = Order.objects.select_for_update().get(pk=order.pk)

        StockService.confirm_reservations(order)
        StockService.fulfill_reservations(order)

        update_fields: list[str] = []
        if order.payment_status != Order.PaymentStatus.CASH_RECEIVED:
            order.payment_status = Order.PaymentStatus.CASH_RECEIVED
            update_fields.append("payment_status")
        if update_fields:
            update_fields.append("updated_at")
            order.save(update_fields=update_fields)

        if order.status != Order.Status.DELIVERED:
            return OrderService.transition(
                order,
                Order.Status.DELIVERED,
                note="Cash received on delivery",
                actor=actor,
            )
        return order
