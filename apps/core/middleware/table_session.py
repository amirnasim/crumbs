from core.table_session import capture_table_from_query, should_capture_table


class CafeTableSessionMiddleware:
    """Persist ?table= from shop/cart/checkout URLs into the session."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if should_capture_table(request):
            capture_table_from_query(request)
        return self.get_response(request)
