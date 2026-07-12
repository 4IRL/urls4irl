"""Integration tests for admin content-moderation POST endpoints and the UTub lock gate.

Moderation endpoints:
    POST /admin/utubs/<int:utub_id>/lock
    POST /admin/utubs/<int:utub_id>/unlock
    POST /admin/utubs/<int:utub_id>/delete
    POST /admin/utubs/<int:utub_id>/members/<int:target_user_id>/remove
    POST /admin/utubs/<int:utub_id>/urls/<int:utub_url_id>/delete
    POST /admin/urls/<int:url_id>/purge

Lock gate:
    Locked UTub blocks add-URL, add-utub-tag, add-url-tag (single + batch),
    add-member for logged-in regular users; other operations are not blocked.
"""

from __future__ import annotations

from typing import Tuple

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient

from backend import db
from backend.models.audit_log import AuditLog
from backend.models.urls import Urls
from backend.models.users import User_Role, Users
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.utils.all_routes import ROUTES
from backend.utils.strings.admin_portal_strs import (
    ADMIN_ACTION_STRINGS,
    ADMIN_AUDIT_ACTIONS,
)
from backend.utils.strings.form_strs import ADD_USER_FORM, TAG_FORM, URL_FORM
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.utub_strs import UTUB_FAILURE
from tests.conftest import AjaxFlaskLoginClient
from tests.models_for_test import valid_url_strings
from tests.utils_for_test import get_csrf_token

pytestmark = pytest.mark.admin

# ---------------------------------------------------------------------------
# Moderation endpoint URL templates
# ---------------------------------------------------------------------------

_MOD_UTUB_LOCK_URL: str = "/admin/utubs/{utub_id}/lock"
_MOD_UTUB_UNLOCK_URL: str = "/admin/utubs/{utub_id}/unlock"
_MOD_UTUB_DELETE_URL: str = "/admin/utubs/{utub_id}/delete"
_MOD_MEMBER_REMOVE_URL: str = "/admin/utubs/{utub_id}/members/{user_id}/remove"
_MOD_URL_DELETE_URL: str = "/admin/utubs/{utub_id}/urls/{utub_url_id}/delete"
_MOD_URL_PURGE_URL: str = "/admin/urls/{url_id}/purge"
_MOD_UTUB_TAG_DELETE_URL: str = "/admin/utubs/{utub_id}/tags/{utub_tag_id}/delete"

_MOCK_REASON: str = "integration test moderation"
_OVERLONG_REASON: str = "x" * 501
_WHITESPACE_ONLY_REASON: str = "   "

# Field key for AddTagsRequest (plural camelCase, distinct from TAG_FORM.TAG_STRING)
_TAG_STRINGS_FIELD: str = "tagStrings"

# Username for the lock-gate add-member test — must be ≤ MAX_USERNAME_LENGTH (20)
_LOCK_GATE_NEW_USERNAME: str = "lockgate_tester"

