from typing import Any
from unittest.mock import MagicMock

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient
from flask.wrappers import Response

from backend import db
from backend.invite_links.lookup import find_invite_by_token
from backend.models.email_validations import Email_Validations
from backend.models.users import Users
from backend.models.utub_invite_links import Utub_Invite_Links
from backend.splash.services import user_registration
from backend.utils.all_routes import ROUTES
from backend.utils.constants import EMAIL_CONSTANTS
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.splash_form_strs import INVITE_NEXT, REGISTER_FORM
from tests.integration.invite_links.invite_route_helpers import seed_dead
from tests.integration.short_links.short_link_helpers import (
    CREATOR_ID,
    FIRST_UTUB_ID,
    SECOND_USER_ID,
)
from tests.integration.splash.conftest import (
    create_user,
    patch_email_confirmation_spy,
    register_json,
)
from tests.utils_for_test import UNKNOWN_INVITE_TOKEN, add_invite_link

pytestmark = pytest.mark.splash

PASSWORD = "InvitePass1234"
OTHER_USERNAME = "InviteHandoffOther"
FRESH_USERNAME = "InviteHandoffFresh"
FRESH_USERNAME_2 = "InviteHandoffFresh2"
EXISTING_USERNAME = "InviteHandoffV"
SECOND_UTUB_ID = FIRST_UTUB_ID + 1


def _identity(index: int) -> dict[str, str]:
    """A register identity that never collides with the mock users."""
    email = f"invitehandoff{index}@email.com"
    return {
        REGISTER_FORM.USERNAME: f"InviteHandoff{index}",
        REGISTER_FORM.EMAIL: email,
        REGISTER_FORM.CONFIRM_EMAIL: email,
        REGISTER_FORM.PASSWORD: PASSWORD,
        REGISTER_FORM.CONFIRM_PASSWORD: PASSWORD,
    }


def _token_of(app: Flask, invite_id: int) -> str:
    with app.app_context():
        invite = db.session.get(Utub_Invite_Links, invite_id)
        assert invite is not None
        return invite.token


def _live_token(app: Flask) -> str:
    return _token_of(app, add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID))


def _post_register(
    client: FlaskClient, csrf: str, identity: dict[str, str], **extra: Any
) -> Response:
    return client.post(
        url_for(ROUTES.SPLASH.REGISTER),
        json={**register_json(identity), **extra},
        headers={"X-CSRFToken": csrf},
    )


def _stored_ref(app: Flask, identity: dict[str, str]) -> int | None:
    """The pending_invite_id stored for the identity's email, after a fresh read."""
    with app.app_context():
        db.session.expire_all()
        user = Users.query.filter(
            Users.email == identity[REGISTER_FORM.EMAIL].lower()
        ).one()
        return user.email_confirm.pending_invite_id


def _invite_form(token: str) -> str:
    return f"/invite/{token}/register"


def test_branch4_stores_live_invite_both_forms(
    app, every_user_makes_a_unique_utub, load_register_page, monkeypatch
):
    patch_email_confirmation_spy(monkeypatch)
    client, csrf = load_register_page
    invite_id = add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)
    token = _token_of(app, invite_id)

    for index, value in enumerate((_invite_form(token), f"/invite/{token}"), start=1):
        identity = _identity(index)
        response = _post_register(client, csrf, identity, **{INVITE_NEXT: value})
        assert response.status_code == 200
        assert _stored_ref(app, identity) == invite_id


@pytest.mark.parametrize("state", ["expired", "used_up", "revoked"])
def test_branch4_stores_dead_invite(
    app, every_user_makes_a_unique_utub, load_register_page, monkeypatch, state
):
    patch_email_confirmation_spy(monkeypatch)
    client, csrf = load_register_page
    if state == "revoked":
        invite_id = add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID, revoked=True)
    else:
        invite_id = seed_dead(app, state)
    identity = _identity(1)
    response = _post_register(
        client, csrf, identity, **{INVITE_NEXT: _invite_form(_token_of(app, invite_id))}
    )
    assert response.status_code == 200
    assert _stored_ref(app, identity) == invite_id


