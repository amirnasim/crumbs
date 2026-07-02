"""Production settings validation for two-phase SSL deployment."""

import importlib
import sys
import warnings

import pytest


_SECURITY_ENV_KEYS = (
    "ALLOWED_HOSTS",
    "CSRF_TRUSTED_ORIGINS",
    "CSRF_COOKIE_SECURE",
    "ENABLE_HTTPS",
    "LOCAL_PROD_DRY_RUN",
    "SECURE_HSTS_INCLUDE_SUBDOMAINS",
    "SECURE_HSTS_PRELOAD",
    "SECURE_HSTS_SECONDS",
    "SECURE_SSL_REDIRECT",
    "SESSION_COOKIE_SECURE",
    "SITE_URL",
)


def _load_prod_settings(monkeypatch, **env):
    defaults = {
        "SECRET_KEY": "test-production-secret-key-not-for-production-use",
        "DEBUG": "False",
        "LOCAL_PROD_DRY_RUN": "True",
    }
    defaults.update(env)
    for key in _SECURITY_ENV_KEYS:
        if key not in env:
            monkeypatch.delenv(key, raising=False)
    for key, value in defaults.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)

    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: None)

    for module_name in list(sys.modules):
        if module_name.startswith("config.settings"):
            del sys.modules[module_name]

    return importlib.import_module("config.settings.prod")


@pytest.mark.parametrize(
    "extra_env",
    [
        {"ENABLE_HTTPS": "False"},
        {
            "ENABLE_HTTPS": "False",
            "SECURE_SSL_REDIRECT": "False",
            "SESSION_COOKIE_SECURE": "False",
            "CSRF_COOKIE_SECURE": "False",
            "SECURE_HSTS_SECONDS": "0",
        },
    ],
)
def test_prod_settings_http_first_phase(monkeypatch, extra_env):
    prod = _load_prod_settings(monkeypatch, **extra_env)

    assert prod.DEBUG is False
    assert prod.ENABLE_HTTPS is False
    assert prod.SECURE_SSL_REDIRECT is False
    assert prod.SESSION_COOKIE_SECURE is False
    assert prod.CSRF_COOKIE_SECURE is False
    assert prod.SECURE_HSTS_SECONDS == 0
    assert prod.SECURE_HSTS_INCLUDE_SUBDOMAINS is False
    assert prod.SECURE_HSTS_PRELOAD is False


def test_prod_settings_local_dry_run_warns_on_localhost_allowed_hosts(monkeypatch):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        prod = _load_prod_settings(
            monkeypatch,
            LOCAL_PROD_DRY_RUN="True",
            ALLOWED_HOSTS="localhost,127.0.0.1",
        )

    assert prod.LOCAL_PROD_DRY_RUN is True
    assert any("ALLOWED_HOSTS is localhost-only" in str(item.message) for item in caught)


def test_prod_settings_requires_explicit_allowed_hosts_without_dry_run(monkeypatch):
    with pytest.raises(ValueError, match="ALLOWED_HOSTS must include your production domain"):
        _load_prod_settings(
            monkeypatch,
            LOCAL_PROD_DRY_RUN="False",
            ALLOWED_HOSTS="localhost,127.0.0.1",
        )


def test_prod_settings_accepts_production_allowed_hosts(monkeypatch):
    prod = _load_prod_settings(
        monkeypatch,
        LOCAL_PROD_DRY_RUN="False",
        ALLOWED_HOSTS="crumbs.ir,www.crumbs.ir",
    )

    assert prod.ALLOWED_HOSTS == ["crumbs.ir", "www.crumbs.ir"]


def test_prod_settings_debug_true_raises(monkeypatch):
    with pytest.raises(ValueError, match="DEBUG must be False"):
        _load_prod_settings(monkeypatch, DEBUG="True")


def test_prod_settings_https_phase(monkeypatch):
    prod = _load_prod_settings(
        monkeypatch,
        LOCAL_PROD_DRY_RUN="False",
        ALLOWED_HOSTS="example.com,www.example.com",
        ENABLE_HTTPS="True",
        SECURE_SSL_REDIRECT="True",
        SESSION_COOKIE_SECURE="True",
        CSRF_COOKIE_SECURE="True",
        SECURE_HSTS_SECONDS="31536000",
        SECURE_HSTS_INCLUDE_SUBDOMAINS="True",
        SECURE_HSTS_PRELOAD="False",
        SITE_URL="https://example.com",
        CSRF_TRUSTED_ORIGINS="https://example.com,https://www.example.com",
    )

    assert prod.ENABLE_HTTPS is True
    assert prod.SECURE_SSL_REDIRECT is True
    assert prod.SESSION_COOKIE_SECURE is True
    assert prod.CSRF_COOKIE_SECURE is True
    assert prod.SECURE_HSTS_SECONDS == 31536000
    assert prod.SECURE_HSTS_INCLUDE_SUBDOMAINS is True
    assert prod.SECURE_HSTS_PRELOAD is False


