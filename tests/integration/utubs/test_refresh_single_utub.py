from datetime import datetime
from typing import Tuple

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient
from flask_login import current_user
from werkzeug.test import TestResponse

from backend import db
from backend.metrics.events import EventName
from backend.models.users import Users
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utubs import Utubs
from backend.utils.all_routes import ROUTES
from backend.utils.strings.json_strs import FAILURE_GENERAL
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import MODELS
from backend.utils.strings.url_validation_strs import URL_VALIDATION
from tests.integration.system.metrics_helpers import count_counter_keys
from tests.settings_stub import (
    DEFAULT_MEMBER_SETTINGS_DICT,
    DEFAULT_SETTINGS_DICT,
    STUB_KEY,
    URLS_DEFAULTS,
    patch_settings_model,
)
from tests.utils_for_test import trash_utub

pytestmark = pytest.mark.utubs

AJAX_HEADERS = {URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST}


def _capture_open_state(
    *, app: Flask, utub_id: int
) -> Tuple[datetime, dict[int, datetime | None]]:
    """Snapshot ``Utubs.last_updated`` and every member's ``last_opened_at``."""
    with app.app_context():
        utub: Utubs = Utubs.query.get(utub_id)
        members: list[Utub_Members] = Utub_Members.query.filter(
            Utub_Members.utub_id == utub_id
        ).all()
        return utub.last_updated, {
            member.user_id: member.last_opened_at for member in members
        }


def _refresh(client: FlaskClient, utub_id: int) -> TestResponse:
    return client.get(
        url_for(ROUTES.UTUBS.REFRESH_SINGLE_UTUB, utub_id=utub_id),
        headers=AJAX_HEADERS,
    )


def _open(client: FlaskClient, utub_id: int) -> TestResponse:
    return client.get(
        url_for(ROUTES.UTUBS.GET_SINGLE_UTUB, utub_id=utub_id),
        headers=AJAX_HEADERS,
    )


def _assert_refresh_matches_open_payload(
    *, client: FlaskClient, app: Flask, utub_id: int
) -> dict:
    """Refresh first (read-only), then open, and compare the two payloads."""
    before_refresh = _capture_open_state(app=app, utub_id=utub_id)

    refresh_response = _refresh(client, utub_id)

    assert refresh_response.status_code == 200
    assert _capture_open_state(app=app, utub_id=utub_id) == before_refresh

    open_response = _open(client, utub_id)

    assert open_response.status_code == 200
    assert refresh_response.json is not None
    assert refresh_response.json == open_response.json
    return refresh_response.json


def test_refresh_payload_matches_open_as_creator(
    add_single_utub_as_user_after_logging_in: Tuple[FlaskClient, int, str, Flask],
):
    """
    GIVEN the creator of a UTub
    WHEN they refresh the UTub
    THEN the payload equals the open payload and nothing is written
    """
    client, utub_id, _, app = add_single_utub_as_user_after_logging_in

    _assert_refresh_matches_open_payload(client=client, app=app, utub_id=utub_id)