@pytest.mark.parametrize(
    "value",
    [
        _invite_form(UNKNOWN_INVITE_TOKEN),
        "/invite/" + "a" * 21,
        "/invite/" + "a" * 22 + "/x",
        "/home",
        "",
        "a" * 22,
        123,
        {},
        [],
        True,
        None,
    ],
)
def test_branch4_unresolved_values_store_null_and_never_400(
    app, every_user_makes_a_unique_utub, load_register_page, monkeypatch, value
):
    patch_email_confirmation_spy(monkeypatch)
    client, csrf = load_register_page
    identity = _identity(1)
    response = _post_register(client, csrf, identity, **{INVITE_NEXT: value})
    assert response.status_code == 200
    assert _stored_ref(app, identity) is None


def test_branch4_oversized_value_is_not_a_400(
    app, every_user_makes_a_unique_utub, load_register_page, monkeypatch
):
    patch_email_confirmation_spy(monkeypatch)
    client, csrf = load_register_page
    identity = _identity(1)
    response = _post_register(client, csrf, identity, **{INVITE_NEXT: "x" * 5000})
    assert response.status_code == 200
    assert _stored_ref(app, identity) is None


def test_branch3_stores_then_latest_wins_then_unresolved_keeps(
    app, every_user_makes_a_unique_utub, load_register_page, monkeypatch
):
    patch_email_confirmation_spy(monkeypatch)
    client, csrf = load_register_page
    identity = _identity(1)
    create_user(
        app,
        identity[REGISTER_FORM.USERNAME],
        identity[REGISTER_FORM.EMAIL],
        PASSWORD,
        validated=False,
    )
    first_id = add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)
    # One active invite per UTub, so the second live invite lives in UTub 2.
    second_id = add_invite_link(app, SECOND_UTUB_ID, SECOND_USER_ID)
    other = {**identity, REGISTER_FORM.USERNAME: OTHER_USERNAME}

    _post_register(
        client, csrf, other, **{INVITE_NEXT: _invite_form(_token_of(app, first_id))}
    )
    assert _stored_ref(app, identity) == first_id

    _post_register(
        client, csrf, other, **{INVITE_NEXT: _invite_form(_token_of(app, second_id))}
    )
    assert _stored_ref(app, identity) == second_id

    for value in (_invite_form(UNKNOWN_INVITE_TOKEN), "/home", None):
        extra = {} if value is None else {INVITE_NEXT: value}
        response = _post_register(client, csrf, other, **extra)
        assert response.status_code == 200
        assert _stored_ref(app, identity) == second_id


def test_branch3_rate_limited_still_stores_and_sends_nothing(
    app, every_user_makes_a_unique_utub, load_register_page, monkeypatch
):
    send_spy = patch_email_confirmation_spy(monkeypatch)
    client, csrf = load_register_page
    identity = _identity(1)
    create_user(
        app,
        identity[REGISTER_FORM.USERNAME],
        identity[REGISTER_FORM.EMAIL],
        PASSWORD,
        validated=False,
    )
    with app.app_context():
        pending = Users.query.filter(
            Users.email == identity[REGISTER_FORM.EMAIL].lower()
        ).one()
        pending.email_confirm.attempts = EMAIL_CONSTANTS.MAX_EMAIL_ATTEMPTS_IN_HOUR + 1
        pending.email_confirm.last_attempt = utc_now()
        db.session.commit()
    invite_id = add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)
    other = {**identity, REGISTER_FORM.USERNAME: OTHER_USERNAME}

    response = _post_register(
        client, csrf, other, **{INVITE_NEXT: _invite_form(_token_of(app, invite_id))}
    )
    assert response.status_code == 200
    send_spy.assert_not_called()
    assert _stored_ref(app, identity) == invite_id