def test_prod_settings_https_enables_secure_cookies_by_default(monkeypatch):
    prod = _load_prod_settings(
        monkeypatch,
        LOCAL_PROD_DRY_RUN="False",
        ALLOWED_HOSTS="example.com",
        ENABLE_HTTPS="True",
        SITE_URL="https://example.com",
        CSRF_TRUSTED_ORIGINS="https://example.com",
    )

    assert prod.SECURE_SSL_REDIRECT is True
    assert prod.SESSION_COOKIE_SECURE is True
    assert prod.CSRF_COOKIE_SECURE is True


def test_prod_settings_https_ignores_stale_insecure_cookie_env(monkeypatch):
    prod = _load_prod_settings(
        monkeypatch,
        LOCAL_PROD_DRY_RUN="False",
        ALLOWED_HOSTS="example.com",
        ENABLE_HTTPS="True",
        SITE_URL="https://example.com",
        CSRF_TRUSTED_ORIGINS="https://example.com",
        SESSION_COOKIE_SECURE="False",
        CSRF_COOKIE_SECURE="False",
        SECURE_HSTS_SECONDS="0",
    )

    assert prod.SESSION_COOKIE_SECURE is True
    assert prod.CSRF_COOKIE_SECURE is True
    assert prod.SECURE_HSTS_SECONDS == 31536000


def test_prod_settings_https_hsts_flags_configurable(monkeypatch):
    prod = _load_prod_settings(
        monkeypatch,
        LOCAL_PROD_DRY_RUN="False",
        ALLOWED_HOSTS="example.com",
        ENABLE_HTTPS="True",
        SITE_URL="https://example.com",
        CSRF_TRUSTED_ORIGINS="https://example.com",
        SECURE_HSTS_SECONDS="86400",
        SECURE_HSTS_INCLUDE_SUBDOMAINS="False",
        SECURE_HSTS_PRELOAD="True",
    )

    assert prod.SECURE_HSTS_SECONDS == 86400
    assert prod.SECURE_HSTS_INCLUDE_SUBDOMAINS is False
    assert prod.SECURE_HSTS_PRELOAD is True


def test_prod_settings_security_headers_and_cookies(monkeypatch):
    prod = _load_prod_settings(monkeypatch)

    assert prod.SESSION_COOKIE_HTTPONLY is True
    assert prod.CSRF_COOKIE_HTTPONLY is True
    assert prod.SESSION_COOKIE_SAMESITE == "Lax"
    assert prod.CSRF_COOKIE_SAMESITE == "Lax"
    assert prod.SECURE_CONTENT_TYPE_NOSNIFF is True
    assert prod.X_FRAME_OPTIONS == "DENY"
    assert prod.SECURE_REFERRER_POLICY == "strict-origin-when-cross-origin"
    assert not hasattr(prod, "SECURE_BROWSER_XSS_FILTER")


def test_prod_settings_https_requires_https_site_url(monkeypatch):
    with pytest.raises(ValueError, match="SITE_URL"):
        _load_prod_settings(
            monkeypatch,
            LOCAL_PROD_DRY_RUN="False",
            ALLOWED_HOSTS="example.com",
            ENABLE_HTTPS="True",
            SITE_URL="http://example.com",
            CSRF_TRUSTED_ORIGINS="https://example.com",
        )


def test_prod_settings_https_requires_csrf_trusted_origins(monkeypatch):
    with pytest.raises(ValueError, match="CSRF_TRUSTED_ORIGINS"):
        _load_prod_settings(
            monkeypatch,
            LOCAL_PROD_DRY_RUN="False",
            ALLOWED_HOSTS="example.com",
            ENABLE_HTTPS="True",
            SITE_URL="https://example.com",
            CSRF_TRUSTED_ORIGINS="",
        )


def test_prod_settings_ssl_redirect_requires_enable_https(monkeypatch):
    with pytest.raises(ValueError, match="SECURE_SSL_REDIRECT=True requires ENABLE_HTTPS=True"):
        _load_prod_settings(
            monkeypatch,
            ENABLE_HTTPS="False",
            SECURE_SSL_REDIRECT="True",
        )
