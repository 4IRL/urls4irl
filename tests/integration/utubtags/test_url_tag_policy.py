"""Policy tests for tagging URLs (members_can_tag) on the add, batch, remove, bulk and URL-create paths.

Fixture shape: UTub 1 holds users 1 (owner), 2 (co-owner, promoted per test) and 3 (plain
member), three tags, and either three URLs (``url_utub``) or none (``create_utub``, with
the three URLs only in the ``Urls`` table). Every case runs on the web route and, where it
exists, its ``/api/v1`` bearer-token twin. Refusal cases use valid targets, since route
decorators and schema validation run before the policy check.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable
from unittest import mock

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient
from flask.wrappers import Response

from backend import db
from backend.api_v1.services.tokens import create_access_token
from backend.models.urls import Urls
from backend.models.users import Users
from backend.models.utub_members import Member_Role
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.tags.constants import URLTagErrorCodes
from backend.urls.constants import URLErrorCodes
from backend.utils.all_routes import ROUTES
from backend.utils.strings.api_auth_strs import API_AUTH
from backend.utils.strings.form_strs import URL_FORM
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import MODELS
from backend.utils.strings.tag_strs import TAG_REMOVE_NOT_ALLOWED, TAG_URLS_NOT_ALLOWED
from backend.utils.strings.utub_strs import UTUB_FAILURE
from backend.utubs.guards import lock_and_reauthorize as real_lock_and_reauthorize
from tests.integration.short_links.short_link_helpers import (
    CREATOR_ID,
    FIRST_UTUB_ID,
    SECOND_USER_ID,
    THIRD_USER_ID,
    logged_in_as,
    set_url_adder,
)
from tests.models_for_test import valid_url_strings
from tests.utils_for_test import (
    lock_utub,
    remove_member,
    set_member_role,
    set_tags_settings,
    trash_utub,
    trash_utub_url,
)

pytestmark = [pytest.mark.tags, pytest.mark.urls, pytest.mark.mobile_api]

CO_OWNER_ID = SECOND_USER_ID
MEMBER_ID = THIRD_USER_ID
TAGGING_OFF = {"members_can_tag": False}
BOTH_OFF = {"members_can_tag": False, "members_can_delete_tags": False}
DELETE_OFF = {"members_can_delete_tags": False}
FRESH_TAG = "freshpolicytag"
FRESH_TAGS = ["freshpolicyone", "freshpolicytwo"]
TAG_STRINGS_FIELD = "tagStrings"
UTUB_URL_IDS_FIELD = "utubUrlIds"
CODE_URL_TAG = URLTagErrorCodes.TAGGING_NOT_ALLOWED
CODE_URL_CREATE = URLErrorCodes.TAGGING_NOT_ALLOWED

LOCK_TAG_ADD = "backend.tags.services.create_url_tag.lock_and_reauthorize"
LOCK_TAG_REMOVE = "backend.tags.services.delete_url_tag.lock_and_reauthorize"
LOCK_URL_CREATE = "backend.urls.services.create_urls.lock_and_reauthorize"


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def url_utub(
    add_all_urls_and_users_to_each_utub_no_tags, add_tags_to_utubs, app: Flask
) -> Flask:
    """UTub 1 with owner 1, co-owner 2, plain member 3, three tags and three URLs.

    The first URL carries the first tag so the remove path has a target.
    """
    set_member_role(app, FIRST_UTUB_ID, CO_OWNER_ID, Member_Role.CO_CREATOR)
    with app.app_context():
        first_url = (
            Utub_Urls.query.filter(Utub_Urls.utub_id == FIRST_UTUB_ID)
            .order_by(Utub_Urls.id)
            .first()
        )
        first_tag = (
            Utub_Tags.query.filter(Utub_Tags.utub_id == FIRST_UTUB_ID)
            .order_by(Utub_Tags.id)
            .first()
        )
        db.session.add(
            Utub_Url_Tags(
                utub_id=FIRST_UTUB_ID,
                utub_url_id=first_url.id,
                utub_tag_id=first_tag.id,
            )
        )
        db.session.commit()
    return app


@pytest.fixture
def create_utub(
    every_user_in_every_utub, add_urls_to_database, add_tags_to_utubs, app: Flask
) -> Flask:
    """UTub 1 with owner 1, co-owner 2, plain member 3 and no URLs (URLs only in ``Urls``)."""
    set_member_role(app, FIRST_UTUB_ID, CO_OWNER_ID, Member_Role.CO_CREATOR)
    return app


def _utub_url_ids(app: Flask) -> list[int]:
    with app.app_context():
        return [
            row.id
            for row in Utub_Urls.query.filter(Utub_Urls.utub_id == FIRST_UTUB_ID)
            .order_by(Utub_Urls.id)
            .all()
        ]


def _first_tag_id(app: Flask) -> int:
    with app.app_context():
        return (
            Utub_Tags.query.filter(Utub_Tags.utub_id == FIRST_UTUB_ID)
            .order_by(Utub_Tags.id)
            .first()
            .id
        )


def _write_state(app: Flask) -> tuple[int, int, int, int]:
    """Row counts of every table a refused request must leave untouched."""
    with app.app_context():
        return (
            Utub_Tags.query.count(),
            Utub_Url_Tags.query.count(),
            Urls.query.count(),
            Utub_Urls.query.count(),
        )


def _code(response: Response) -> Any:
    return (response.get_json(silent=True) or {}).get(STD_JSON.ERROR_CODE)


def _message(response: Response) -> Any:
    return (response.get_json(silent=True) or {}).get(STD_JSON.MESSAGE)


def _bearer(app: Flask, user_id: int) -> dict[str, str]:
    with app.app_context():
        token = create_access_token(user=Users.query.get(user_id))
    return {API_AUTH.AUTHORIZATION_HEADER: f"{API_AUTH.BEARER_PREFIX}{token}"}


def _send(
    app: Flask,
    *,
    surface: str,
    method: str,
    web_route: str,
    api_route: str | None,
    user_id: int,
    json: dict[str, Any] | None = None,
    **route_values: int,
) -> Response:
    """Send a request on the web route (AJAX client + CSRF) or the API twin (bearer)."""
    if surface == "web":
        with logged_in_as(app, user_id) as (client, csrf_token):
            return getattr(client, method)(
                url_for(web_route, **route_values),
                json=json,
                headers={"X-CSRFToken": csrf_token},
            )
    assert api_route is not None
    with app.test_request_context():
        url = url_for(api_route, **route_values)
    app.test_client_class = FlaskClient
    return getattr(app.test_client(), method)(
        url, json=json, headers=_bearer(app, user_id)
    )


Call = Callable[[Flask, str, int, int], Response]


def _call_add_single(app: Flask, surface: str, user_id: int, utub_id: int) -> Response:
    return _send(
        app,
        surface=surface,
        method="post",
        web_route=ROUTES.URL_TAGS.CREATE_URL_TAG,
        api_route=ROUTES.API_V1.CREATE_URL_TAG,
        user_id=user_id,
        json={MODELS.TAG_STRING: FRESH_TAG},
        utub_id=utub_id,
        utub_url_id=_utub_url_ids(app)[1],
    )


def _call_add_batch(app: Flask, surface: str, user_id: int, utub_id: int) -> Response:
    return _send(
        app,
        surface=surface,
        method="post",
        web_route=ROUTES.URL_TAGS.BATCH_ADD_URL_TAGS,
        api_route=ROUTES.API_V1.CREATE_URL_TAGS_BATCH,
        user_id=user_id,
        json={TAG_STRINGS_FIELD: FRESH_TAGS},
        utub_id=utub_id,
        utub_url_id=_utub_url_ids(app)[1],
    )


def _call_remove(app: Flask, surface: str, user_id: int, utub_id: int) -> Response:
    return _send(
        app,
        surface=surface,
        method="delete",
        web_route=ROUTES.URL_TAGS.DELETE_URL_TAG,
        api_route=ROUTES.API_V1.DELETE_URL_TAG,
        user_id=user_id,
        utub_id=utub_id,
        utub_url_id=_utub_url_ids(app)[0],
        utub_tag_id=_first_tag_id(app),
    )


def _call_bulk(app: Flask, surface: str, user_id: int, utub_id: int) -> Response:
    return _send(
        app,
        surface=surface,
        method="post",
        web_route=ROUTES.URL_TAGS.APPLY_TAGS_TO_URLS,
        api_route=None,
        user_id=user_id,
        json={
            UTUB_URL_IDS_FIELD: _utub_url_ids(app)[:2],
            TAG_STRINGS_FIELD: FRESH_TAGS,
        },
        utub_id=utub_id,
    )


@dataclass(frozen=True)
class UrlTagService:
    """One gated URL-tag service group and how to drive it."""

    name: str
    call: Call
    surfaces: tuple[str, ...]
    message: str
    lock_patch: str
    success_delta: bool


SERVICES = [
    UrlTagService(
        "add",
        _call_add_single,
        ("web", "api"),
        TAG_URLS_NOT_ALLOWED,
        LOCK_TAG_ADD,
        True,
    ),
    UrlTagService(
        "batch",
        _call_add_batch,
        ("web", "api"),
        TAG_URLS_NOT_ALLOWED,
        LOCK_TAG_ADD,
        True,
    ),
    UrlTagService(
        "remove",
        _call_remove,
        ("web", "api"),
        TAG_REMOVE_NOT_ALLOWED,
        LOCK_TAG_REMOVE,
        True,
    ),
    UrlTagService(
        "bulk", _call_bulk, ("web",), TAG_URLS_NOT_ALLOWED, LOCK_TAG_ADD, True
    ),
]
CASES = [
    pytest.param(service, surface, id=f"{service.name}-{surface}")
    for service in SERVICES
    for surface in service.surfaces
]


# ---------------------------------------------------------------------------
# Add, batch, remove and bulk
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("service,surface", CASES)
@pytest.mark.parametrize("user_id", [CREATOR_ID, CO_OWNER_ID])
@pytest.mark.parametrize("settings", [TAGGING_OFF, BOTH_OFF])
def test_manager_unaffected_by_policy(url_utub, service, surface, user_id, settings):
    """
    GIVEN Tagging off
    WHEN the owner or a co-owner uses a URL-tag service
    THEN 200 and the tag tables changed
    """
    set_tags_settings(url_utub, FIRST_UTUB_ID, settings)
    before = _write_state(url_utub)

    response = service.call(url_utub, surface, user_id, FIRST_UTUB_ID)

    assert response.status_code == 200
    assert _write_state(url_utub) != before


@pytest.mark.parametrize("service,surface", CASES)
@pytest.mark.parametrize("settings", [TAGGING_OFF, BOTH_OFF])
def test_plain_member_refused_when_tagging_off(url_utub, service, surface, settings):
    """
    GIVEN Tagging off (Delete stored either way)
    WHEN a plain member uses a URL-tag service with valid targets
    THEN 403 errorCode 4 with the service's message and nothing is written
    """
    set_tags_settings(url_utub, FIRST_UTUB_ID, settings)
    before = _write_state(url_utub)

    response = service.call(url_utub, surface, MEMBER_ID, FIRST_UTUB_ID)

    assert response.status_code == 403
    assert _code(response) == CODE_URL_TAG
    assert _message(response) == service.message
    assert _write_state(url_utub) == before


@pytest.mark.parametrize("service,surface", CASES)
@pytest.mark.parametrize("settings", [None, {}, DELETE_OFF, {"members_can_tag": True}])
def test_plain_member_allowed_when_tagging_on(url_utub, service, surface, settings):
    """
    GIVEN Tagging on (stored or default), with Delete either way
    WHEN a plain member uses a URL-tag service
    THEN 200 (Delete only governs deleting UTub tags); the bulk apply also reports
        every targeted URL as applied and none skipped, so a gate that short-circuits
        the per-URL work on an allowed call is caught
    """
    if settings is not None:
        set_tags_settings(url_utub, FIRST_UTUB_ID, settings)

    response = service.call(url_utub, surface, MEMBER_ID, FIRST_UTUB_ID)

    assert response.status_code == 200
    if service.name == "bulk":
        body = response.get_json()
        assert (
            sorted(entry[MODELS.UTUB_URL_ID] for entry in body[MODELS.APPLIED])
            == (_utub_url_ids(url_utub)[:2])
        )
        assert body[MODELS.SKIPPED] == []


@pytest.mark.parametrize("service,surface", CASES)
@pytest.mark.parametrize(
    "stored", [{"members_can_tag": "garbage"}, {"members_can_tag": None}, "garbage"]
)
def test_corrupt_stored_values_resolve_to_defaults_and_allow(
    url_utub, service, surface, stored
):
    """
    GIVEN a corrupt stored tags section or members_can_tag
    WHEN a plain member uses a URL-tag service
    THEN the resolver defaults apply (Tagging on) and it is allowed
    """
    set_tags_settings(url_utub, FIRST_UTUB_ID, stored)

    response = service.call(url_utub, surface, MEMBER_ID, FIRST_UTUB_ID)

    assert response.status_code == 200


@pytest.mark.parametrize("service,surface", CASES)
def test_locked_utub_beats_policy(url_utub, service, surface):
    """
    GIVEN a locked UTub with Tagging off
    WHEN a plain member uses a URL-tag service
    THEN UTUB_IS_LOCKED (code 3), not the policy refusal, and nothing is written
    """
    set_tags_settings(url_utub, FIRST_UTUB_ID, TAGGING_OFF)
    lock_utub(url_utub, FIRST_UTUB_ID)
    before = _write_state(url_utub)

    response = service.call(url_utub, surface, MEMBER_ID, FIRST_UTUB_ID)

    assert response.status_code == 403
    assert _code(response) == URLTagErrorCodes.UTUB_IS_LOCKED
    assert _message(response) == UTUB_FAILURE.UTUB_IS_LOCKED
    assert _write_state(url_utub) == before


@pytest.mark.parametrize("service,surface", CASES)
def test_post_lock_read_wins_over_route_guard_state(url_utub, service, surface):
    """
    GIVEN Tagging on when the route guard runs and a manager turns it off before the lock
    WHEN a plain member uses a URL-tag service
    THEN the locked read refuses with errorCode 4 and nothing is written
    """
    set_tags_settings(url_utub, FIRST_UTUB_ID, {"members_can_tag": True})
    before = _write_state(url_utub)

    def flip_then_lock(*args: Any, **kwargs: Any) -> Any:
        set_tags_settings(url_utub, FIRST_UTUB_ID, TAGGING_OFF)
        return real_lock_and_reauthorize(*args, **kwargs)

    with mock.patch(service.lock_patch, side_effect=flip_then_lock) as patched:
        response = service.call(url_utub, surface, MEMBER_ID, FIRST_UTUB_ID)

    patched.assert_called_once()
    assert response.status_code == 403
    assert _code(response) == CODE_URL_TAG
    assert _write_state(url_utub) == before


@pytest.mark.parametrize("service,surface", CASES)
@pytest.mark.parametrize("scenario", ["revoked_member", "trashed_utub"])
def test_revoked_member_or_gone_utub_is_404(url_utub, service, surface, scenario):
    """
    GIVEN a revoked member, or a trashed UTub
    WHEN they use a URL-tag service (lock_and_reauthorize replaces reject_if_utub_locked)
    THEN 404
    """
    if scenario == "revoked_member":
        remove_member(url_utub, FIRST_UTUB_ID, MEMBER_ID)
        actor = MEMBER_ID
    else:
        trash_utub(url_utub, FIRST_UTUB_ID, deleted_by=CREATOR_ID)
        actor = CREATOR_ID
    before = _write_state(url_utub)

    response = service.call(url_utub, surface, actor, FIRST_UTUB_ID)

    assert response.status_code == 404
    assert _write_state(url_utub) == before


@pytest.mark.parametrize("service,surface", CASES)
def test_member_revoked_after_route_guard_is_404_from_the_lock(
    url_utub, service, surface
):
    """
    GIVEN a member whose membership is revoked after the route guard but before the lock
    WHEN they use a URL-tag service
    THEN lock_and_reauthorize re-checks membership and returns 404 with nothing written
    """
    before = _write_state(url_utub)

    def revoke_then_lock(*args: Any, **kwargs: Any) -> Any:
        remove_member(url_utub, FIRST_UTUB_ID, MEMBER_ID)
        return real_lock_and_reauthorize(*args, **kwargs)

    with mock.patch(service.lock_patch, side_effect=revoke_then_lock) as patched:
        response = service.call(url_utub, surface, MEMBER_ID, FIRST_UTUB_ID)

    patched.assert_called_once()
    assert response.status_code == 404
    assert _write_state(url_utub) == before


@pytest.mark.parametrize("service,surface", CASES)
def test_policy_refusal_rolls_back_the_lock_transaction(url_utub, service, surface):
    """
    GIVEN tagging is off
    WHEN a plain member is refused by a URL-tag service
    THEN the session is rolled back so the row lock is released
    """
    set_tags_settings(url_utub, FIRST_UTUB_ID, TAGGING_OFF)

    with mock.patch.object(db.session, "rollback", wraps=db.session.rollback) as spy:
        response = service.call(url_utub, surface, MEMBER_ID, FIRST_UTUB_ID)

    assert response.status_code == 403
    spy.assert_called()


@pytest.mark.parametrize("service,surface", CASES)
def test_locked_refusal_rolls_back_the_lock_transaction(url_utub, service, surface):
    """
    GIVEN a locked UTub
    WHEN a plain member is refused by a URL-tag service
    THEN the session is rolled back so the row lock is released
    """
    lock_utub(url_utub, FIRST_UTUB_ID)

    with mock.patch.object(db.session, "rollback", wraps=db.session.rollback) as spy:
        response = service.call(url_utub, surface, MEMBER_ID, FIRST_UTUB_ID)

    assert response.status_code == 403
    spy.assert_called()


def test_bulk_refusal_is_whole_request_with_no_per_url_result(url_utub):
    """
    GIVEN Tagging off
    WHEN a plain member bulk-applies tags to several URLs
    THEN the whole request is refused (no applied/skipped report) and no URL gained a tag
    """
    set_tags_settings(url_utub, FIRST_UTUB_ID, TAGGING_OFF)
    before = _write_state(url_utub)

    response = _call_bulk(url_utub, "web", MEMBER_ID, FIRST_UTUB_ID)

    body = response.get_json()
    assert response.status_code == 403
    assert "applied" not in body
    assert "skipped" not in body
    assert _write_state(url_utub) == before


# ---------------------------------------------------------------------------
# URL create with tags
# ---------------------------------------------------------------------------


def _create_url(
    app: Flask,
    surface: str,
    user_id: int,
    *,
    url_string: str,
    tags: list[str],
    utub_id: int = FIRST_UTUB_ID,
) -> Response:
    return _send(
        app,
        surface=surface,
        method="post",
        web_route=ROUTES.URLS.CREATE_URL,
        api_route=ROUTES.API_V1.CREATE_URL,
        user_id=user_id,
        json={
            URL_FORM.URL_STRING: url_string,
            URL_FORM.URL_TITLE: "Policy title",
            TAG_STRINGS_FIELD: tags,
        },
        utub_id=utub_id,
    )


SURFACES = [pytest.param("web", id="web"), pytest.param("api", id="api")]


@pytest.mark.parametrize("surface", SURFACES)
@pytest.mark.parametrize("user_id", [CREATOR_ID, CO_OWNER_ID])
def test_manager_create_url_with_tags_unaffected(create_utub, surface, user_id):
    """
    GIVEN Tagging off
    WHEN the owner or a co-owner creates a URL with tags
    THEN 200 and the tags are applied
    """
    set_tags_settings(create_utub, FIRST_UTUB_ID, TAGGING_OFF)

    response = _create_url(
        create_utub, surface, user_id, url_string=valid_url_strings[0], tags=FRESH_TAGS
    )

    assert response.status_code == 200
    assert len(response.get_json()[MODELS.APPLIED_TAGS]) == len(FRESH_TAGS)


@pytest.mark.parametrize("surface", SURFACES)
def test_plain_member_create_url_with_tags_refused(create_utub, surface):
    """
    GIVEN Tagging off
    WHEN a plain member creates a URL with tags
    THEN 403 URL errorCode 18 and no Urls, Utub_Urls or tag rows are written
    """
    set_tags_settings(create_utub, FIRST_UTUB_ID, TAGGING_OFF)
    before = _write_state(create_utub)

    response = _create_url(
        create_utub,
        surface,
        MEMBER_ID,
        url_string=valid_url_strings[0],
        tags=FRESH_TAGS,
    )

    assert response.status_code == 403
    assert _code(response) == CODE_URL_CREATE
    assert _message(response) == TAG_URLS_NOT_ALLOWED
    assert _write_state(create_utub) == before


@pytest.mark.parametrize("surface", SURFACES)
def test_plain_member_create_url_without_tags_succeeds(create_utub, surface):
    """
    GIVEN Tagging off
    WHEN a plain member creates the same URL with an empty tag list
    THEN 200
    """
    set_tags_settings(create_utub, FIRST_UTUB_ID, TAGGING_OFF)

    response = _create_url(
        create_utub, surface, MEMBER_ID, url_string=valid_url_strings[0], tags=[]
    )

    assert response.status_code == 200


@pytest.mark.parametrize("surface", SURFACES)
def test_plain_member_create_url_with_tags_allowed_when_tagging_on(
    create_utub, surface
):
    """
    GIVEN Tagging on
    WHEN a plain member creates a URL with tags
    THEN 200
    """
    response = _create_url(
        create_utub,
        surface,
        MEMBER_ID,
        url_string=valid_url_strings[0],
        tags=FRESH_TAGS,
    )

    assert response.status_code == 200


@pytest.mark.parametrize("surface", SURFACES)
def test_create_url_policy_before_invalid_url_validation(create_utub, surface):
    """
    GIVEN Tagging off
    WHEN a plain member submits tags together with an invalid URL
    THEN 403 code 18 (not 400) and no Urls row is created
    """
    set_tags_settings(create_utub, FIRST_UTUB_ID, TAGGING_OFF)
    before = _write_state(create_utub)

    response = _create_url(
        create_utub, surface, MEMBER_ID, url_string="not a valid url", tags=FRESH_TAGS
    )

    assert response.status_code == 403
    assert _code(response) == CODE_URL_CREATE
    assert _write_state(create_utub) == before


@pytest.mark.parametrize("surface", SURFACES)
def test_create_url_policy_before_brand_new_url_creation(create_utub, surface):
    """
    GIVEN Tagging off and a URL string not yet in the Urls table
    WHEN a plain member submits it with tags
    THEN 403 code 18 and no Urls row is created (the gate precedes get_or_create_url)
    """
    set_tags_settings(create_utub, FIRST_UTUB_ID, TAGGING_OFF)
    before = _write_state(create_utub)

    response = _create_url(
        create_utub,
        surface,
        MEMBER_ID,
        url_string="https://never-seen-before.example.com/policy",
        tags=FRESH_TAGS,
    )

    assert response.status_code == 403
    assert _code(response) == CODE_URL_CREATE
    assert _write_state(create_utub) == before


@pytest.mark.parametrize("surface", SURFACES)
def test_create_url_policy_before_already_in_utub_conflict(url_utub, surface):
    """
    GIVEN Tagging off and a URL already live in the UTub
    WHEN a plain member submits it again with tags
    THEN 403 code 18 (not the 409 conflict)
    """
    set_tags_settings(url_utub, FIRST_UTUB_ID, TAGGING_OFF)
    with url_utub.app_context():
        existing = Urls.query.order_by(Urls.id).first().url_string
    before = _write_state(url_utub)

    response = _create_url(
        url_utub, surface, MEMBER_ID, url_string=existing, tags=FRESH_TAGS
    )

    assert response.status_code == 403
    assert _code(response) == CODE_URL_CREATE
    assert _write_state(url_utub) == before


@pytest.mark.parametrize("surface", SURFACES)
def test_revive_from_trash_with_tags_refused_and_row_stays_trashed(url_utub, surface):
    """
    GIVEN Tagging off and a trashed URL row in the UTub
    WHEN a plain member re-adds it with tags
    THEN 403 code 18 and the row stays trashed
    """
    set_tags_settings(url_utub, FIRST_UTUB_ID, TAGGING_OFF)
    trashed_id = _utub_url_ids(url_utub)[1]
    trash_utub_url(url_utub, trashed_id, deleted_by=CREATOR_ID)
    with url_utub.app_context():
        trashed_string = Utub_Urls.query.get(trashed_id).standalone_url.url_string
    before = _write_state(url_utub)

    response = _create_url(
        url_utub, surface, MEMBER_ID, url_string=trashed_string, tags=FRESH_TAGS
    )

    assert response.status_code == 403
    assert _code(response) == CODE_URL_CREATE
    assert _write_state(url_utub) == before
    with url_utub.app_context():
        assert Utub_Urls.query.get(trashed_id).is_trashed


@pytest.mark.parametrize("surface", SURFACES)
def test_revive_from_trash_without_tags_still_succeeds(url_utub, surface):
    """
    GIVEN Tagging off and a trashed URL row
    WHEN a plain member re-adds it with no tags
    THEN 200 and the row is live again
    """
    set_tags_settings(url_utub, FIRST_UTUB_ID, TAGGING_OFF)
    trashed_id = _utub_url_ids(url_utub)[1]
    trash_utub_url(url_utub, trashed_id, deleted_by=CREATOR_ID)
    with url_utub.app_context():
        trashed_string = Utub_Urls.query.get(trashed_id).standalone_url.url_string

    response = _create_url(
        url_utub, surface, MEMBER_ID, url_string=trashed_string, tags=[]
    )

    assert response.status_code == 200
    with url_utub.app_context():
        assert not Utub_Urls.query.get(trashed_id).is_trashed


@pytest.mark.parametrize("surface", SURFACES)
def test_create_url_with_tags_locked_utub_returns_locked_not_tagging(
    create_utub, surface
):
    """
    GIVEN a locked UTub with Tagging off
    WHEN a plain member creates a URL with tags
    THEN UTUB_IS_LOCKED (8), not TAGGING_NOT_ALLOWED (18)
    """
    set_tags_settings(create_utub, FIRST_UTUB_ID, TAGGING_OFF)
    lock_utub(create_utub, FIRST_UTUB_ID)
    before = _write_state(create_utub)

    response = _create_url(
        create_utub,
        surface,
        MEMBER_ID,
        url_string=valid_url_strings[0],
        tags=FRESH_TAGS,
    )

    assert response.status_code == 403
    assert _code(response) == URLErrorCodes.UTUB_IS_LOCKED
    assert _write_state(create_utub) == before


@pytest.mark.parametrize("surface", SURFACES)
def test_create_url_without_tags_in_locked_utub_keeps_locked_behavior(
    create_utub, surface
):
    """
    GIVEN a locked UTub
    WHEN a plain member creates a URL with no tags
    THEN UTUB_IS_LOCKED (8), exactly as before this feature
    """
    lock_utub(create_utub, FIRST_UTUB_ID)

    response = _create_url(
        create_utub, surface, MEMBER_ID, url_string=valid_url_strings[0], tags=[]
    )

    assert response.status_code == 403
    assert _code(response) == URLErrorCodes.UTUB_IS_LOCKED


@pytest.mark.parametrize("surface", SURFACES)
def test_create_url_with_tags_post_lock_read_wins(create_utub, surface):
    """
    GIVEN Tagging on when the route guard runs and a manager turns it off before the lock
    WHEN a plain member creates a URL with tags
    THEN the locked read refuses with code 18 and nothing is written
    """
    set_tags_settings(create_utub, FIRST_UTUB_ID, {"members_can_tag": True})
    before = _write_state(create_utub)

    def flip_then_lock(*args: Any, **kwargs: Any) -> Any:
        set_tags_settings(create_utub, FIRST_UTUB_ID, TAGGING_OFF)
        return real_lock_and_reauthorize(*args, **kwargs)

    with mock.patch(LOCK_URL_CREATE, side_effect=flip_then_lock) as patched:
        response = _create_url(
            create_utub,
            surface,
            MEMBER_ID,
            url_string=valid_url_strings[0],
            tags=FRESH_TAGS,
        )

    patched.assert_called_once()
    assert response.status_code == 403
    assert _code(response) == CODE_URL_CREATE
    assert _write_state(create_utub) == before


@pytest.mark.parametrize("surface", SURFACES)
@pytest.mark.parametrize("scenario", ["revoked_member", "trashed_utub"])
def test_create_url_with_tags_revoked_or_gone_utub_is_404(
    create_utub, surface, scenario
):
    """
    GIVEN a revoked member, or a trashed UTub
    WHEN they create a URL with tags
    THEN 404 (tag-free create keeps its previous behavior)
    """
    if scenario == "revoked_member":
        remove_member(create_utub, FIRST_UTUB_ID, MEMBER_ID)
        actor = MEMBER_ID
    else:
        trash_utub(create_utub, FIRST_UTUB_ID, deleted_by=CREATOR_ID)
        actor = CREATOR_ID
    before = _write_state(create_utub)

    response = _create_url(
        create_utub, surface, actor, url_string=valid_url_strings[0], tags=FRESH_TAGS
    )

    assert response.status_code == 404
    assert _write_state(create_utub) == before


@pytest.mark.parametrize("surface", SURFACES)
def test_create_url_with_tags_member_revoked_after_route_guard_is_404_from_the_lock(
    create_utub, surface
):
    """
    GIVEN a member revoked after the route guard but before the lock
    WHEN they create a URL with tags
    THEN lock_and_reauthorize returns 404 with nothing written
    """
    before = _write_state(create_utub)

    def revoke_then_lock(*args: Any, **kwargs: Any) -> Any:
        remove_member(create_utub, FIRST_UTUB_ID, MEMBER_ID)
        return real_lock_and_reauthorize(*args, **kwargs)

    with mock.patch(LOCK_URL_CREATE, side_effect=revoke_then_lock) as patched:
        response = _create_url(
            create_utub,
            surface,
            MEMBER_ID,
            url_string=valid_url_strings[0],
            tags=FRESH_TAGS,
        )

    patched.assert_called_once()
    assert response.status_code == 404
    assert _write_state(create_utub) == before


@pytest.mark.parametrize("surface", SURFACES)
def test_create_url_with_tags_policy_refusal_rolls_back(create_utub, surface):
    """
    GIVEN tagging is off
    WHEN a plain member creates a URL with tags
    THEN the session is rolled back so the row lock is released
    """
    set_tags_settings(create_utub, FIRST_UTUB_ID, TAGGING_OFF)

    with mock.patch.object(db.session, "rollback", wraps=db.session.rollback) as spy:
        response = _create_url(
            create_utub,
            surface,
            MEMBER_ID,
            url_string=valid_url_strings[0],
            tags=FRESH_TAGS,
        )

    assert response.status_code == 403
    spy.assert_called()


# ---------------------------------------------------------------------------
# Revive-on-edit stays ungated
# ---------------------------------------------------------------------------


def test_revive_on_edit_still_carries_existing_tags_for_plain_member(url_utub):
    """
    GIVEN Tagging off, the plain member's own tagged URL, and a trashed URL they added
    WHEN they edit their URL's link to the trashed URL's link (revive-on-edit)
    THEN 200 and the revived row carries the edited row's existing tags
    """
    set_tags_settings(url_utub, FIRST_UTUB_ID, TAGGING_OFF)
    url_ids = _utub_url_ids(url_utub)
    edited_id, trashed_id = url_ids[0], url_ids[1]
    set_url_adder(url_utub, edited_id, MEMBER_ID)
    set_url_adder(url_utub, trashed_id, MEMBER_ID)
    with url_utub.app_context():
        edited_tag_ids = Utub_Urls.query.get(edited_id).associated_tag_ids
        trashed_string = Utub_Urls.query.get(trashed_id).standalone_url.url_string
    assert edited_tag_ids
    trash_utub_url(url_utub, trashed_id, deleted_by=MEMBER_ID, trashed_tag_ids=[])

    response = _send(
        url_utub,
        surface="web",
        method="patch",
        web_route=ROUTES.URLS.UPDATE_URL,
        api_route=None,
        user_id=MEMBER_ID,
        json={URL_FORM.URL_STRING: trashed_string},
        utub_id=FIRST_UTUB_ID,
        utub_url_id=edited_id,
    )

    assert response.status_code == 200
    with url_utub.app_context():
        assert Utub_Urls.query.get(trashed_id).associated_tag_ids == edited_tag_ids
