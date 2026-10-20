"""A URL whose adder was removed by an admin moderation action is actionable by every
remaining member (the orphaned-URL rule), on both branches of the member-remove action:
a non-creator member, and the creator (ownership transfer).
"""

from __future__ import annotations

from typing import Tuple

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient

from backend import db
from backend.models.urls import Urls
from backend.models.users import Users
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.utils.all_routes import ROUTES
from backend.utils.strings.url_validation_strs import URL_VALIDATION
from tests.integration.trash.trash_helpers import get_row_state, login_as_user
from tests.models_for_test import valid_url_strings

pytestmark = pytest.mark.admin

_MOD_MEMBER_REMOVE_URL: str = "/admin/utubs/{utub_id}/members/{user_id}/remove"
_MOCK_REASON: str = "integration test moderation"


def _seed_member(app: Flask, utub_id: int, username: str) -> int:
    """Create an email-validated user and add them to the UTub as a plain MEMBER."""
    with app.app_context():
        user = Users(
            username=username,
            email=f"{username}@test.com",
            plaintext_password="TestPass1!",
        )
        user.email_validated = True
        db.session.add(user)
        db.session.flush()
        db.session.add(
            Utub_Members(
                utub_id=utub_id, user_id=user.id, member_role=Member_Role.MEMBER
            )
        )
        db.session.commit()
        return user.id


def _seed_utub_with_creator(app: Flask, creator_id: int) -> int:
    with app.app_context():
        utub = Utubs(
            name="Orphan Mod UTub", utub_creator=creator_id, utub_description=""
        )
        db.session.add(utub)
        db.session.flush()
        db.session.add(
            Utub_Members(
                utub_id=utub.id, user_id=creator_id, member_role=Member_Role.CREATOR
            )
        )
        db.session.commit()
        return utub.id


def _seed_url(app: Flask, utub_id: int, adder_id: int) -> int:
    """Add a URL attributed to ``adder_id``; returns the Utub_Urls row id."""
    with app.app_context():
        url = Urls(normalized_url=valid_url_strings[0], current_user_id=adder_id)
        db.session.add(url)
        db.session.flush()
        utub_url = Utub_Urls(
            utub_id=utub_id, url_id=url.id, user_id=adder_id, url_title="Orphan me"
        )
        db.session.add(utub_url)
        db.session.commit()
        return utub_url.id


def _admin_removes_member(
    client: FlaskClient, csrf: str, utub_id: int, user_id: int
) -> None:
    response = client.post(
        _MOD_MEMBER_REMOVE_URL.format(utub_id=utub_id, user_id=user_id),
        json={"reason": _MOCK_REASON},
        headers={URL_VALIDATION.X_CSRF_TOKEN: csrf},
    )
    assert response.status_code == 200


def _assert_plain_member_can_delete(
    app: Flask, *, member_id: int, utub_id: int, row_id: int, adder_id: int
) -> None:
    with app.app_context():
        assert Utub_Members.query.get((utub_id, adder_id)) is None
        assert Utub_Members.query.get((utub_id, member_id)).member_role == (
            Member_Role.MEMBER
        )
        assert Utub_Urls.query.get(row_id).user_id == adder_id

    with login_as_user(app, member_id) as (client, csrf_token):
        response = client.delete(
            url_for(ROUTES.URLS.DELETE_URL, utub_id=utub_id, utub_url_id=row_id),
            headers={URL_VALIDATION.X_CSRF_TOKEN: csrf_token},
        )

    assert response.status_code == 200
    assert get_row_state(app, row_id)["deleted_at"] is not None


def test_admin_removes_non_creator_adder_plain_member_deletes_url(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a UTub (creator = admin) with plain members user A and user B, B added a URL
    WHEN the admin removes B (non-creator branch), then A deletes B's URL
    THEN it is 200 and the row is soft-deleted with B kept as historical adder
    """
    client, csrf, admin_user, app = login_admin_user_with_register
    utub_id = _seed_utub_with_creator(app, admin_user.id)
    plain_member_id = _seed_member(app, utub_id, "orph_plain")
    adder_id = _seed_member(app, utub_id, "orph_adder")
    row_id = _seed_url(app, utub_id, adder_id)

    _admin_removes_member(client, csrf, utub_id, adder_id)

    _assert_plain_member_can_delete(
        app,
        member_id=plain_member_id,
        utub_id=utub_id,
        row_id=row_id,
        adder_id=adder_id,
    )


def test_admin_removes_creator_plain_member_deletes_old_creators_url(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a multi-member UTub whose creator (the admin) added a URL, with plain members
        P1 (lowest id, inherits ownership) and P2
    WHEN the admin removes the creator (ownership-transfer branch), then P2 deletes it
    THEN it is 200 and the row is soft-deleted with the old creator as historical adder
    """
    client, csrf, admin_user, app = login_admin_user_with_register
    utub_id = _seed_utub_with_creator(app, admin_user.id)
    new_owner_id = _seed_member(app, utub_id, "orph_heir")
    plain_member_id = _seed_member(app, utub_id, "orph_plain2")
    row_id = _seed_url(app, utub_id, admin_user.id)

    _admin_removes_member(client, csrf, utub_id, admin_user.id)

    with app.app_context():
        assert Utubs.query.get(utub_id).utub_creator == new_owner_id
    _assert_plain_member_can_delete(
        app,
        member_id=plain_member_id,
        utub_id=utub_id,
        row_id=row_id,
        adder_id=admin_user.id,
    )
