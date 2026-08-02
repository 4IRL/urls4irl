"""Integration tests for the irreversible self-delete endpoint
(``DELETE /users/<id>``).

Mirrors ``test_account_deactivate.py``'s fixture/CSRF conventions (the
``login_first_user_with_register`` fixture, the meta-tag CSRF scrape, and the
autouse ``reauth-fail:*`` Redis reset) but exercises the GDPR-erasure path: the
account is tombstoned in place via the shared ``erase_user_core`` and the acting
session is logged out. Replicates the admin erase membership matrix for the self
path (solo-deleted, ownership-transferred, non-creator-removed), asserts the new
self-actor audit trail (DD-4) and the ``ACCOUNT_DELETED`` metric, verifies the
transfer-count context (DD-5) and the typed-username confirmation re-check (DD-C).
The OAuth-only round-trip is covered separately in
``test_account_removal_oauth_proof.py``.
"""

from __future__ import annotations

from typing import Generator, Tuple

import pytest
from flask import Flask, g, url_for
from flask.testing import FlaskClient
from flask_login import login_user
from redis import Redis

from backend import db
from backend.admin.account_data_service import (
    TOMBSTONE_EMAIL_DOMAIN,
    TOMBSTONE_USERNAME_PREFIX,
    is_tombstoned,
)
from backend.api_v1.services.tokens import issue_refresh_token
from backend.metrics.events import EventName
from backend.models.api_refresh_tokens import ApiRefreshTokens
from backend.models.audit_log import AuditLog
from backend.models.users import User_Role, Users
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utubs import Utubs
from backend.schemas.users import AccountRemovalResponseSchema
from backend.users.constants import DeleteAccountErrorCodes
from backend.users.services.account_service import build_account_info_context
from backend.utils.all_routes import ROUTES
from backend.utils.constants import USER_CONSTANTS
from backend.utils.strings import model_strs
from backend.utils.strings.config_strs import CONFIG_ENVS
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.splash_form_strs import LOGIN_FORM
from backend.utils.strings.user_strs import (
    ACCOUNT_AUDIT_ACTIONS,
    ACCOUNT_DELETED_SUCCESS,
    REDIRECT_URL,
    USER_FAILURE,
)
from tests.conftest import AjaxFlaskLoginClient
from tests.integration.system.metrics_helpers import count_counter_keys
from tests.integration.utils import assert_response_conforms_to_schema
from tests.models_for_test import valid_user_1
from tests.utils_for_test import get_csrf_token

pytestmark = pytest.mark.account_and_support

_CURRENT_PASSWORD = valid_user_1[model_strs.PASSWORD]
_WRONG_PASSWORD = "TotallyWrongPassword!23"
_USERNAME = valid_user_1[LOGIN_FORM.USERNAME]


@pytest.fixture(autouse=True)
def _reset_reauth_failure_counter(app: Flask) -> Generator[None, None, None]:
    """Clear the worker-scoped ``reauth-fail:*`` Redis counter before and after
    every test in this module (copied from ``test_account_deactivate.py`` — the
    per-user re-auth lockout counter survives DB teardown, so without this a
    wrong-password test would 429 a later unrelated test on the same xdist
    worker)."""

    def _clear() -> None:
        redis_uri = app.config.get(CONFIG_ENVS.REDIS_URI)
        if not redis_uri or redis_uri == "memory://":
            return
        client = Redis.from_url(redis_uri)
        try:
            keys = client.keys("reauth-fail:*")
            if keys:
                client.delete(*keys)
        finally:
            client.close()

    _clear()
    yield
    _clear()


def _delete_payload(
    *,
    current_password: str | None = _CURRENT_PASSWORD,
    confirm_username: str = _USERNAME,
) -> dict[str, str | None]:
    return {"currentPassword": current_password, "confirmUsername": confirm_username}


def _clear_flask_login_request_cache() -> None:
    """Drop Flask-Login's per-request user cache (``g._login_user``) so the next
    request consults the user_loader again (mirrors ``test_account_deactivate``)."""
    if hasattr(g, "_login_user"):
        delattr(g, "_login_user")