# One representative URL from each moderation endpoint, used for parametrized
# auth-guard tests.
_ALL_MOD_URLS: list[str] = [
    _MOD_UTUB_LOCK_URL.format(utub_id=9999),
    _MOD_UTUB_UNLOCK_URL.format(utub_id=9999),
    _MOD_UTUB_DELETE_URL.format(utub_id=9999),
    _MOD_MEMBER_REMOVE_URL.format(utub_id=9999, user_id=9999),
    _MOD_URL_DELETE_URL.format(utub_id=9999, utub_url_id=9999),
    _MOD_URL_PURGE_URL.format(url_id=9999),
    _MOD_UTUB_TAG_DELETE_URL.format(utub_id=9999, utub_tag_id=9999),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _post_mod(
    client: FlaskClient,
    url: str,
    csrf: str,
    reason: str | None = _MOCK_REASON,
) -> object:
    """POST a moderation endpoint with an optional reason payload."""
    payload: dict = {}
    if reason is not None:
        payload["reason"] = reason
    return client.post(url, json=payload, headers={"X-CSRFToken": csrf})


def _seed_utub(app: Flask, creator_id: int) -> Utubs:
    """Create a UTub owned by creator_id, add them as CREATOR member, and commit."""
    with app.app_context():
        utub = Utubs(name="Mod Test UTub", utub_creator=creator_id, utub_description="")
        db.session.add(utub)
        db.session.flush()
        member = Utub_Members(
            utub_id=utub.id, user_id=creator_id, member_role=Member_Role.CREATOR
        )
        db.session.add(member)
        db.session.commit()
        db.session.refresh(utub)
        return utub


def _seed_url(app: Flask, utub_id: int, user_id: int) -> tuple[Urls, Utub_Urls]:
    """Create a Urls row and a Utub_Urls association, commit, and return both."""
    with app.app_context():
        url = Urls(normalized_url=valid_url_strings[0], current_user_id=user_id)
        db.session.add(url)
        db.session.flush()
        utub_url = Utub_Urls(
            utub_id=utub_id,
            url_id=url.id,
            user_id=user_id,
            url_title="Test URL",
        )
        db.session.add(utub_url)
        db.session.commit()
        db.session.refresh(url)
        db.session.refresh(utub_url)
        return url, utub_url


def _seed_utub_tag(
    app: Flask, utub_id: int, created_by: int, tag_string: str = "moderate-me"
) -> Utub_Tags:
    """Create a Utub_Tags vocabulary row for a UTub, commit, and return it."""
    with app.app_context():
        utub_tag = Utub_Tags(
            utub_id=utub_id, tag_string=tag_string, created_by=created_by
        )
        db.session.add(utub_tag)
        db.session.commit()
        db.session.refresh(utub_tag)
        return utub_tag


def _seed_url_tag(
    app: Flask, utub_id: int, utub_url_id: int, utub_tag_id: int
) -> Utub_Url_Tags:
    """Create a Utub_Url_Tags application row, commit, and return it."""
    with app.app_context():
        url_tag = Utub_Url_Tags(
            utub_id=utub_id, utub_url_id=utub_url_id, utub_tag_id=utub_tag_id
        )
        db.session.add(url_tag)
        db.session.commit()
        db.session.refresh(url_tag)
        return url_tag


def _make_admin(app: Flask, user_id: int) -> None:
    """Promote a user to User_Role.ADMIN and commit."""
    with app.app_context():
        user: Users = Users.query.get(user_id)
        user.role = User_Role.ADMIN
        db.session.commit()


def _login_user(app: Flask, user_id: int) -> tuple[FlaskClient, str]:
    """Log in a user via AjaxFlaskLoginClient and return (client, csrf)."""
    app.test_client_class = AjaxFlaskLoginClient
    with app.app_context():
        user_to_login: Users = Users.query.get(user_id)
    client = app.test_client(user=user_to_login).__enter__()
    response = client.get("/home")
    csrf = get_csrf_token(response.get_data(), meta_tag=True)
    return client, csrf


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


def test_admin_mod_lock_utub_happy_path(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin and an existing unlocked UTub
    WHEN POST /admin/utubs/<id>/lock with a reason
    THEN 200 JSON success; UTub.is_locked=True; one audit row with action=utub.lock
         and reason in metadata.
    """
    client, csrf, admin_user, app = login_admin_user_with_register
    utub = _seed_utub(app, admin_user.id)

    with app.app_context():
        rows_before = AuditLog.query.count()
    assert rows_before == 0

    response = _post_mod(client, _MOD_UTUB_LOCK_URL.format(utub_id=utub.id), csrf)

    assert response.status_code == 200
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert body[STD_JSON.MESSAGE] == ADMIN_ACTION_STRINGS.MOD_UTUB_LOCK_SUCCESS

    with app.app_context():
        refreshed_utub: Utubs = Utubs.query.get(utub.id)
        assert refreshed_utub.is_locked is True
        audit_row: AuditLog | None = AuditLog.query.first()
    assert audit_row is not None
    assert audit_row.action == ADMIN_AUDIT_ACTIONS.UTUB_LOCK
    assert audit_row.actor_id == admin_user.id
    assert audit_row.log_metadata is not None
    assert audit_row.log_metadata.get("reason") == _MOCK_REASON


def test_admin_mod_unlock_utub_happy_path(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin and a locked UTub
    WHEN POST /admin/utubs/<id>/unlock with a reason
    THEN 200 JSON success; UTub.is_locked=False; one audit row with action=utub.unlock.
    """
    client, csrf, admin_user, app = login_admin_user_with_register
    utub = _seed_utub(app, admin_user.id)

    with app.app_context():
        target_utub: Utubs = Utubs.query.get(utub.id)
        target_utub.is_locked = True
        db.session.commit()

    response = _post_mod(client, _MOD_UTUB_UNLOCK_URL.format(utub_id=utub.id), csrf)

    assert response.status_code == 200
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert body[STD_JSON.MESSAGE] == ADMIN_ACTION_STRINGS.MOD_UTUB_UNLOCK_SUCCESS

    with app.app_context():
        refreshed_utub: Utubs = Utubs.query.get(utub.id)
        assert refreshed_utub.is_locked is False
        audit_row: AuditLog | None = AuditLog.query.first()
    assert audit_row is not None
    assert audit_row.action == ADMIN_AUDIT_ACTIONS.UTUB_UNLOCK
    assert audit_row.actor_id == admin_user.id


def test_admin_mod_delete_utub_happy_path(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin and an existing UTub
    WHEN POST /admin/utubs/<id>/delete with a reason
    THEN 200 JSON success; UTub gone from DB; one audit row with utub_name in metadata.
    """
    client, csrf, admin_user, app = login_admin_user_with_register
    utub = _seed_utub(app, admin_user.id)
    utub_id = utub.id

    response = _post_mod(client, _MOD_UTUB_DELETE_URL.format(utub_id=utub_id), csrf)

    assert response.status_code == 200
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert body[STD_JSON.MESSAGE] == ADMIN_ACTION_STRINGS.MOD_UTUB_DELETE_SUCCESS

    with app.app_context():
        assert Utubs.query.get(utub_id) is None
        audit_row: AuditLog | None = AuditLog.query.first()
    assert audit_row is not None
    assert audit_row.action == ADMIN_AUDIT_ACTIONS.UTUB_DELETE
    assert audit_row.log_metadata is not None
    assert audit_row.log_metadata.get("utub_name") == utub.name
    assert audit_row.log_metadata.get("reason") == _MOCK_REASON


def test_admin_mod_remove_non_creator_member_happy_path(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin, a UTub with creator (user 1) and a non-creator member (user 2)
    WHEN POST /admin/utubs/<id>/members/<user_2_id>/remove
    THEN 200 JSON success; membership deleted; creator unchanged; one audit row.
    """
    client, csrf, admin_user, app = login_admin_user_with_register
    utub = _seed_utub(app, admin_user.id)

    with app.app_context():
        second_user = Users(
            username="mod_test_user2",
            email="mod_test_user2@test.com",
            plaintext_password="TestPass1!",
        )
        second_user.email_validated = True
        db.session.add(second_user)
        db.session.flush()
        second_user_id = second_user.id
        member = Utub_Members(
            utub_id=utub.id, user_id=second_user_id, member_role=Member_Role.MEMBER
        )
        db.session.add(member)
        db.session.commit()

    response = _post_mod(
        client,
        _MOD_MEMBER_REMOVE_URL.format(utub_id=utub.id, user_id=second_user_id),
        csrf,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert body[STD_JSON.MESSAGE] == ADMIN_ACTION_STRINGS.MOD_MEMBER_REMOVE_SUCCESS

    with app.app_context():
        remaining_utub: Utubs = Utubs.query.get(utub.id)
        assert remaining_utub is not None
        assert remaining_utub.utub_creator == admin_user.id
        assert Utub_Members.query.get((utub.id, second_user_id)) is None
        audit_row: AuditLog | None = AuditLog.query.first()
    assert audit_row is not None
    assert audit_row.action == ADMIN_AUDIT_ACTIONS.MEMBER_REMOVE
    assert audit_row.log_metadata is not None
    assert audit_row.log_metadata.get("reason") == _MOCK_REASON


def test_admin_mod_remove_creator_transfers_to_co_creator(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a UTub with creator (user 1), a CO_CREATOR (user 2), and a MEMBER (user 3)
    WHEN removing the creator via admin
    THEN UTub.utub_creator = user 2 (the lowest-id CO_CREATOR); user 2 role = CREATOR.
    """
    client, csrf, admin_user, app = login_admin_user_with_register
    utub = _seed_utub(app, admin_user.id)

    with app.app_context():
        user2 = Users(
            username="mod_co_creator",
            email="mod_co@test.com",
            plaintext_password="TestPass1!",
        )
        user2.email_validated = True
        user3 = Users(
            username="mod_member",
            email="mod_mem@test.com",
            plaintext_password="TestPass1!",
        )
        user3.email_validated = True
        db.session.add_all([user2, user3])
        db.session.flush()
        user2_id = user2.id
        user3_id = user3.id
        db.session.add(
            Utub_Members(
                utub_id=utub.id,
                user_id=user2_id,
                member_role=Member_Role.CO_CREATOR,
            )
        )
        db.session.add(
            Utub_Members(
                utub_id=utub.id,
                user_id=user3_id,
                member_role=Member_Role.MEMBER,
            )
        )
        db.session.commit()

    response = _post_mod(
        client,
        _MOD_MEMBER_REMOVE_URL.format(utub_id=utub.id, user_id=admin_user.id),
        csrf,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert (
        ADMIN_ACTION_STRINGS.MOD_MEMBER_REMOVE_TRANSFERRED.format(user_id=user2_id)
        == body[STD_JSON.MESSAGE]
    )

    with app.app_context():
        updated_utub: Utubs = Utubs.query.get(utub.id)
        assert updated_utub.utub_creator == user2_id
        new_owner_membership = Utub_Members.query.get((utub.id, user2_id))
        assert new_owner_membership.member_role == Member_Role.CREATOR
        assert Utub_Members.query.get((utub.id, admin_user.id)) is None
        audit_row: AuditLog | None = AuditLog.query.first()
    assert audit_row is not None
    assert audit_row.log_metadata.get("ownership_transferred_to") == user2_id


def test_admin_mod_remove_creator_only_members_transfers_to_lowest_member(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a UTub with creator (user 1) and one MEMBER (user 2, no CO_CREATOR)
    WHEN removing the creator via admin
    THEN ownership transfers to user 2 (lowest user_id among remaining MEMBERs).
    """
    client, csrf, admin_user, app = login_admin_user_with_register
    utub = _seed_utub(app, admin_user.id)

    with app.app_context():
        user2 = Users(
            username="mod_only_member",
            email="mod_only_member@test.com",
            plaintext_password="TestPass1!",
        )
        user2.email_validated = True
        db.session.add(user2)
        db.session.flush()
        user2_id = user2.id
        db.session.add(
            Utub_Members(
                utub_id=utub.id,
                user_id=user2_id,
                member_role=Member_Role.MEMBER,
            )
        )
        db.session.commit()

    response = _post_mod(
        client,
        _MOD_MEMBER_REMOVE_URL.format(utub_id=utub.id, user_id=admin_user.id),
        csrf,
    )

    assert response.status_code == 200
    with app.app_context():
        updated_utub: Utubs = Utubs.query.get(utub.id)
        assert updated_utub.utub_creator == user2_id
        new_owner_membership = Utub_Members.query.get((utub.id, user2_id))
        assert new_owner_membership.member_role == Member_Role.CREATOR


def test_admin_mod_remove_sole_creator_deletes_utub(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a UTub with only the creator as its sole member
    WHEN removing the creator via admin
    THEN the whole UTub is deleted; audit log has utub_deleted=True.
    """
    client, csrf, admin_user, app = login_admin_user_with_register
    utub = _seed_utub(app, admin_user.id)
    utub_id = utub.id

    response = _post_mod(
        client,
        _MOD_MEMBER_REMOVE_URL.format(utub_id=utub_id, user_id=admin_user.id),
        csrf,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body[STD_JSON.MESSAGE] == ADMIN_ACTION_STRINGS.MOD_MEMBER_REMOVE_UTUB_DELETED

    with app.app_context():
        assert Utubs.query.get(utub_id) is None
        audit_row: AuditLog | None = AuditLog.query.first()
    assert audit_row is not None
    assert audit_row.log_metadata.get("utub_deleted") is True


def test_admin_mod_delete_url_in_utub_happy_path(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a UTub with one URL and no tags on it
    WHEN POST /admin/utubs/<id>/urls/<utub_url_id>/delete
    THEN 200 JSON success; Utub_Urls row gone; Urls row preserved; audit row.
    """
    client, csrf, admin_user, app = login_admin_user_with_register
    utub = _seed_utub(app, admin_user.id)
    url, utub_url = _seed_url(app, utub.id, admin_user.id)
    url_id = url.id
    utub_url_id = utub_url.id

    response = _post_mod(
        client,
        _MOD_URL_DELETE_URL.format(utub_id=utub.id, utub_url_id=utub_url_id),
        csrf,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert body[STD_JSON.MESSAGE] == ADMIN_ACTION_STRINGS.MOD_URL_DELETE_SUCCESS

    with app.app_context():
        assert Utub_Urls.query.get(utub_url_id) is None
        # Urls row is preserved
        assert Urls.query.get(url_id) is not None
        audit_row: AuditLog | None = AuditLog.query.first()
    assert audit_row is not None
    assert audit_row.action == ADMIN_AUDIT_ACTIONS.URL_DELETE
    assert audit_row.log_metadata.get("url_id") == url_id


def test_admin_mod_delete_url_in_utub_keeps_other_utub_association(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a URL present in two UTubs
    WHEN deleting it from the first UTub via admin
    THEN the second UTub's association is preserved.
    """
    client, csrf, admin_user, app = login_admin_user_with_register
    utub_a = _seed_utub(app, admin_user.id)
    utub_b = _seed_utub(app, admin_user.id)
    url, utub_url_a = _seed_url(app, utub_a.id, admin_user.id)
    url_id = url.id
    utub_url_a_id = utub_url_a.id

    with app.app_context():
        utub_url_b = Utub_Urls(
            utub_id=utub_b.id, url_id=url_id, user_id=admin_user.id, url_title=""
        )
        db.session.add(utub_url_b)
        db.session.commit()
        utub_url_b_id = utub_url_b.id

    response = _post_mod(
        client,
        _MOD_URL_DELETE_URL.format(utub_id=utub_a.id, utub_url_id=utub_url_a_id),
        csrf,
    )

    assert response.status_code == 200
    with app.app_context():
        assert Utub_Urls.query.get(utub_url_a_id) is None
        assert Utub_Urls.query.get(utub_url_b_id) is not None
        assert Urls.query.get(url_id) is not None


def test_admin_mod_purge_url_globally_happy_path(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a URL in two UTubs
    WHEN POST /admin/urls/<url_id>/purge
    THEN 200 JSON with count=2; all Utub_Urls associations removed; Urls row preserved.
    """
    client, csrf, admin_user, app = login_admin_user_with_register
    utub_a = _seed_utub(app, admin_user.id)
    utub_b = _seed_utub(app, admin_user.id)
    url, utub_url_a = _seed_url(app, utub_a.id, admin_user.id)
    url_id = url.id
    utub_url_a_id = utub_url_a.id

    with app.app_context():
        utub_url_b = Utub_Urls(
            utub_id=utub_b.id, url_id=url_id, user_id=admin_user.id, url_title=""
        )
        db.session.add(utub_url_b)
        db.session.commit()
        utub_url_b_id = utub_url_b.id

    response = _post_mod(
        client,
        _MOD_URL_PURGE_URL.format(url_id=url_id),
        csrf,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert body["count"] == 2
    assert body[STD_JSON.MESSAGE] == ADMIN_ACTION_STRINGS.MOD_URL_PURGE_SUCCESS.format(
        count=2
    )

    with app.app_context():
        assert Utub_Urls.query.get(utub_url_a_id) is None
        assert Utub_Urls.query.get(utub_url_b_id) is None
        # Urls row is intentionally preserved
        assert Urls.query.get(url_id) is not None
        audit_row: AuditLog | None = AuditLog.query.first()
    assert audit_row is not None
    assert audit_row.action == ADMIN_AUDIT_ACTIONS.URL_PURGE
    assert audit_row.log_metadata.get("utub_count") == 2
    assert audit_row.log_metadata.get("reason") == _MOCK_REASON


def test_admin_mod_purge_url_zero_utubs(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a Urls row with zero UTub associations
    WHEN POST /admin/urls/<url_id>/purge
    THEN 200 JSON with count=0 and an audit row (URL confirmed present, no-op is valid).
    """
    client, csrf, admin_user, app = login_admin_user_with_register

    with app.app_context():
        url = Urls(normalized_url=valid_url_strings[0], current_user_id=admin_user.id)
        db.session.add(url)
        db.session.commit()
        url_id = url.id

    response = _post_mod(client, _MOD_URL_PURGE_URL.format(url_id=url_id), csrf)

    assert response.status_code == 200
    body = response.get_json()
    assert body["count"] == 0
    with app.app_context():
        assert Urls.query.get(url_id) is not None
        assert AuditLog.query.count() == 1


def test_admin_mod_utub_tag_delete_happy_path(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a UTub tag applied to two URLs
    WHEN POST /admin/utubs/<id>/tags/<utub_tag_id>/delete
    THEN 200 JSON with count=2; the Utub_Tags row and ALL its Utub_Url_Tags
         cascade-removed; one audit row with associations_removed=2.
    """
    client, csrf, admin_user, app = login_admin_user_with_register
    utub = _seed_utub(app, admin_user.id)
    _, utub_url_one = _seed_url(app, utub.id, admin_user.id)
    # Second URL must use a distinct url string (Urls.urlString is unique).
    with app.app_context():
        second_url = Urls(
            normalized_url=valid_url_strings[1], current_user_id=admin_user.id
        )
        db.session.add(second_url)
        db.session.flush()
        second_utub_url = Utub_Urls(
            utub_id=utub.id,
            url_id=second_url.id,
            user_id=admin_user.id,
            url_title="Second URL",
        )
        db.session.add(second_utub_url)
        db.session.commit()
        second_utub_url_id = second_utub_url.id
    utub_tag = _seed_utub_tag(app, utub.id, admin_user.id)
    utub_tag_id = utub_tag.id
    url_tag_one = _seed_url_tag(app, utub.id, utub_url_one.id, utub_tag_id)
    url_tag_two = _seed_url_tag(app, utub.id, second_utub_url_id, utub_tag_id)
    url_tag_one_id = url_tag_one.id
    url_tag_two_id = url_tag_two.id

    with app.app_context():
        assert AuditLog.query.count() == 0
        assert Utub_Url_Tags.query.get(url_tag_one_id) is not None
        assert Utub_Url_Tags.query.get(url_tag_two_id) is not None

    response = _post_mod(
        client,
        _MOD_UTUB_TAG_DELETE_URL.format(utub_id=utub.id, utub_tag_id=utub_tag_id),
        csrf,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert body["count"] == 2
    assert body[
        STD_JSON.MESSAGE
    ] == ADMIN_ACTION_STRINGS.MOD_UTUB_TAG_DELETE_SUCCESS.format(count=2)

    with app.app_context():
        assert Utub_Tags.query.get(utub_tag_id) is None
        assert Utub_Url_Tags.query.get(url_tag_one_id) is None
        assert Utub_Url_Tags.query.get(url_tag_two_id) is None
        assert AuditLog.query.count() == 1
        audit_row: AuditLog | None = AuditLog.query.first()
    assert audit_row is not None
    assert audit_row.action == ADMIN_AUDIT_ACTIONS.UTUB_TAG_DELETE
    assert audit_row.log_metadata is not None
    assert audit_row.log_metadata.get("associations_removed") == 2
    assert audit_row.log_metadata.get("reason") == _MOCK_REASON


def test_admin_mod_utub_tag_delete_zero_associations(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a UTub tag applied to no URLs
    WHEN POST /admin/utubs/<id>/tags/<utub_tag_id>/delete
    THEN 200 JSON with count=0; the Utub_Tags row is gone; one audit row.
    """
    client, csrf, admin_user, app = login_admin_user_with_register
    utub = _seed_utub(app, admin_user.id)
    utub_tag = _seed_utub_tag(app, utub.id, admin_user.id)
    utub_tag_id = utub_tag.id

    response = _post_mod(
        client,
        _MOD_UTUB_TAG_DELETE_URL.format(utub_id=utub.id, utub_tag_id=utub_tag_id),
        csrf,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["count"] == 0
    with app.app_context():
        assert Utub_Tags.query.get(utub_tag_id) is None
        assert AuditLog.query.count() == 1


def test_admin_mod_utub_tag_delete_mismatched_utub_returns_404(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a UTub tag owned by one UTub
    WHEN POSTing utub-tag-delete with a valid tag id but a DIFFERENT utub_id
    THEN 404 and the tag survives untouched.
    """
    client, csrf, admin_user, app = login_admin_user_with_register
    owning_utub = _seed_utub(app, admin_user.id)
    other_utub = _seed_utub(app, admin_user.id)
    utub_tag = _seed_utub_tag(app, owning_utub.id, admin_user.id)
    utub_tag_id = utub_tag.id

    response = _post_mod(
        client,
        _MOD_UTUB_TAG_DELETE_URL.format(utub_id=other_utub.id, utub_tag_id=utub_tag_id),
        csrf,
    )

    assert response.status_code == 404
    with app.app_context():
        assert Utub_Tags.query.get(utub_tag_id) is not None
        assert AuditLog.query.count() == 0


# ---------------------------------------------------------------------------
# 404 tests for missing targets
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        _MOD_UTUB_LOCK_URL.format(utub_id=99999),
        _MOD_UTUB_UNLOCK_URL.format(utub_id=99999),
        _MOD_UTUB_DELETE_URL.format(utub_id=99999),
        _MOD_MEMBER_REMOVE_URL.format(utub_id=99999, user_id=99999),
        _MOD_URL_DELETE_URL.format(utub_id=99999, utub_url_id=99999),
        _MOD_URL_PURGE_URL.format(url_id=99999),
        _MOD_UTUB_TAG_DELETE_URL.format(utub_id=99999, utub_tag_id=99999),
    ],
)
def test_admin_mod_missing_target_returns_404(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    url: str,
) -> None:
    """
    GIVEN a logged-in admin and a non-existent target ID
    WHEN POSTing any moderation endpoint with that ID
    THEN 404 JSON is returned and no audit row is written.
    """
    client, csrf, _, app = login_admin_user_with_register

    response = _post_mod(client, url, csrf)

    assert response.status_code == 404
    with app.app_context():
        assert AuditLog.query.count() == 0


# ---------------------------------------------------------------------------
# Auth guard tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mod_url", _ALL_MOD_URLS)
def test_admin_mod_non_admin_returns_404(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    mod_url: str,
) -> None:
    """
    GIVEN a logged-in non-admin user
    WHEN POSTing any moderation endpoint
    THEN 404 JSON (admin_required hides the admin surface from non-admins).
    """
    client, csrf, _, _ = login_first_user_with_register

    response = _post_mod(client, mod_url, csrf)

    assert response.status_code == 404


@pytest.mark.parametrize("mod_url", _ALL_MOD_URLS)
def test_admin_mod_anonymous_returns_401(
    client: FlaskClient,
    mod_url: str,
) -> None:
    """
    GIVEN an unauthenticated (anonymous) session
    WHEN POSTing any moderation endpoint with a valid CSRF token
    THEN 401 JSON.
    """
    splash_response = client.get("/")
    csrf_token = get_csrf_token(splash_response.get_data(), meta_tag=True)

    response = client.post(
        mod_url, json={"reason": _MOCK_REASON}, headers={"X-CSRFToken": csrf_token}
    )

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Required-reason schema validation tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        _MOD_UTUB_LOCK_URL.format(utub_id=99999),
        _MOD_UTUB_UNLOCK_URL.format(utub_id=99999),
        _MOD_UTUB_DELETE_URL.format(utub_id=99999),
        _MOD_MEMBER_REMOVE_URL.format(utub_id=99999, user_id=99999),
        _MOD_URL_DELETE_URL.format(utub_id=99999, utub_url_id=99999),
        _MOD_URL_PURGE_URL.format(url_id=99999),
        _MOD_UTUB_TAG_DELETE_URL.format(utub_id=99999, utub_tag_id=99999),
    ],
)
def test_admin_mod_missing_reason_returns_400(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    url: str,
) -> None:
    """
    GIVEN a logged-in admin sending no reason field
    WHEN POSTing a moderation endpoint
    THEN 400 JSON (AdminReasonRequiredRequest rejects missing reason).
    """
    client, csrf, _, _ = login_admin_user_with_register

    response = _post_mod(client, url, csrf, reason=None)

    assert response.status_code == 400


@pytest.mark.parametrize(
    "url",
    [
        _MOD_UTUB_LOCK_URL.format(utub_id=99999),
        _MOD_UTUB_UNLOCK_URL.format(utub_id=99999),
        _MOD_UTUB_DELETE_URL.format(utub_id=99999),
        _MOD_MEMBER_REMOVE_URL.format(utub_id=99999, user_id=99999),
        _MOD_URL_DELETE_URL.format(utub_id=99999, utub_url_id=99999),
        _MOD_URL_PURGE_URL.format(url_id=99999),
        _MOD_UTUB_TAG_DELETE_URL.format(utub_id=99999, utub_tag_id=99999),
    ],
)
def test_admin_mod_whitespace_only_reason_returns_400(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    url: str,
) -> None:
    """
    GIVEN a logged-in admin sending a whitespace-only reason
    WHEN POSTing a moderation endpoint
    THEN 400 JSON (AdminReasonRequiredRequest rejects whitespace-only strings).
    """
    client, csrf, _, _ = login_admin_user_with_register

    response = _post_mod(client, url, csrf, reason=_WHITESPACE_ONLY_REASON)

    assert response.status_code == 400


@pytest.mark.parametrize(
    "url",
    [
        _MOD_UTUB_LOCK_URL.format(utub_id=99999),
        _MOD_UTUB_UNLOCK_URL.format(utub_id=99999),
        _MOD_UTUB_DELETE_URL.format(utub_id=99999),
        _MOD_MEMBER_REMOVE_URL.format(utub_id=99999, user_id=99999),
        _MOD_URL_DELETE_URL.format(utub_id=99999, utub_url_id=99999),
        _MOD_URL_PURGE_URL.format(url_id=99999),
        _MOD_UTUB_TAG_DELETE_URL.format(utub_id=99999, utub_tag_id=99999),
    ],
)
def test_admin_mod_overlong_reason_returns_400(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    url: str,
) -> None:
    """
    GIVEN a logged-in admin sending a 501-character reason
    WHEN POSTing a moderation endpoint
    THEN 400 JSON (field_validator rejects over-length reasons).
    """
    client, csrf, _, _ = login_admin_user_with_register

    response = _post_mod(client, url, csrf, reason=_OVERLONG_REASON)

    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Idempotent no-op tests for lock/unlock
# ---------------------------------------------------------------------------


def test_admin_mod_lock_already_locked_utub_is_noop(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a UTub that is already locked
    WHEN POST /admin/utubs/<id>/lock
    THEN 200 no-op message; is_locked remains True; NO audit row is written.
    """
    client, csrf, admin_user, app = login_admin_user_with_register
    utub = _seed_utub(app, admin_user.id)

    with app.app_context():
        target_utub: Utubs = Utubs.query.get(utub.id)
        target_utub.is_locked = True
        db.session.commit()

    response = _post_mod(client, _MOD_UTUB_LOCK_URL.format(utub_id=utub.id), csrf)

    assert response.status_code == 200
    body = response.get_json()
    assert body[STD_JSON.MESSAGE] == ADMIN_ACTION_STRINGS.MOD_UTUB_LOCK_NOOP
    with app.app_context():
        assert AuditLog.query.count() == 0
        assert Utubs.query.get(utub.id).is_locked is True


def test_admin_mod_unlock_already_unlocked_utub_is_noop(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a UTub that is already unlocked (default state)
    WHEN POST /admin/utubs/<id>/unlock
    THEN 200 no-op message; is_locked remains False; NO audit row is written.
    """
    client, csrf, admin_user, app = login_admin_user_with_register
    utub = _seed_utub(app, admin_user.id)

    response = _post_mod(client, _MOD_UTUB_UNLOCK_URL.format(utub_id=utub.id), csrf)

    assert response.status_code == 200
    body = response.get_json()
    assert body[STD_JSON.MESSAGE] == ADMIN_ACTION_STRINGS.MOD_UTUB_UNLOCK_NOOP
    with app.app_context():
        assert AuditLog.query.count() == 0
        assert Utubs.query.get(utub.id).is_locked is False


# ---------------------------------------------------------------------------
# Lock gate tests: locked UTub blocks content writes, not reads/deletes
# ---------------------------------------------------------------------------


def test_lock_gate_blocks_add_url_to_locked_utub(
    add_multiple_users_to_utub_without_logging_in: None,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a locked UTub that the logged-in user is a creator of
    WHEN the user POSTs to add a URL
    THEN 403 with UTUB_IS_LOCKED message.
    """
    client, csrf, user, app = login_first_user_without_register

    with app.app_context():
        utub: Utubs = Utubs.query.filter_by(utub_creator=user.id).first()
        utub.is_locked = True
        db.session.commit()
        utub_id = utub.id

    with app.app_context():
        add_url_path = url_for(ROUTES.URLS.CREATE_URL, utub_id=utub_id)

    response = client.post(
        add_url_path,
        json={URL_FORM.URL_STRING: valid_url_strings[0], URL_FORM.URL_TITLE: "Test"},
        headers={"X-CSRFToken": csrf},
    )

    assert response.status_code == 403
    body = response.get_json()
    assert body[STD_JSON.MESSAGE] == UTUB_FAILURE.UTUB_IS_LOCKED


def test_lock_gate_blocks_add_utub_tag_to_locked_utub(
    add_multiple_users_to_utub_without_logging_in: None,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a locked UTub that the logged-in user is a creator of
    WHEN the user POSTs to add a UTub tag
    THEN 403 with UTUB_IS_LOCKED message.
    """
    client, csrf, user, app = login_first_user_without_register

    with app.app_context():
        utub: Utubs = Utubs.query.filter_by(utub_creator=user.id).first()
        utub.is_locked = True
        db.session.commit()
        utub_id = utub.id

    with app.app_context():
        add_tag_path = url_for(ROUTES.UTUB_TAGS.CREATE_UTUB_TAG, utub_id=utub_id)

    response = client.post(
        add_tag_path,
        json={TAG_FORM.TAG_STRING: "test-tag"},
        headers={"X-CSRFToken": csrf},
    )

    assert response.status_code == 403
    body = response.get_json()
    assert body[STD_JSON.MESSAGE] == UTUB_FAILURE.UTUB_IS_LOCKED


def test_lock_gate_blocks_add_url_tag_to_locked_utub(
    add_one_url_to_each_utub_no_tags: None,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a locked UTub with a URL, logged-in as the creator
    WHEN the user POSTs to add a single URL tag
    THEN 403 with UTUB_IS_LOCKED message.
    """
    client, csrf, user, app = login_first_user_without_register

    with app.app_context():
        utub: Utubs = Utubs.query.filter_by(utub_creator=user.id).first()
        utub.is_locked = True
        db.session.commit()
        utub_id = utub.id
        utub_url: Utub_Urls = Utub_Urls.query.filter_by(utub_id=utub_id).first()
        utub_url_id = utub_url.id

    with app.app_context():
        add_url_tag_path = url_for(
            ROUTES.URL_TAGS.CREATE_URL_TAG, utub_id=utub_id, utub_url_id=utub_url_id
        )

    response = client.post(
        add_url_tag_path,
        json={TAG_FORM.TAG_STRING: "test-tag"},
        headers={"X-CSRFToken": csrf},
    )

    assert response.status_code == 403
    body = response.get_json()
    assert body[STD_JSON.MESSAGE] == UTUB_FAILURE.UTUB_IS_LOCKED


def test_lock_gate_blocks_batch_add_url_tags_to_locked_utub(
    add_one_url_to_each_utub_no_tags: None,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a locked UTub with a URL, logged-in as the creator
    WHEN the user POSTs to batch-add URL tags
    THEN 403 with UTUB_IS_LOCKED message.
    """
    client, csrf, user, app = login_first_user_without_register

    with app.app_context():
        utub: Utubs = Utubs.query.filter_by(utub_creator=user.id).first()
        utub.is_locked = True
        db.session.commit()
        utub_id = utub.id
        utub_url: Utub_Urls = Utub_Urls.query.filter_by(utub_id=utub_id).first()
        utub_url_id = utub_url.id

    with app.app_context():
        batch_path = url_for(
            ROUTES.URL_TAGS.BATCH_ADD_URL_TAGS, utub_id=utub_id, utub_url_id=utub_url_id
        )

    response = client.post(
        batch_path,
        json={_TAG_STRINGS_FIELD: ["tag1", "tag2"]},
        headers={"X-CSRFToken": csrf},
    )

    assert response.status_code == 403
    body = response.get_json()
    assert body[STD_JSON.MESSAGE] == UTUB_FAILURE.UTUB_IS_LOCKED


def test_lock_gate_blocks_add_member_to_locked_utub(
    add_multiple_users_to_utub_without_logging_in: None,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a locked UTub, logged-in as creator, and a fourth user not in the UTub
    WHEN the creator tries to add the fourth user as a member
    THEN 403 with UTUB_IS_LOCKED message.
    """
    client, csrf, user, app = login_first_user_without_register

    with app.app_context():
        utub: Utubs = Utubs.query.filter_by(utub_creator=user.id).first()
        utub.is_locked = True
        db.session.commit()
        utub_id = utub.id
        fourth_user = Users(
            username=_LOCK_GATE_NEW_USERNAME,
            email="fourth_lock@test.com",
            plaintext_password="TestPass1!",
        )
        fourth_user.email_validated = True
        db.session.add(fourth_user)
        db.session.commit()
        fourth_username = fourth_user.username

    with app.app_context():
        add_member_path = url_for(ROUTES.MEMBERS.CREATE_MEMBER, utub_id=utub_id)

    response = client.post(
        add_member_path,
        json={ADD_USER_FORM.USERNAME: fourth_username},
        headers={"X-CSRFToken": csrf},
    )

    assert response.status_code == 403
    body = response.get_json()
    assert body[STD_JSON.MESSAGE] == UTUB_FAILURE.UTUB_IS_LOCKED


def test_lock_gate_allows_member_to_leave_locked_utub(
    add_multiple_users_to_utub_without_logging_in: None,
    login_second_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a locked UTub the logged-in user is a non-creator member of
    WHEN the user removes themselves (leaves the UTub)
    THEN the leave succeeds (200) — lock freezes new content only, never
         a member's ability to leave.
    """
    client, csrf, member_user, app = login_second_user_without_register

    with app.app_context():
        utub: Utubs = Utubs.query.first()
        utub.is_locked = True
        db.session.commit()
        utub_id = utub.id
        membership_before: Utub_Members | None = Utub_Members.query.get(
            (utub_id, member_user.id)
        )
        assert membership_before is not None

    with app.app_context():
        leave_path = url_for(
            ROUTES.MEMBERS.REMOVE_MEMBER, utub_id=utub_id, user_id=member_user.id
        )

    response = client.delete(leave_path, headers={"X-CSRFToken": csrf})

    assert response.status_code == 200
    with app.app_context():
        membership_after: Utub_Members | None = Utub_Members.query.get(
            (utub_id, member_user.id)
        )
    assert membership_after is None


def test_lock_gate_allows_creator_to_delete_locked_utub(
    add_multiple_users_to_utub_without_logging_in: None,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a locked UTub the logged-in user created
    WHEN the creator deletes the UTub
    THEN the delete succeeds (200) — lock freezes new content only, never
         the creator's ability to delete their UTub.
    """
    client, csrf, creator_user, app = login_first_user_without_register

    with app.app_context():
        utub: Utubs = Utubs.query.filter_by(utub_creator=creator_user.id).first()
        utub.is_locked = True
        db.session.commit()
        utub_id = utub.id

    with app.app_context():
        delete_path = url_for(ROUTES.UTUBS.DELETE_UTUB, utub_id=utub_id)

    response = client.delete(delete_path, headers={"X-CSRFToken": csrf})

    assert response.status_code == 200
    with app.app_context():
        assert Utubs.query.get(utub_id) is None


def test_admin_mod_url_delete_mismatched_utub_returns_404(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a Utub_Urls row that belongs to one UTub
    WHEN POSTing the admin URL delete with a valid utub_url_id but a
         DIFFERENT utub_id
    THEN 404 — the cross-UTub guard requires both ids to match — and the
         association row survives untouched.
    """
    client, csrf, admin_user, app = login_admin_user_with_register
    owning_utub = _seed_utub(app, admin_user.id)
    other_utub = _seed_utub(app, admin_user.id)
    _, utub_url = _seed_url(app, owning_utub.id, admin_user.id)
    utub_url_id = utub_url.id

    response = _post_mod(
        client,
        _MOD_URL_DELETE_URL.format(utub_id=other_utub.id, utub_url_id=utub_url_id),
        csrf,
    )

    assert response.status_code == 404
    with app.app_context():
        assert Utub_Urls.query.get(utub_url_id) is not None
