"""Attach request path to log records for the current request."""

from __future__ import annotations

import logging
from contextvars import ContextVar

_request_path: ContextVar[str | None] = ContextVar("request_path", default=None)


class RequestLogContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = _request_path.set(request.path)
        try:
            return self.get_response(request)
        finally:
            _request_path.reset(token)


class RequestPathLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not getattr(record, "request_path", None):
            path = _request_path.get()
            if path:
                record.request_path = path
        return True
