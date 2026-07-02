from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path("webhooks/stripe/", views.stripe_webhook, name="stripe-webhook"),
    path("zarinpal/callback/", views.zarinpal_callback, name="zarinpal-callback"),
    path(
        "orders/<str:order_number>/checkout/",
        views.create_checkout_session,
        name="create-checkout-session",
    ),
]
