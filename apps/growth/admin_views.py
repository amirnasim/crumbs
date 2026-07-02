from django.contrib import admin
from django.shortcuts import render

from growth.revenue_analytics import get_growth_dashboard_snapshot
from growth.services import get_analytics_snapshot


def analytics_dashboard(request):
    days = int(request.GET.get("days", 30))
    snapshot = get_analytics_snapshot(days=days)
    context = {
        **admin.site.each_context(request),
        "title": "CRUMBS Analytics",
        "snapshot": snapshot,
        "days": days,
    }
    return render(request, "admin/growth/analytics_dashboard.html", context)


def growth_control_panel(request):
    days = int(request.GET.get("days", 30))
    snapshot = get_growth_dashboard_snapshot(days=days)
    context = {
        **admin.site.each_context(request),
        "title": "Growth Control Panel",
        "snapshot": snapshot,
        "days": days,
    }
    return render(request, "admin/growth/growth_control_panel.html", context)
