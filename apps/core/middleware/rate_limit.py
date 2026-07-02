"""Basic IP rate limiting for sensitive endpoints (login, checkout)."""

import logging

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponseForbidden

logger = logging.getLogger("crumbs.security")


class RateLimitMiddleware:
    """
    Sliding-window rate limiter backed by the default cache backend.
    Does not modify business logic — rejects excess requests at the edge.
    """

    DEFAULT_PATHS = {
        "/accounts/login/": (10, 60),
        "/checkout/": (5, 60),
    }

    def __init__(self, get_response):
        self.get_response = get_response
        self.paths = getattr(settings, "RATE_LIMIT_PATHS", self.DEFAULT_PATHS)

    def __call__(self, request):
        if request.method == "POST" and not settings.DEBUG:
            limit_config = self._match_path(request.path)
            if limit_config and self._is_limited(request, limit_config):
                logger.warning(
                    "Rate limit exceeded path=%s ip=%s",
                    request.path,
                    self._client_ip(request),
                )
                return HttpResponseForbidden("تعداد درخواست‌ها بیش از حد مجاز است. لطفاً کمی صبر کنید.")

        return self.get_response(request)

    def _match_path(self, path: str) -> tuple[int, int] | None:
        for prefix, config in self.paths.items():
            if path.startswith(prefix):
                return config
        return None

    def _client_ip(self, request) -> str:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "unknown")

    def _is_limited(self, request, config: tuple[int, int]) -> bool:
        max_requests, window_seconds = config
        ip = self._client_ip(request)
        key = f"ratelimit:{request.path}:{ip}"
        count = cache.get(key, 0)
        if count >= max_requests:
            return True
        cache.set(key, count + 1, window_seconds)
        return False