def test_branch3_email_confirm_none_stores_nothing(
    app, every_user_makes_a_unique_utub, load_register_page, monkeypatch
):
    patch_email_confirmation_spy(monkeypatch)
    client, csrf = load_register_page
    identity = _identity(1)
    with app.app_context():
        erased = Users(
            username=identity[REGISTER_FORM.USERNAME],
            email=identity[REGISTER_FORM.EMAIL].lower(),
            plaintext_password=PASSWORD,
        )
        erased.email_validated = False
        db.session.add(erased)
        db.session.commit()
    token = _live_token(app)
    other = {**identity, REGISTER_FORM.USERNAME: OTHER_USERNAME}

    response = _post_register(client, csrf, other, **{INVITE_NEXT: _invite_form(token)})
    assert response.status_code == 200
    with app.app_context():
        assert Email_Validations.query.count() == 0


def test_branches_1_and_2_never_write_a_reference(
    app, every_user_makes_a_unique_utub, load_register_page, monkeypatch
):
    patch_email_confirmation_spy(monkeypatch)
    client, csrf = load_register_page
    taken = _identity(1)
    create_user(
        app,
        taken[REGISTER_FORM.USERNAME],
        taken[REGISTER_FORM.EMAIL],
        PASSWORD,
        validated=True,
    )
    pending = _identity(2)
    create_user(
        app,
        pending[REGISTER_FORM.USERNAME],
        pending[REGISTER_FORM.EMAIL],
        PASSWORD,
        validated=False,
    )
    # The pending user already holds a reference to an invite in UTub 1; the
    # posted token is a different live invite in UTub 2.
    existing_id = add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)
    with app.app_context():
        pending_user = Users.query.filter(
            Users.email == pending[REGISTER_FORM.EMAIL]
        ).one()
        pending_user.email_confirm.pending_invite_id = existing_id
        db.session.commit()
    posted_id = add_invite_link(app, SECOND_UTUB_ID, SECOND_USER_ID)
    value = _invite_form(_token_of(app, posted_id))

    # Branch 1: username taken (validated). Branch 2: email taken (validated).
    username_taken = {
        **_identity(3),
        REGISTER_FORM.USERNAME: taken[REGISTER_FORM.USERNAME],
    }
    email_taken = {
        **taken,
        REGISTER_FORM.USERNAME: FRESH_USERNAME,
    }
    # Branch 1 with an unvalidated email owner must not touch that owner either.
    username_taken_pending_email = {
        **pending,
        REGISTER_FORM.USERNAME: taken[REGISTER_FORM.USERNAME],
    }
    expected_statuses = (
        (username_taken, 400),
        (email_taken, 200),
        (username_taken_pending_email, 400),
    )
    for body, status in expected_statuses:
        response = _post_register(client, csrf, body, **{INVITE_NEXT: value})
        assert response.status_code == status

    assert _stored_ref(app, pending) == existing_id
    with app.app_context():
        references = [
            row.pending_invite_id
            for row in Email_Validations.query.all()
            if row.pending_invite_id is not None
        ]
        assert references == [existing_id]


def test_lookup_runs_once_on_every_branch_and_never_for_unparseable(
    app, every_user_makes_a_unique_utub, load_register_page, monkeypatch
):
    patch_email_confirmation_spy(monkeypatch)
    client, csrf = load_register_page
    spy = MagicMock(wraps=find_invite_by_token)
    monkeypatch.setattr(user_registration, "find_invite_by_token", spy)
    validated = _identity(1)
    create_user(
        app,
        validated[REGISTER_FORM.USERNAME],
        validated[REGISTER_FORM.EMAIL],
        PASSWORD,
        validated=True,
    )
    pending = _identity(2)
    create_user(
        app,
        pending[REGISTER_FORM.USERNAME],
        pending[REGISTER_FORM.EMAIL],
        PASSWORD,
        validated=False,
    )
    value = _invite_form(_live_token(app))
    bodies = [
        {**_identity(3), REGISTER_FORM.USERNAME: validated[REGISTER_FORM.USERNAME]},
        {**validated, REGISTER_FORM.USERNAME: FRESH_USERNAME},
        {**pending, REGISTER_FORM.USERNAME: FRESH_USERNAME_2},
        _identity(4),
    ]
    for body in bodies:
        spy.reset_mock()
        _post_register(client, csrf, body, **{INVITE_NEXT: value})
        assert spy.call_count == 1

    for extra in ({}, {INVITE_NEXT: "/home"}, {INVITE_NEXT: 123}):
        spy.reset_mock()
        _post_register(client, csrf, _identity(5), **extra)
        spy.assert_not_called()


