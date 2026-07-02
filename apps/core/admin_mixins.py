"""Shared Django admin mixins."""

from __future__ import annotations


class NoBulkDeleteMixin:
    """Remove dangerous bulk-delete from admin changelist actions."""

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions


class NoDeleteMixin(NoBulkDeleteMixin):
    """Disable single-object and bulk delete in admin."""

    def has_delete_permission(self, request, obj=None):
        return False
