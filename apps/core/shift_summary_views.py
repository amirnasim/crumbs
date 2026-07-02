"""Staff daily shift summary page."""

from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

from core.shift_summary import build_shift_summary, parse_shift_date


@staff_member_required
def shift_summary(request):
    raw_date = request.GET.get("date", "").strip()
    try:
        selected_date = parse_shift_date(raw_date or None)
    except ValueError:
        selected_date = parse_shift_date(None)

    summary = build_shift_summary(selected_date)
    context = {
        **admin.site.each_context(request),
        "title": "Shift Summary",
        "selected_date": summary.selected_date,
        "summary": summary,
    }
    return render(request, "admin/shift_summary.html", context)
