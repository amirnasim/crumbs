"""Read-through cache helpers for public catalog pages (no business logic)."""

from collections.abc import Callable
from typing import TypeVar

from django.core.cache import cache
from django.conf import settings

T = TypeVar("T")


def cache_get_or_set(key: str, factory: Callable[[], T], *, timeout: int | None = None) -> T:
    value = cache.get(key)
    if value is not None:
        return value
    value = factory()
    cache.set(key, value, timeout or settings.CACHE_TIMEOUT_CATALOG)
    return value


def invalidate_catalog_cache() -> None:
    """Optional manual bust — call after bulk product updates in admin."""
    from django.core.cache import cache

    keys = [
        "crumbs:categories:all",
        "crumbs:home:featured",
        "crumbs:home:best_sellers",
        "crumbs:catalog:products:all",
    ]
    keys.extend(
        f"crumbs:catalog:products:{slug}"
        for slug in cache.get("crumbs:category_slugs", []) or []
    )
    cache.delete_many(keys)
