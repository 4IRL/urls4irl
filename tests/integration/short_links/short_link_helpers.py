"""Shared helpers for the short-link route tests."""

from __future__ import annotations

import re
from contextlib import contextmanager
from typing import Generator

from flask import Flask, url_for
from flask.testing import FlaskClient
from flask.wrappers import Response

from backend import db
from backend.models.short_links import Short_Links
from backend.models.users import Users
from backend.models.utub_urls import Utub_Urls
from backend.utils.all_routes import ROUTES
from backend.utils.strings.url_validation_strs import URL_VALIDATION
from tests.conftest import AjaxFlaskClient, AjaxFlaskLoginClient
from tests.utils_for_test import get_csrf_token

FIRST_UTUB_ID: int = 1
FIRST_UTUB_URL_ID: int = 1
CREATOR_ID: int = 1
SECOND_USER_ID: int = 2
THIRD_USER_ID: int = 3
NONEXISTENT_ID: int = 99999

SHORT_URL_KEY: str = "shortUrl"
EXPIRES_AT_KEY: str = "expiresAt"
CAN_REVOKE_KEY: str = "canRevoke"
CREATED_KEY: str = "created"


@contextmanager
def logged_in_as(
    app: Flask, user_id: int
) -> Generator[tuple[FlaskClient, str], None, None]:
    """Yield an AJAX client logged in as ``user_id`` plus its CSRF token."""
    app.test_client_class = AjaxFlaskLoginClient
    with app.app_context():
        user = Users.query.get(user_id)
    with app.test_client(user=user) as client:
        home_response = client.get("/home")
        yield client, get_csrf_token(home_response.get_data(), meta_tag=True)


def post_mint(
    client: FlaskClient,
    csrf_token: str,
    utub_id: int = FIRST_UTUB_ID,
    utub_url_id: int = FIRST_UTUB_URL_ID,
) -> Response:
    return client.post(
        url_for(ROUTES.URLS.MINT_SHORT_LINK, utub_id=utub_id, utub_url_id=utub_url_id),
        headers={"X-CSRFToken": csrf_token},
    )


def delete_revoke(
    client: FlaskClient,
    csrf_token: str,
    utub_id: int = FIRST_UTUB_ID,
    utub_url_id: int = FIRST_UTUB_URL_ID,
) -> Response:
    return client.delete(
        url_for(
            ROUTES.URLS.REVOKE_SHORT_LINK, utub_id=utub_id, utub_url_id=utub_url_id
        ),
        headers={"X-CSRFToken": csrf_token},
    )


def short_link_rows(app: Flask, utub_url_id: int | None = None) -> list[Short_Links]:
    """Return the ShortLinks rows (optionally for one URL), read in a fresh context."""
    with app.app_context():
        db.session.expire_all()
        query = db.session.query(Short_Links)
        if utub_url_id is not None:
            query = query.filter(Short_Links.utub_url_id == utub_url_id)
        rows = query.order_by(Short_Links.id).all()
        db.session.expunge_all()
        return rows


def set_url_adder(app: Flask, utub_url_id: int, user_id: int) -> None:
    """Make ``user_id`` the recorded adder of the UTub URL."""
    with app.app_context():
        utub_url: Utub_Urls = Utub_Urls.query.get(utub_url_id)
        utub_url.user_id = user_id
        db.session.commit()


def code_from_short_url(short_url: str) -> str:
    """Return the trailing code of a ``.../s/<code>`` short URL."""
    return short_url.rsplit("/s/", 1)[1]


# An empty X-Requested-With keeps the harness from injecting the AJAX sentinel, so the
# request is a plain page load (HTML errors, not the JSON an AJAX request would get).
NON_XHR_HEADERS: dict[str, str] = {URL_VALIDATION.X_REQUESTED_WITH: ""}

_NONCE_PATTERN = re.compile(r'nonce="[^"]*"')
_CSRF_META_PATTERN = re.compile(r'(name="csrf-token" content=)"[^"]*"')


def anonymous_client(app: Flask) -> FlaskClient:
    """Return a fresh client with no session cookie (an anonymous visitor)."""
    app.test_client_class = AjaxFlaskClient
    return app.test_client()


def get_share_page(
    client: FlaskClient, code: str, headers: dict[str, str] | None = None
) -> Response:
    """GET ``/s/<code>`` as a plain page load."""
    return client.get(
        url_for(ROUTES.SHORT_LINKS.RESOLVE_SHORT_LINK, code=code),
        headers={**NON_XHR_HEADERS, **(headers or {})},
    )


def normalized_body(response: Response) -> str:
    """The response HTML with the per-request nonce and CSRF token blanked out."""
    html = response.get_data(as_text=True)
    html = _NONCE_PATTERN.sub('nonce="N"', html)
    return _CSRF_META_PATTERN.sub(r'\1"CSRF"', html)
