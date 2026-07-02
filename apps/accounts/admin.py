from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth import get_user_model

from .models import Address, CustomerProfile

User = get_user_model()


class CustomerProfileInline(admin.StackedInline):
    model = CustomerProfile
    can_delete = False
    extra = 0


class AddressInline(admin.TabularInline):
    model = Address
    extra = 0
    fields = ("label", "city", "is_default", "phone")


if admin.site.is_registered(User):
    admin.site.unregister(User)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = (CustomerProfileInline, AddressInline)
    list_display = ("username", "email", "first_name", "last_name", "is_staff", "date_joined")
    search_fields = ("username", "email", "first_name", "last_name")


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("user", "label", "city", "is_default", "updated_at")
    list_filter = ("is_default", "city", "country")
    search_fields = ("user__username", "user__email", "label", "city", "postal_code")
