"""Shared payment settings overrides for tests."""

STRIPE_ONLINE_SETTINGS = {
    "DEFAULT_PAYMENT_METHOD": "online",
    "DEFAULT_PAYMENT_PROVIDER": "stripe",
    "PAYMENT_PROVIDER": "stripe",
    "STRIPE_ENABLED": True,
}

ZARINPAL_INTEGRATION_SETTINGS = {
    "DEFAULT_PAYMENT_METHOD": "online",
    "DEFAULT_PAYMENT_PROVIDER": "zarinpal",
    "PAYMENT_PROVIDER": "zarinpal",
    "ZARINPAL_MERCHANT_ID": "test-merchant-id",
    "ZARINPAL_SANDBOX": True,
    "ZARINPAL_CALLBACK_URL": "https://example.com/payments/zarinpal/callback/",
    "ONLINE_PAYMENT_CURRENCY": "irr",
}
