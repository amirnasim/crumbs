from django.urls import path

from . import views

app_name = "wishlist"

urlpatterns = [
    path("", views.wishlist_view, name="wishlist"),
    path("add/", views.wishlist_add, name="add"),
    path("remove/", views.wishlist_remove, name="remove"),
]