def test_refresh_payload_matches_open_as_member(
    add_single_user_to_utub_without_logging_in,
    login_second_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a plain member of a UTub
    WHEN they refresh the UTub
    THEN the payload equals the open payload and nothing is written
    """
    client, _, _, app = login_second_user_without_register

    with app.app_context():
        utub_id = Utubs.query.filter(Utubs.utub_creator != current_user.id).first().id

    _assert_refresh_matches_open_payload(client=client, app=app, utub_id=utub_id)


def test_refresh_payload_matches_open_as_co_creator(
    add_co_creator_to_utub_without_logging_in,
    login_second_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a co-creator of a UTub
    WHEN they refresh the UTub
    THEN the payload equals the open payload, with isCoCreator True
    """
    client, _, _, app = login_second_user_without_register

    with app.app_context():
        utub_id = Utubs.query.filter(Utubs.utub_creator != current_user.id).first().id

    refresh_json = _assert_refresh_matches_open_payload(
        client=client, app=app, utub_id=utub_id
    )

    assert refresh_json[MODELS.IS_CO_CREATOR] is True
    assert refresh_json[MODELS.IS_CREATOR] is False
    assert any(
        member[MODELS.MEMBER_ROLE] == Member_Role.CO_CREATOR.value
        for member in refresh_json[MODELS.MEMBERS]
    )


def test_refresh_carries_callers_member_settings_only(
    add_single_user_to_utub_without_logging_in,
    login_second_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN the creator holding a stored override and a plain member holding none
    WHEN the plain member refreshes the UTub
    THEN `memberSettings` is the all-default slice, equal to the open payload
    """
    client, _, member, app = login_second_user_without_register

    with app.app_context():
        utub_id = Utubs.query.filter(Utubs.utub_creator != member.id).first().id
        creator_row: Utub_Members = Utub_Members.query.filter(
            Utub_Members.utub_id == utub_id, Utub_Members.user_id != member.id
        ).first()
        creator_row.settings = {"urls": {"hide_date_added": True}}
        db.session.commit()

    refresh_json = _refresh(client, utub_id).json
    assert refresh_json is not None
    assert refresh_json[MODELS.MEMBER_SETTINGS] == DEFAULT_MEMBER_SETTINGS_DICT
    assert refresh_json == _open(client, utub_id).json


def test_refresh_carries_callers_own_stored_member_override(
    add_single_utub_as_user_after_logging_in: Tuple[FlaskClient, int, str, Flask],
):
    """
    GIVEN the caller's own membership stores a sort override
    WHEN they refresh the UTub
    THEN `memberSettings` carries it and equals the open payload
    """
    client, utub_id, _, app = add_single_utub_as_user_after_logging_in

    with app.app_context():
        membership: Utub_Members = Utub_Members.query.filter(
            Utub_Members.utub_id == utub_id
        ).first()
        membership.settings = {"urls": {"sort": "oldest"}}
        db.session.commit()

    refresh_json = _refresh(client, utub_id).json
    assert refresh_json is not None
    assert refresh_json[MODELS.MEMBER_SETTINGS]["urls"]["sort"] == "oldest"
    assert refresh_json == _open(client, utub_id).json


def test_refresh_includes_settings_defaults_and_stored_override(
    add_single_utub_as_user_after_logging_in: Tuple[FlaskClient, int, str, Flask],
    monkeypatch: pytest.MonkeyPatch,
):
    """
    GIVEN a UTub with NULL settings, then a stored override under a stubbed settings model
    WHEN the member refreshes the UTub
    THEN `settings` carries defaults, then the override merged over defaults
    """
    client, utub_id, _, app = add_single_utub_as_user_after_logging_in

    default_json = _refresh(client, utub_id).json
    assert default_json is not None
    assert default_json[MODELS.SETTINGS] == DEFAULT_SETTINGS_DICT

    patch_settings_model(monkeypatch)
    with app.app_context():
        utub: Utubs = Utubs.query.get(utub_id)
        utub.settings = {"urls": {STUB_KEY: True}}
        db.session.commit()

    refresh_json = _refresh(client, utub_id).json
    assert refresh_json is not None
    assert refresh_json[MODELS.SETTINGS]["urls"] == {**URLS_DEFAULTS, STUB_KEY: True}
    assert refresh_json == _open(client, utub_id).json


def test_refresh_does_not_write_last_updated_or_last_opened_at(
    add_single_utub_as_user_after_logging_in: Tuple[FlaskClient, int, str, Flask],
):
    """
    GIVEN a UTub the user has never opened
    WHEN the user refreshes it repeatedly
    THEN ``Utubs.last_updated`` and every ``last_opened_at`` are unchanged
    """
    client, utub_id, _, app = add_single_utub_as_user_after_logging_in

    before = _capture_open_state(app=app, utub_id=utub_id)

    assert _refresh(client, utub_id).status_code == 200
    assert _refresh(client, utub_id).status_code == 200

    after = _capture_open_state(app=app, utub_id=utub_id)
    assert after == before
    assert all(opened_at is None for opened_at in after[1].values())


def test_refresh_does_not_record_utub_opened_metric(
    metrics_enabled_app,
    provide_metrics_redis,
    add_single_utub_as_user_after_logging_in: Tuple[FlaskClient, int, str, Flask],
):
    """
    GIVEN a logged-in member of a UTub and metrics enabled
    WHEN they refresh the UTub
    THEN the request succeeds and no UTUB_OPENED counter is written
    """
    client, utub_id, _, _ = add_single_utub_as_user_after_logging_in

    assert count_counter_keys(provide_metrics_redis, EventName.UTUB_OPENED) == 0

    response = _refresh(client, utub_id)

    assert response.status_code == 200
    assert count_counter_keys(provide_metrics_redis, EventName.UTUB_OPENED) == 0

    # Control: a real open does move the counter, so the zero above is meaningful
    assert _open(client, utub_id).status_code == 200
    assert count_counter_keys(provide_metrics_redis, EventName.UTUB_OPENED) == 1


def test_refresh_as_not_member_is_404(
    every_user_makes_a_unique_utub,
    login_second_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a user who is not a member of a UTub
    WHEN they refresh it
    THEN the server responds 404 with the generic not-found message
    """
    client, _, _, app = login_second_user_without_register

    with app.app_context():
        utub_id = Utubs.query.filter(Utubs.utub_creator != current_user.id).first().id

    response = _refresh(client, utub_id)

    assert response.status_code == 404
    json_response = response.get_json()
    assert json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert json_response[STD_JSON.MESSAGE] == FAILURE_GENERAL.NOT_FOUND


def test_refresh_trashed_utub_as_creator_is_404(
    add_single_utub_as_user_after_logging_in: Tuple[FlaskClient, int, str, Flask],
):
    """
    GIVEN the creator of a UTub that has been moved to trash
    WHEN they refresh it
    THEN the server responds 404 with the generic not-found message
    """
    client, utub_id, _, app = add_single_utub_as_user_after_logging_in

    with app.app_context():
        creator_user_id = current_user.id

    trash_utub(app, utub_id, deleted_by=creator_user_id)

    response = _refresh(client, utub_id)

    assert response.status_code == 404
    json_response = response.get_json()
    assert json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert json_response[STD_JSON.MESSAGE] == FAILURE_GENERAL.NOT_FOUND


def test_refresh_trashed_utub_as_member_is_404(
    every_user_in_every_utub,
    login_second_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a trashed UTub in which user 2 is a plain member
    WHEN user 2 refreshes it
    THEN the server responds 404 with the generic not-found message
    """
    client, _, user, app = login_second_user_without_register

    with app.app_context():
        member_row: Utub_Members = Utub_Members.query.filter(
            Utub_Members.user_id == user.id,
            Utub_Members.member_role == Member_Role.MEMBER,
        ).first()
        trashed_utub_id = member_row.utub_id
        deleter_id = Utubs.query.get(trashed_utub_id).utub_creator

    trash_utub(app, trashed_utub_id, deleted_by=deleter_id)

    response = _refresh(client, trashed_utub_id)

    assert response.status_code == 404
    json_response = response.get_json()
    assert json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert json_response[STD_JSON.MESSAGE] == FAILURE_GENERAL.NOT_FOUND


def test_refresh_reflects_locked_state(
    add_single_utub_as_user_after_logging_in: Tuple[FlaskClient, int, str, Flask],
):
    """
    GIVEN a UTub locked directly through the ORM
    WHEN a member refreshes it
    THEN the payload reports isLocked True
    """
    client, utub_id, _, app = add_single_utub_as_user_after_logging_in

    with app.app_context():
        utub_to_lock: Utubs = Utubs.query.get(utub_id)
        assert not utub_to_lock.is_locked
        utub_to_lock.is_locked = True
        db.session.commit()

    response = _refresh(client, utub_id)

    assert response.status_code == 200
    assert response.json is not None
    assert response.json[MODELS.IS_LOCKED]


def test_refresh_without_ajax_request_redirects(
    add_single_utub_as_user_after_logging_in: Tuple[FlaskClient, int, str, Flask],
):
    """
    GIVEN a logged-in member of a UTub
    WHEN they refresh it without the AJAX header
    THEN the server responds 302
    """
    client, utub_id, _, _ = add_single_utub_as_user_after_logging_in

    response = client.get(
        url_for(ROUTES.UTUBS.REFRESH_SINGLE_UTUB, utub_id=utub_id),
        headers={URL_VALIDATION.X_REQUESTED_WITH: "not-ajax"},
    )

    assert response.status_code == 302
