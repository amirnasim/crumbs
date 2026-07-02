from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("about/", views.about, name="about"),
    path("contact/", views.contact, name="contact"),
    path("cart/", views.cart_view, name="cart"),
    path("cart/add/", views.add_to_cart, name="add_to_cart"),
    path("checkout/", views.checkout, name="checkout"),
    path(
        "checkout/confirmation/<str:order_number>/",
        views.order_confirmation,
        name="order_confirmation",
    ),
    path(
        "orders/<str:order_number>/receipt/",
        views.order_receipt,
        name="order_receipt",
    ),
    path("checkout/redirect/", views.checkout_redirect_info, name="checkout_redirect_info"),
]
