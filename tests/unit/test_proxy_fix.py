"""Unit tests for `apply_proxy_fix`, the ProxyFix counts used behind the proxy chain.

Prod and dev sit behind Cloudflare -> cloudflared -> nginx. Cloudflare sends a
single `X-Forwarded-Proto` value, and nginx appends to `X-Forwarded-For`, so the
app must trust 1 proto value and 2 for values. A count above the header's value
count makes werkzeug ignore the header, which made every external URL `http://`
(#715). See ARCHITECTURE.md "Edge -> origin topology".
"""

import pytest
from flask import Flask, request, url_for
from flask.testing import FlaskClient
from flask_wtf.csrf import CSRFProtect, generate_csrf
from werkzeug.middleware.proxy_fix import ProxyFix

from backend import apply_proxy_fix
from backend.config import ConfigTest
from tests.utils_for_test import create_secondary_app

pytestmark = pytest.mark.unit

CLIENT_IP = "203.0.113.7"
CLOUDFLARED_IP = "127.0.0.1"
CALLBACK_PATH = "/oauth/google/callback"
PUBLIC_BASE_URL = "http://urls.4irl.app"
CSRF_TOKEN_PATH = "/csrf-token"
CSRF_FORM_PATH = "/form"
CLOUDFLARE_HTTPS_HEADERS = {"X-Forwarded-Proto": "https"}


class ConfigTestDevServer(ConfigTest):
    DEV_SERVER = True


@pytest.fixture
def proxied_app() -> Flask:
    app = Flask(__name__)

    @app.route(CALLBACK_PATH)
    def callback() -> dict[str, str | None]:
        return {
            "external_url": url_for("callback", _external=True),
            "remote_addr": request.remote_addr,
        }

    apply_proxy_fix(app)
    return app


def test_single_forwarded_proto_value_yields_https_external_urls(
    proxied_app: Flask,
) -> None:
    """
    GIVEN the app behind the proxy chain, where Cloudflare sends one
        `X-Forwarded-Proto: https` value and nginx proxies over plain http
    WHEN an external URL is built during the request
    THEN it uses https, so OAuth redirect_uris, short links and email links are https
    """
    response = proxied_app.test_client().get(
        CALLBACK_PATH,
        headers={"X-Forwarded-Proto": "https", "Host": "urls.4irl.app"},
    )
    assert response.json is not None
    assert response.json["external_url"] == f"https://urls.4irl.app{CALLBACK_PATH}"


def test_two_forwarded_for_values_resolve_the_client_ip(proxied_app: Flask) -> None:
    """
    GIVEN `X-Forwarded-For: <client>, <cloudflared>`: Cloudflare's client IP,
        then nginx's appended address
    WHEN the request is handled
    THEN `request.remote_addr` (used by logs and rate limiting) is the client IP
    """
    response = proxied_app.test_client().get(
        CALLBACK_PATH,
        headers={"X-Forwarded-For": f"{CLIENT_IP}, {CLOUDFLARED_IP}"},
        environ_base={"REMOTE_ADDR": CLOUDFLARED_IP},
    )
    assert response.json is not None
    assert response.json["remote_addr"] == CLIENT_IP


def test_client_supplied_forwarded_for_cannot_spoof_the_client_ip(
    proxied_app: Flask,
) -> None:
    """
    GIVEN a client that sent its own `X-Forwarded-For`, which Cloudflare
        appends the real client IP to before nginx appends cloudflared's
    WHEN the request is handled
    THEN `request.remote_addr` is still the real client IP, not the spoofed one
    """
    response = proxied_app.test_client().get(
        CALLBACK_PATH,
        headers={"X-Forwarded-For": f"198.51.100.99, {CLIENT_IP}, {CLOUDFLARED_IP}"},
        environ_base={"REMOTE_ADDR": CLOUDFLARED_IP},
    )
    assert response.json is not None
    assert response.json["remote_addr"] == CLIENT_IP