def _seed_user(app: Flask, *, username: str, email: str) -> int:
    """Create a non-admin email-validated user with a local password; return id."""
    with app.app_context():
        user = Users(username=username, email=email, plaintext_password="OtherPass1!")
        user.email_validated = True
        db.session.add(user)
        db.session.commit()
        return user.id


def _seed_solo_utub(app: Flask, *, creator_id: int, name: str) -> int:
    """Create a UTub whose only member is ``creator_id``; return the UTub id."""
    with app.app_context():
        new_utub = Utubs(name=name, utub_creator=creator_id, utub_description="")
        db.session.add(new_utub)
        db.session.flush()
        db.session.add(
            Utub_Members(
                utub_id=new_utub.id,
                user_id=creator_id,
                member_role=Member_Role.CREATOR,
            )
        )
        db.session.commit()
        return new_utub.id


def _seed_shared_utub(app: Flask, *, creator_id: int, other_id: int, name: str) -> int:
    """Create a UTub created by ``creator_id`` with ``other_id`` as a co-creator;
    return the UTub id."""
    with app.app_context():
        new_utub = Utubs(name=name, utub_creator=creator_id, utub_description="")
        db.session.add(new_utub)
        db.session.flush()
        db.session.add_all(
            [
                Utub_Members(
                    utub_id=new_utub.id,
                    user_id=creator_id,
                    member_role=Member_Role.CREATOR,
                ),
                Utub_Members(
                    utub_id=new_utub.id,
                    user_id=other_id,
                    member_role=Member_Role.CO_CREATOR,
                ),
            ]
        )
        db.session.commit()
        return new_utub.id


def _seed_membership_in_others_utub(
    app: Flask, *, creator_id: int, member_id: int, name: str
) -> int:
    """Create a UTub owned by ``creator_id`` with ``member_id`` as a plain member;
    return the UTub id."""
    with app.app_context():
        new_utub = Utubs(name=name, utub_creator=creator_id, utub_description="")
        db.session.add(new_utub)
        db.session.flush()
        db.session.add_all(
            [
                Utub_Members(
                    utub_id=new_utub.id,
                    user_id=creator_id,
                    member_role=Member_Role.CREATOR,
                ),
                Utub_Members(
                    utub_id=new_utub.id,
                    user_id=member_id,
                    member_role=Member_Role.MEMBER,
                ),
            ]
        )
        db.session.commit()
        return new_utub.id


def _seed_refresh_token(app: Flask, user_id: int) -> int:
    with app.app_context():
        user: Users = Users.query.get(user_id)
        issue_refresh_token(user=user)
        token_row: ApiRefreshTokens = ApiRefreshTokens.query.filter_by(
            user_id=user_id
        ).first()
        return token_row.id


# --------------------------------------------------------------------------- #
# Happy path — tombstone + logout + audit trail.
# --------------------------------------------------------------------------- #


