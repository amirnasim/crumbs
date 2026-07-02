"""Staff order quick lookup page."""

from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

from core.order_lookup import (
    DEFAULT_LOOKUP_LIMIT,
    SEARCH_LOOKUP_LIMIT,
    order_is_kitchen_relevant,
    order_is_pickup_relevant,
    recent_active_orders_queryset,
    search_orders_queryset,
)


@staff_member_required
def order_lookup(request):
    query = request.GET.get("q", "").strip()
    is_search = bool(query)

    if is_search:
        orders = list(search_orders_queryset(query))
        result_limit = SEARCH_LOOKUP_LIMIT
    else:
        orders = list(recent_active_orders_queryset())
        result_limit = DEFAULT_LOOKUP_LIMIT

    order_rows = []
    for order in orders:
        order_rows.append(
            {
                "order": order,
                "show_kitchen_link": order_is_kitchen_relevant(order),
                "show_pickup_link": order_is_pickup_relevant(order),
            }
        )

    context = {
        **admin.site.each_context(request),
        "title": "Order Lookup",
        "query": query,
        "is_search": is_search,
        "result_limit": result_limit,
        "order_rows": order_rows,
    }
    return render(request, "admin/order_lookup.html", context)