def test_without_proxy_fix_external_urls_stay_http() -> None:
    """
    GIVEN a local app, where `create_app` never applies ProxyFix
    WHEN an external URL is built for a request carrying `X-Forwarded-Proto: https`
    THEN the header is ignored and the URL stays http (local loopback callbacks)
    """
    app = Flask(__name__)

    @app.route(CALLBACK_PATH)
    def callback() -> dict[str, str]:
        return {"external_url": url_for("callback", _external=True)}

    response = app.test_client().get(
        CALLBACK_PATH,
        headers={"X-Forwarded-Proto": "https", "Host": "127.0.0.1:8659"},
    )
    assert response.json is not None
    assert response.json["external_url"] == f"http://127.0.0.1:8659{CALLBACK_PATH}"


@pytest.fixture
def csrf_protected_proxied_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "proxy-fix-csrf-test-secret"
    CSRFProtect(app)

    @app.route(CSRF_TOKEN_PATH)
    def csrf_token() -> dict[str, str]:
        return {"csrf_token": generate_csrf()}

    @app.route(CSRF_FORM_PATH, methods=["POST"])
    def form() -> dict[str, str]:
        return {"status": "ok"}

    apply_proxy_fix(app)
    return app


def _fetch_csrf_token(client_for_proxied_app: FlaskClient) -> str:
    token_response = client_for_proxied_app.get(
        CSRF_TOKEN_PATH, base_url=PUBLIC_BASE_URL, headers=CLOUDFLARE_HTTPS_HEADERS
    )
    assert token_response.json is not None
    return token_response.json["csrf_token"]


def test_csrf_ssl_strict_accepts_same_origin_referer_behind_proxy(
    csrf_protected_proxied_app: Flask,
) -> None:
    """
    GIVEN a CSRF-protected app behind the proxy chain, where Cloudflare's
        `X-Forwarded-Proto: https` makes `request.is_secure` true
    WHEN a POST carries a valid CSRF token and a same-origin https Referer
    THEN Flask-WTF's SSL-strict Referer check passes and the request succeeds
    """
    client = csrf_protected_proxied_app.test_client()
    csrf_token = _fetch_csrf_token(client)

    response = client.post(
        CSRF_FORM_PATH,
        base_url=PUBLIC_BASE_URL,
        headers={
            **CLOUDFLARE_HTTPS_HEADERS,
            "X-CSRFToken": csrf_token,
            "Referer": "https://urls.4irl.app/home",
        },
    )
    assert response.status_code == 200
    assert response.json == {"status": "ok"}


def test_csrf_ssl_strict_rejects_missing_referer_behind_proxy(
    csrf_protected_proxied_app: Flask,
) -> None:
    """
    GIVEN a CSRF-protected app behind the proxy chain, where Cloudflare's
        `X-Forwarded-Proto: https` makes `request.is_secure` true
    WHEN a POST carries a valid CSRF token but no Referer header
    THEN Flask-WTF's SSL-strict check (`WTF_CSRF_SSL_STRICT`, default True)
        rejects it with 400, showing the check is active behind the proxy
    """
    client = csrf_protected_proxied_app.test_client()
    csrf_token = _fetch_csrf_token(client)

    response = client.post(
        CSRF_FORM_PATH,
        base_url=PUBLIC_BASE_URL,
        headers={**CLOUDFLARE_HTTPS_HEADERS, "X-CSRFToken": csrf_token},
    )
    assert response.status_code == 400
    assert b"The referrer header is missing." in response.data


def test_create_app_applies_proxy_fix_on_dev_server() -> None:
    """
    GIVEN a test config with `DEV_SERVER = True` (dev sits behind the proxy chain)
    WHEN the full app is built via `create_app`
    THEN its `wsgi_app` is wrapped in ProxyFix
    """
    app = create_secondary_app(ConfigTestDevServer)
    assert isinstance(app.wsgi_app, ProxyFix)


def test_create_app_skips_proxy_fix_for_local_config() -> None:
    """
    GIVEN the default test config (neither PRODUCTION nor DEV_SERVER)
    WHEN the full app is built via `create_app`
    THEN its `wsgi_app` is not wrapped in ProxyFix, so forwarded headers are ignored
    """
    app = create_secondary_app(ConfigTest)
    assert not isinstance(app.wsgi_app, ProxyFix)
