from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from products.models import Product

from .models import WishlistItem


@login_required
def wishlist_view(request):
    items = WishlistItem.objects.filter(user=request.user).select_related(
        "product", "product__category"
    )
    return render(request, "wishlist/wishlist.html", {"items": items})


@login_required
@require_POST
def wishlist_add(request):
    product = get_object_or_404(Product, pk=request.POST.get("product_id"))
    _, created = WishlistItem.objects.get_or_create(user=request.user, product=product)
    if created:
        messages.success(request, f"«{product.name}» به علاقه‌مندی‌ها اضافه شد.")
    else:
        messages.info(request, "این محصول قبلاً در علاقه‌مندی‌ها بود.")
    next_url = request.POST.get("next") or product.get_absolute_url()
    return redirect(next_url)


@login_required
@require_POST
def wishlist_remove(request):
    product = get_object_or_404(Product, pk=request.POST.get("product_id"))
    WishlistItem.objects.filter(user=request.user, product=product).delete()
    messages.info(request, f"«{product.name}» از علاقه‌مندی‌ها حذف شد.")
    next_url = request.POST.get("next") or "wishlist:wishlist"
    return redirect(next_url)
