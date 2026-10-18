from contextlib import contextmanager
from typing import Any, Iterator, Tuple

from flask import Flask, g, url_for
from flask.testing import FlaskClient
from flask.wrappers import Response

from backend.models.users import Users
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.urls.constants import URLErrorCodes
from backend.utils.all_routes import ROUTES
from backend.utils.strings.json_strs import STD_JSON_RESPONSE
from backend.utils.strings.model_strs import MODELS
from backend.utils.strings.trash_strs import TRASH_FAILURE
from backend.utils.strings.url_validation_strs import URL_VALIDATION
from backend.utils.strings.utub_strs import UTUB_ID
from tests.conftest import AjaxFlaskLoginClient
from tests.utils_for_test import get_csrf_token

AJAX_HEADERS = {URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST}
FIRST_UTUB_ID = 1
SECOND_UTUB_ID = 2
FIRST_USER_ID = 1
SECOND_USER_ID = 2
THIRD_USER_ID = 3
NONEXISTENT_ID = 99999


def post_restore(
    client: FlaskClient,
    csrf_token: str,
    utub_id: int,
    utub_url_id: int,
    body: dict[str, Any] | None = None,
) -> Response:
    return client.post(
        url_for(ROUTES.URLS.RESTORE_URL, utub_id=utub_id, utub_url_id=utub_url_id),
        json={} if body is None else body,
        headers={**AJAX_HEADERS, URL_VALIDATION.X_CSRF_TOKEN: csrf_token},
    )


def post_restore_urls(
    client: FlaskClient,
    csrf_token: str,
    utub_id: int,
    utub_url_ids: list[int],
) -> Response:
    return client.post(
        url_for(ROUTES.URLS.RESTORE_URLS, utub_id=utub_id),
        json={"utubUrlIds": utub_url_ids},
        headers={**AJAX_HEADERS, URL_VALIDATION.X_CSRF_TOKEN: csrf_token},
    )


def get_trash_url_ids(client: FlaskClient) -> list[int]:
    response = client.get(url_for(ROUTES.UTUBS.GET_TRASH), headers=AJAX_HEADERS)
    assert response.status_code == 200
    return [item[MODELS.UTUB_URL_ID] for item in response.json[MODELS.URLS]]


def clear_shared_request_caches() -> None:
    """Drop Flask-Login's and Flask-WTF's per-request caches on ``g``."""
    for cached_attribute in ("_login_user", "csrf_token"):
        if hasattr(g, cached_attribute):
            delattr(g, cached_attribute)


@contextmanager
def login_as_user(app: Flask, user_id: int) -> Iterator[Tuple[FlaskClient, str]]:
    """Log an arbitrary seeded user in; yields their client and CSRF token.

    The client is used as a context manager (like the login fixtures) so the session
    cookie holding the CSRF secret survives across requests. The harness keeps one app
    context alive for the whole test, so request-scoped values on ``g`` would carry the
    first client's identity and CSRF token into this one; they are cleared on entry and
    again on exit so the fixture client is not left seeing this user.
    """
    app.test_client_class = AjaxFlaskLoginClient
    with app.app_context():
        user_to_login: Users = Users.query.get(user_id)
    clear_shared_request_caches()
    try:
        with app.test_client(user=user_to_login) as logged_in_client:
            csrf_token = get_csrf_token(
                logged_in_client.get("/home").get_data(), meta_tag=True
            )
            yield logged_in_client, csrf_token
    finally:
        clear_shared_request_caches()


def assert_not_in_trash_response(response: Response) -> None:
    assert response.status_code == 404
    response_json = response.json
    assert response_json[STD_JSON_RESPONSE.STATUS] == STD_JSON_RESPONSE.FAILURE
    assert response_json[STD_JSON_RESPONSE.MESSAGE] == TRASH_FAILURE.NOT_IN_TRASH
    assert response_json[STD_JSON_RESPONSE.ERROR_CODE] == URLErrorCodes.NOT_IN_TRASH


def get_row_state(app: Flask, utub_url_id: int) -> dict[str, Any]:
    with app.app_context():
        utub_url: Utub_Urls = Utub_Urls.query.get(utub_url_id)
        return {
            "utub_id": utub_url.utub_id,
            "deleted_at": utub_url.deleted_at,
            "deleted_by": utub_url.deleted_by,
            "trashed_tag_ids": utub_url.trashed_tag_ids,
            "trashed_tag_names": utub_url.trashed_tag_names,
            "user_id": utub_url.user_id,
            "added_at": utub_url.added_at,
            "url_title": utub_url.url_title,
            "last_accessed": utub_url.last_accessed,
        }


def get_trashed_utub_ids(client: FlaskClient) -> list[int]:
    response = client.get(url_for(ROUTES.UTUBS.GET_TRASH), headers=AJAX_HEADERS)
    assert response.status_code == 200
    return [item[UTUB_ID] for item in response.json[MODELS.UTUBS]]


def count_url_tags_of_row(app: Flask, utub_url_id: int) -> int:
    with app.app_context():
        return Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_url_id == utub_url_id
        ).count()


def count_url_tags_in_utub(app: Flask, utub_id: int) -> int:
    with app.app_context():
        return Utub_Url_Tags.query.filter(Utub_Url_Tags.utub_id == utub_id).count()


def row_exists(app: Flask, utub_url_id: int) -> bool:
    with app.app_context():
        return Utub_Urls.query.get(utub_url_id) is not None


def utub_exists(app: Flask, utub_id: int) -> bool:
    with app.app_context():
        return Utubs.query.get(utub_id) is not None
