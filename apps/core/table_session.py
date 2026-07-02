"""In-cafe table QR session — store table number from ?table= query param."""

SESSION_CAFE_TABLE = "cafe_table_number"
MAX_TABLE_LENGTH = 20


def sanitize_table_number(value) -> str:
    """Return a short printable table identifier, at most 20 characters."""
    if value is None:
        return ""
    text = str(value).strip()
    text = "".join(ch for ch in text if ch.isprintable() and ch not in "\r\n\t")
    text = text.strip()
    if not text:
        return ""
    return text[:MAX_TABLE_LENGTH]


def set_table_in_session(request, value: str) -> None:
    table = sanitize_table_number(value)
    if table:
        request.session[SESSION_CAFE_TABLE] = table
    else:
        request.session.pop(SESSION_CAFE_TABLE, None)
    request.session.modified = True


def get_table_from_session(request) -> str:
    return sanitize_table_number(request.session.get(SESSION_CAFE_TABLE, ""))


def clear_table_from_session(request) -> None:
    if SESSION_CAFE_TABLE in request.session:
        request.session.pop(SESSION_CAFE_TABLE, None)
        request.session.modified = True


def capture_table_from_query(request) -> str:
    """Read ?table= from the query string and persist it in session."""
    if "table" not in request.GET:
        return get_table_from_session(request)

    table = sanitize_table_number(request.GET.get("table"))
    set_table_in_session(request, table)
    return table


def should_capture_table(request) -> bool:
    if request.method != "GET" or "table" not in request.GET:
        return False
    path = request.path
    return path == "/cart/" or path.startswith("/shop/") or path.startswith("/checkout/")


def sync_table_from_pickup_note(request, pickup_note: str) -> None:
    """Keep session aligned with checkout pickup note edits."""
    set_table_in_session(request, pickup_note)


def get_checkout_table_initial(request) -> dict:
    table = get_table_from_session(request)
    if table:
        return {"pickup_note": table}
    return {}
