"""Unit tests for `apply_proxy_fix`, the ProxyFix counts used behind the proxy chain.

Prod and dev sit behind Cloudflare -> cloudflared -> nginx. Cloudflare sends a
single `X-Forwarded-Proto` value, and nginx appends to `X-Forwarded-For`, so the
app must trust 1 proto value and 2 for values. A count above the header's value
count makes werkzeug ignore the header, which made every external URL `http://`
(#715). See ARCHITECTURE.md "Edge -> origin topology".
"""

import pytest
from flask import Flask, request, url_for

from backend import apply_proxy_fix

pytestmark = pytest.mark.unit

CLIENT_IP = "203.0.113.7"
CLOUDFLARED_IP = "127.0.0.1"
CALLBACK_PATH = "/oauth/google/callback"


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
):
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


def test_two_forwarded_for_values_resolve_the_client_ip(proxied_app: Flask):
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
):
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


def test_without_proxy_fix_external_urls_stay_http():
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
