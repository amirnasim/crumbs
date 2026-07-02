from django.urls import path

from core import views

app_name = "products"

urlpatterns = [
    path("", views.product_list, name="product_list"),
    path("<slug:category_slug>/", views.product_list, name="category"),
    path(
        "<slug:category_slug>/<slug:slug>/",
        views.product_detail,
        name="product_detail",
    ),
]