_OPACITY_CASES = [
    "new_valid",
    "new_dead",
    "new_unknown",
    "new_malformed",
    "validated_with_token",
    "validated_without_token",
    "unvalidated_stored",
    "unvalidated_nothing_stored",
    "unvalidated_email_confirm_none",
]


_CASES_USING_LIVE_INVITE = frozenset(
    {
        "new_valid",
        "validated_with_token",
        "unvalidated_stored",
        "unvalidated_email_confirm_none",
    }
)


def _stable_headers(response: Response) -> list[tuple[str, str]]:
    return sorted(
        (name, value)
        for name, value in response.headers.items()
        if name.lower() not in ("date", "set-cookie", "x-request-id")
    )


@pytest.mark.parametrize("case", _OPACITY_CASES)
def test_register_responses_are_opaque_across_invite_cases(
    app, every_user_makes_a_unique_utub, load_register_page, monkeypatch, case
):
    patch_email_confirmation_spy(monkeypatch)
    client, csrf = load_register_page

    reference = _post_register(client, csrf, _identity(1))
    assert reference.status_code == 200

    # Only one active invite per UTub: seed the live one only for cases using it.
    live_id: int | None = None
    live = ""
    if case in _CASES_USING_LIVE_INVITE:
        live_id = add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)
        live = _invite_form(_token_of(app, live_id))
    extra: dict[str, Any] = {}
    body = _identity(2)
    expected_ref: int | None = None
    if case == "new_valid":
        extra = {INVITE_NEXT: live}
        expected_ref = live_id
    elif case == "new_dead":
        dead_id = seed_dead(app, "expired")
        extra = {INVITE_NEXT: _invite_form(_token_of(app, dead_id))}
        expected_ref = dead_id
    elif case == "new_unknown":
        extra = {INVITE_NEXT: _invite_form(UNKNOWN_INVITE_TOKEN)}
    elif case == "new_malformed":
        extra = {INVITE_NEXT: "/invite/short"}
    elif case.startswith("validated"):
        create_user(
            app,
            EXISTING_USERNAME,
            body[REGISTER_FORM.EMAIL],
            PASSWORD,
            validated=True,
        )
        body = {**body, REGISTER_FORM.USERNAME: FRESH_USERNAME}
        extra = {INVITE_NEXT: live} if case == "validated_with_token" else {}
    elif case.startswith("unvalidated"):
        if case == "unvalidated_email_confirm_none":
            with app.app_context():
                erased = Users(
                    username=EXISTING_USERNAME,
                    email=body[REGISTER_FORM.EMAIL].lower(),
                    plaintext_password=PASSWORD,
                )
                erased.email_validated = False
                db.session.add(erased)
                db.session.commit()
        else:
            create_user(
                app,
                EXISTING_USERNAME,
                body[REGISTER_FORM.EMAIL],
                PASSWORD,
                validated=False,
            )
        body = {**body, REGISTER_FORM.USERNAME: FRESH_USERNAME}
        if case in _CASES_USING_LIVE_INVITE:
            extra = {INVITE_NEXT: live}
        if case == "unvalidated_stored":
            expected_ref = live_id

    response = _post_register(client, csrf, body, **extra)

    # Prove the intended branch ran: the per-case side effect is what the name says.
    if case.startswith("new_") or case.startswith("unvalidated_"):
        if case == "unvalidated_email_confirm_none":
            with app.app_context():
                assert Email_Validations.query.count() == 1  # only the reference's
        else:
            assert _stored_ref(app, body) == expected_ref

    assert response.status_code == reference.status_code
    assert response.get_data() == reference.get_data()
    assert _stable_headers(response) == _stable_headers(reference)