def test_delete_password_happy_path_tombstones_and_logs_out(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A valid delete returns 200 with the splash ``redirectUrl``, tombstones the
    account in place (username/email tombstoned, password None, email_validated
    False, pending_email None), bumps ``sessions_invalidated_at``, revokes the
    refresh token, writes the self-actor audit row (DD-4), and logs the acting
    session out (a follow-up gated GET 302-redirects)."""
    client, csrf_token, user, app = login_first_user_with_register
    user_id = user.id
    refresh_token_id = _seed_refresh_token(app, user_id)
    solo_utub_id = _seed_solo_utub(app, creator_id=user_id, name="HappySoloUTub")

    with app.app_context():
        target: Users = Users.query.get(user_id)
        target.pending_email = "pending-change@example.com"
        db.session.commit()

    response = client.delete(
        url_for(ROUTES.USERS.DELETE_ACCOUNT, user_id=user_id),
        json=_delete_payload(),
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    assert response.content_type == "application/json"
    response_json = response.get_json()
    assert_response_conforms_to_schema(
        response_json,
        AccountRemovalResponseSchema,
        expected_keys={STD_JSON.STATUS, STD_JSON.MESSAGE, REDIRECT_URL},
    )
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[STD_JSON.MESSAGE] == ACCOUNT_DELETED_SUCCESS
    assert response_json[REDIRECT_URL] == url_for(ROUTES.SPLASH.SPLASH_PAGE)

    with app.app_context():
        erased: Users = Users.query.get(user_id)
        assert is_tombstoned(user=erased)
        assert erased.username == f"{TOMBSTONE_USERNAME_PREFIX}{user_id}"
        assert erased.email == (
            f"{TOMBSTONE_USERNAME_PREFIX}{user_id}@{TOMBSTONE_EMAIL_DOMAIN}"
        )
        assert erased.password is None
        assert erased.email_validated is False
        assert erased.pending_email is None
        assert erased.sessions_invalidated_at is not None
        # Solo UTub deleted outright.
        assert Utubs.query.get(solo_utub_id) is None
        # Refresh token revoked.
        revoked_token: ApiRefreshTokens = ApiRefreshTokens.query.get(refresh_token_id)
        assert revoked_token.revoked_at is not None
        # Self-actor GDPR audit trail (DD-4).
        audit_row: AuditLog | None = AuditLog.query.filter_by(
            action=ACCOUNT_AUDIT_ACTIONS.SELF_ACCOUNT_ERASE
        ).first()
        assert audit_row is not None
        assert audit_row.actor_id == user_id
        assert audit_row.target_id == str(user_id)
        assert audit_row.log_metadata is not None
        assert audit_row.log_metadata.get("utubs_deleted") == 1
        assert audit_row.log_metadata.get("api_tokens_revoked") == 1

    # The acting session was logged out and the account is tombstoned, so the
    # next gated request resolves to anonymous and redirects.
    _clear_flask_login_request_cache()
    settings_response = client.get(url_for(ROUTES.USERS.SETTINGS))
    assert settings_response.status_code == 302


# --------------------------------------------------------------------------- #
# Membership matrix (self path mirrors the admin erase suite).
# --------------------------------------------------------------------------- #


def test_delete_ownership_transferred_to_other_member(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A created UTub with another member transfers ownership to that member and
    removes the erased user's membership."""
    client, csrf_token, user, app = login_first_user_with_register
    user_id = user.id
    other_id = _seed_user(app, username="transferee", email="transferee@test.com")
    utub_id = _seed_shared_utub(
        app, creator_id=user_id, other_id=other_id, name="SharedUTub"
    )

    response = client.delete(
        url_for(ROUTES.USERS.DELETE_ACCOUNT, user_id=user_id),
        json=_delete_payload(),
        headers={"X-CSRFToken": csrf_token},
    )
    assert response.status_code == 200

    with app.app_context():
        utub_after: Utubs = Utubs.query.get(utub_id)
        assert utub_after is not None
        assert utub_after.utub_creator == other_id
        promoted: Utub_Members | None = Utub_Members.query.filter_by(
            utub_id=utub_id, user_id=other_id
        ).first()
        assert promoted is not None
        assert promoted.member_role == Member_Role.CREATOR
        assert (
            Utub_Members.query.filter_by(utub_id=utub_id, user_id=user_id).first()
            is None
        )
        audit_row: AuditLog | None = AuditLog.query.filter_by(
            action=ACCOUNT_AUDIT_ACTIONS.SELF_ACCOUNT_ERASE
        ).first()
        assert audit_row is not None
        assert audit_row.log_metadata.get("ownerships_transferred") == 1
        assert audit_row.log_metadata.get("memberships_removed") == 1


def test_delete_non_creator_membership_removed(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A non-creator membership row is removed; the UTub and its creator stay."""
    client, csrf_token, user, app = login_first_user_with_register
    user_id = user.id
    creator_id = _seed_user(app, username="realowner", email="realowner@test.com")
    utub_id = _seed_membership_in_others_utub(
        app, creator_id=creator_id, member_id=user_id, name="OthersUTub"
    )

    response = client.delete(
        url_for(ROUTES.USERS.DELETE_ACCOUNT, user_id=user_id),
        json=_delete_payload(),
        headers={"X-CSRFToken": csrf_token},
    )
    assert response.status_code == 200

    with app.app_context():
        utub_after: Utubs = Utubs.query.get(utub_id)
        assert utub_after is not None
        assert utub_after.utub_creator == creator_id
        assert (
            Utub_Members.query.filter_by(utub_id=utub_id, user_id=user_id).first()
            is None
        )
        audit_row: AuditLog | None = AuditLog.query.filter_by(
            action=ACCOUNT_AUDIT_ACTIONS.SELF_ACCOUNT_ERASE
        ).first()
        assert audit_row is not None
        assert audit_row.log_metadata.get("memberships_removed") == 1
        assert audit_row.log_metadata.get("utubs_deleted") == 0
        assert audit_row.log_metadata.get("ownerships_transferred") == 0


# --------------------------------------------------------------------------- #
# Transfer-count context correctness (DD-5).
# --------------------------------------------------------------------------- #


def test_build_account_info_context_transfer_counts_are_exact(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """``build_account_info_context`` reports the exact split of created UTubs
    that will transfer (≥1 other member) versus be deleted solo — distinct from
    the over-counting ``stats_utubs_created`` (DD-5). Seeds a mixed fixture: 2
    shared created UTubs, 1 solo created UTub, and 1 non-creator membership (which
    counts toward neither key)."""
    _, _, user, app = login_first_user_with_register
    user_id = user.id
    other_a = _seed_user(app, username="mix_a", email="mix_a@test.com")
    other_b = _seed_user(app, username="mix_b", email="mix_b@test.com")

    _seed_shared_utub(app, creator_id=user_id, other_id=other_a, name="Shared1")
    _seed_shared_utub(app, creator_id=user_id, other_id=other_b, name="Shared2")
    _seed_solo_utub(app, creator_id=user_id, name="SoloMix")
    _seed_membership_in_others_utub(
        app, creator_id=other_a, member_id=user_id, name="NonCreatorMix"
    )

    with app.test_request_context():
        login_user(Users.query.get(user_id))
        context = build_account_info_context()

    assert context["account_utubs_transferring"] == 2
    assert context["account_utubs_deleting_solo"] == 1


# --------------------------------------------------------------------------- #
# Typed-confirmation gate (DD-C).
# --------------------------------------------------------------------------- #


def test_delete_confirmation_mismatch_returns_400_no_mutation(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A ``confirmUsername`` that does not match the account username fails the
    server-side re-check → 400 with CONFIRMATION_MISMATCH and a ``confirmUsername``
    field error; the account is untouched (guard runs before any erasure)."""
    client, csrf_token, user, app = login_first_user_with_register
    user_id = user.id

    response = client.delete(
        url_for(ROUTES.USERS.DELETE_ACCOUNT, user_id=user_id),
        json=_delete_payload(confirm_username="not-my-username"),
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert (
        response_json[STD_JSON.ERROR_CODE]
        == DeleteAccountErrorCodes.CONFIRMATION_MISMATCH
    )
    assert USER_FAILURE.DELETE_CONFIRMATION_MISMATCH in (
        response_json[STD_JSON.ERRORS]["confirmUsername"]
    )

    with app.app_context():
        untouched: Users = Users.query.get(user_id)
        assert not is_tombstoned(user=untouched)
        assert untouched.email_validated is True


# --------------------------------------------------------------------------- #
# Re-auth / authorization guards.
# --------------------------------------------------------------------------- #


def test_delete_wrong_password_returns_400_field_error(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A wrong current password fails re-auth → 400 INVALID_PASSWORD with a
    ``currentPassword`` field error; no state is mutated."""
    client, csrf_token, user, app = login_first_user_with_register
    user_id = user.id

    response = client.delete(
        url_for(ROUTES.USERS.DELETE_ACCOUNT, user_id=user_id),
        json=_delete_payload(current_password=_WRONG_PASSWORD),
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert (
        response_json[STD_JSON.ERROR_CODE] == DeleteAccountErrorCodes.INVALID_PASSWORD
    )
    assert USER_FAILURE.CURRENT_PASSWORD_INCORRECT in (
        response_json[STD_JSON.ERRORS]["currentPassword"]
    )

    with app.app_context():
        assert not is_tombstoned(user=Users.query.get(user_id))


def test_delete_missing_password_returns_400_field_error(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A password account that omits ``currentPassword`` (optional so OAuth-only
    accounts can) is treated as a failed re-auth → clean 400, NOT a 500 crash on
    ``is_password_correct(None)``. No state is mutated."""
    client, csrf_token, user, app = login_first_user_with_register
    user_id = user.id

    response = client.delete(
        url_for(ROUTES.USERS.DELETE_ACCOUNT, user_id=user_id),
        json=_delete_payload(current_password=None),
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert (
        response_json[STD_JSON.ERROR_CODE] == DeleteAccountErrorCodes.INVALID_PASSWORD
    )
    with app.app_context():
        assert not is_tombstoned(user=Users.query.get(user_id))


def test_delete_self_ownership_mismatch_returns_403(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A DELETE whose URL user_id is not the acting user is rejected 403."""
    client, csrf_token, user, _ = login_first_user_with_register

    response = client.delete(
        url_for(ROUTES.USERS.DELETE_ACCOUNT, user_id=user.id + 999),
        json=_delete_payload(),
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 403


def test_delete_sole_admin_returns_403(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """The last active admin cannot delete their own account → 403 with the
    SOLE_ADMIN_CANNOT_LEAVE message; no state is mutated."""
    client, csrf_token, user, app = login_first_user_with_register
    user_id = user.id

    with app.app_context():
        admin_user: Users = Users.query.get(user_id)
        admin_user.role = User_Role.ADMIN
        db.session.commit()

    response = client.delete(
        url_for(ROUTES.USERS.DELETE_ACCOUNT, user_id=user_id),
        json=_delete_payload(),
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 403
    response_json = response.get_json()
    assert (
        response_json[STD_JSON.ERROR_CODE]
        == DeleteAccountErrorCodes.SOLE_ADMIN_FORBIDDEN
    )
    assert response_json[STD_JSON.MESSAGE] == USER_FAILURE.SOLE_ADMIN_CANNOT_LEAVE

    with app.app_context():
        assert not is_tombstoned(user=Users.query.get(user_id))


def test_delete_locks_out_after_max_reauth_failures(
    provide_redis: Redis | None,
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """``MAX_REAUTH_FAILURES`` wrong-password attempts each return 400; a further
    attempt returns 429 TOO_MANY_ATTEMPTS even with the correct password."""
    if provide_redis is None:
        pytest.skip("Requires a real Redis instance (Docker stack)")

    client, csrf_token, user, _ = login_first_user_with_register
    user_id = user.id

    for _ in range(USER_CONSTANTS.MAX_REAUTH_FAILURES):
        response = client.delete(
            url_for(ROUTES.USERS.DELETE_ACCOUNT, user_id=user_id),
            json=_delete_payload(current_password=_WRONG_PASSWORD),
            headers={"X-CSRFToken": csrf_token},
        )
        assert response.status_code == 400

    blocked = client.delete(
        url_for(ROUTES.USERS.DELETE_ACCOUNT, user_id=user_id),
        json=_delete_payload(),
        headers={"X-CSRFToken": csrf_token},
    )
    assert blocked.status_code == 429
    assert (
        blocked.get_json()[STD_JSON.ERROR_CODE]
        == DeleteAccountErrorCodes.TOO_MANY_ATTEMPTS
    )


# --------------------------------------------------------------------------- #
# ACCOUNT_DELETED domain metric.
# --------------------------------------------------------------------------- #


def test_delete_records_account_deleted_metric(
    metrics_enabled_app: Flask,
    provide_metrics_redis: Redis | None,
    register_first_user,
) -> None:
    """A successful self-delete writes exactly one ACCOUNT_DELETED counter key to
    the metrics Redis DB."""
    if provide_metrics_redis is None:
        pytest.skip("metrics Redis is unavailable in this environment")

    app = metrics_enabled_app
    app.test_client_class = AjaxFlaskLoginClient
    with app.app_context():
        target: Users = Users.query.get(1)
        user_id = target.id
        username = target.username

    assert count_counter_keys(provide_metrics_redis, EventName.ACCOUNT_DELETED) == 0

    with app.app_context():
        user_to_login: Users = Users.query.get(user_id)

    with app.test_client(user=user_to_login) as logged_in_client:
        home_response = logged_in_client.get("/home")
        csrf_token = get_csrf_token(home_response.get_data(), meta_tag=True)
        response = logged_in_client.delete(
            url_for(ROUTES.USERS.DELETE_ACCOUNT, user_id=user_id),
            json=_delete_payload(confirm_username=username),
            headers={"X-CSRFToken": csrf_token},
        )
        assert response.status_code == 200

    assert count_counter_keys(provide_metrics_redis, EventName.ACCOUNT_DELETED) == 1
