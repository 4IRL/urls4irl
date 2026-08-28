"""Integration tests for the web-blueprint grant/revoke co-owner endpoint:

    PATCH /utubs/<utub_id>/members/<user_id>

Owner-only: promotes a plain member to co-owner (``member_role`` == "cocreator")
or revokes it ("member"). Emits a single MEMBER_ROLE_CHANGED metric per real
change; a no-op (target already at the requested role) returns success without
writing or emitting.

Conventions mirror test_co_member_candidates_route.py (authz matrix) and
test_add_member_to_utub_route.py (metric-emit shape).
"""

from __future__ import annotations

from typing import Tuple

from flask import Flask, url_for
from flask.testing import FlaskClient
import pytest

from backend import db
from backend.members.constants import UTubMembersErrorCodes
from backend.metrics.events import EventName
from backend.models.users import Users
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utubs import Utubs
from backend.utils.all_routes import ROUTES
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.url_validation_strs import URL_VALIDATION
from backend.utils.strings.user_strs import MEMBER_FAILURE, MEMBER_SUCCESS
from backend.utils.strings.utub_strs import UTUB_FAILURE
from tests.integration.system.metrics_helpers import (
    count_counter_keys,
    find_counter_keys,
    parse_dims,
)

pytestmark = pytest.mark.members

FIRST_USER_ID = 1
SECOND_USER_ID = 2
THIRD_USER_ID = 3
NONEXISTENT_UTUB_ID = 9999
NONMEMBER_USER_ID = 3

_MEMBER_ROLE_FIELD = "member_role"
_ROLE_CO_CREATOR = "cocreator"
_ROLE_MEMBER = "member"


def _make_utub(creator: Users, name: str) -> Utubs:
    new_utub = Utubs(name=name, utub_creator=creator.id, utub_description="")
    db.session.add(new_utub)
    db.session.commit()

    creator_membership = Utub_Members(member_role=Member_Role.CREATOR)
    creator_membership.utub_id = new_utub.id
    creator_membership.user_id = creator.id
    db.session.add(creator_membership)
    db.session.commit()
    return new_utub


def _add_member(
    utub: Utubs, user: Users, role: Member_Role = Member_Role.MEMBER
) -> None:
    membership = Utub_Members(member_role=role)
    membership.utub_id = utub.id
    membership.user_id = user.id
    db.session.add(membership)
    db.session.commit()


def _role_of(app: Flask, utub_id: int, user_id: int) -> Member_Role:
    with app.app_context():
        member: Utub_Members = Utub_Members.query.get((utub_id, user_id))
        return member.member_role


# ===========================================================================
# Happy paths — grant / revoke (owner actor)
# ===========================================================================


def test_grant_co_creator_as_owner(
    register_multiple_users,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """Owner PATCHes a plain member to `cocreator` → 200 and the row flips to
    CO_CREATOR."""
    logged_in_client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        owner = Users.query.get(FIRST_USER_ID)
        member = Users.query.get(THIRD_USER_ID)
        utub = _make_utub(owner, "Target")
        _add_member(utub, member, Member_Role.MEMBER)
        utub_id = utub.id

    response = logged_in_client.patch(
        url_for(
            ROUTES.MEMBERS.MODIFY_MEMBER_ROLE, utub_id=utub_id, user_id=THIRD_USER_ID
        ),
        json={_MEMBER_ROLE_FIELD: _ROLE_CO_CREATOR},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert body[STD_JSON.MESSAGE] == MEMBER_SUCCESS.MEMBER_ROLE_MODIFIED
    assert _role_of(app, utub_id, THIRD_USER_ID) == Member_Role.CO_CREATOR


def test_revoke_co_creator_as_owner(
    register_multiple_users,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """Owner PATCHes a co-creator to `member` → 200 and the row flips to
    MEMBER."""
    logged_in_client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        owner = Users.query.get(FIRST_USER_ID)
        co_creator = Users.query.get(SECOND_USER_ID)
        utub = _make_utub(owner, "Target")
        _add_member(utub, co_creator, Member_Role.CO_CREATOR)
        utub_id = utub.id

    response = logged_in_client.patch(
        url_for(
            ROUTES.MEMBERS.MODIFY_MEMBER_ROLE, utub_id=utub_id, user_id=SECOND_USER_ID
        ),
        json={_MEMBER_ROLE_FIELD: _ROLE_MEMBER},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert body[STD_JSON.MESSAGE] == MEMBER_SUCCESS.MEMBER_ROLE_MODIFIED
    assert _role_of(app, utub_id, SECOND_USER_ID) == Member_Role.MEMBER


# ===========================================================================
# Metric emission — grant / revoke / no-op
# ===========================================================================


def test_grant_emits_member_role_changed_metric(
    metrics_enabled_app,
    provide_metrics_redis,
    register_multiple_users,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A grant writes exactly one MEMBER_ROLE_CHANGED counter with
    new_role=cocreator."""
    logged_in_client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        owner = Users.query.get(FIRST_USER_ID)
        member = Users.query.get(THIRD_USER_ID)
        utub = _make_utub(owner, "Target")
        _add_member(utub, member, Member_Role.MEMBER)
        utub_id = utub.id

    assert count_counter_keys(provide_metrics_redis, EventName.MEMBER_ROLE_CHANGED) == 0

    response = logged_in_client.patch(
        url_for(
            ROUTES.MEMBERS.MODIFY_MEMBER_ROLE, utub_id=utub_id, user_id=THIRD_USER_ID
        ),
        json={_MEMBER_ROLE_FIELD: _ROLE_CO_CREATOR},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    keys = find_counter_keys(provide_metrics_redis, EventName.MEMBER_ROLE_CHANGED)
    assert len(keys) == 1
    assert parse_dims(keys[0])["new_role"] == _ROLE_CO_CREATOR


def test_revoke_emits_member_role_changed_metric(
    metrics_enabled_app,
    provide_metrics_redis,
    register_multiple_users,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A revoke writes exactly one MEMBER_ROLE_CHANGED counter with
    new_role=member."""
    logged_in_client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        owner = Users.query.get(FIRST_USER_ID)
        co_creator = Users.query.get(SECOND_USER_ID)
        utub = _make_utub(owner, "Target")
        _add_member(utub, co_creator, Member_Role.CO_CREATOR)
        utub_id = utub.id

    assert count_counter_keys(provide_metrics_redis, EventName.MEMBER_ROLE_CHANGED) == 0

    response = logged_in_client.patch(
        url_for(
            ROUTES.MEMBERS.MODIFY_MEMBER_ROLE, utub_id=utub_id, user_id=SECOND_USER_ID
        ),
        json={_MEMBER_ROLE_FIELD: _ROLE_MEMBER},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    keys = find_counter_keys(provide_metrics_redis, EventName.MEMBER_ROLE_CHANGED)
    assert len(keys) == 1
    assert parse_dims(keys[0])["new_role"] == _ROLE_MEMBER


def test_noop_role_change_emits_no_metric(
    metrics_enabled_app,
    provide_metrics_redis,
    register_multiple_users,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """Owner PATCHes a member already at the requested role → 200 success with
    ZERO new MEMBER_ROLE_CHANGED counter keys (guards the no-op branch)."""
    logged_in_client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        owner = Users.query.get(FIRST_USER_ID)
        member = Users.query.get(THIRD_USER_ID)
        utub = _make_utub(owner, "Target")
        _add_member(utub, member, Member_Role.MEMBER)
        utub_id = utub.id

    before = count_counter_keys(provide_metrics_redis, EventName.MEMBER_ROLE_CHANGED)

    response = logged_in_client.patch(
        url_for(
            ROUTES.MEMBERS.MODIFY_MEMBER_ROLE, utub_id=utub_id, user_id=THIRD_USER_ID
        ),
        json={_MEMBER_ROLE_FIELD: _ROLE_MEMBER},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS
    after = count_counter_keys(provide_metrics_redis, EventName.MEMBER_ROLE_CHANGED)
    assert after == before
    # Role unchanged
    assert _role_of(app, utub_id, THIRD_USER_ID) == Member_Role.MEMBER


# ===========================================================================
# Authorization matrix
# ===========================================================================


def test_co_creator_actor_forbidden(
    register_multiple_users,
    login_second_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A co-creator (not the literal owner) is forbidden from changing roles →
    403."""
    logged_in_client, csrf_token, _, app = login_second_user_without_register

    with app.app_context():
        owner = Users.query.get(FIRST_USER_ID)
        co_creator = Users.query.get(SECOND_USER_ID)
        plain_member = Users.query.get(THIRD_USER_ID)
        utub = _make_utub(owner, "Target")
        _add_member(utub, co_creator, Member_Role.CO_CREATOR)
        _add_member(utub, plain_member, Member_Role.MEMBER)
        utub_id = utub.id

    response = logged_in_client.patch(
        url_for(
            ROUTES.MEMBERS.MODIFY_MEMBER_ROLE, utub_id=utub_id, user_id=THIRD_USER_ID
        ),
        json={_MEMBER_ROLE_FIELD: _ROLE_CO_CREATOR},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 403
    assert response.get_json()[STD_JSON.STATUS] == STD_JSON.FAILURE
    # Unchanged
    assert _role_of(app, utub_id, THIRD_USER_ID) == Member_Role.MEMBER


def test_plain_member_actor_forbidden(
    register_multiple_users,
    login_second_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A plain member is forbidden from changing roles → 403."""
    logged_in_client, csrf_token, _, app = login_second_user_without_register

    with app.app_context():
        owner = Users.query.get(FIRST_USER_ID)
        actor = Users.query.get(SECOND_USER_ID)
        other = Users.query.get(THIRD_USER_ID)
        utub = _make_utub(owner, "Target")
        _add_member(utub, actor, Member_Role.MEMBER)
        _add_member(utub, other, Member_Role.MEMBER)
        utub_id = utub.id

    response = logged_in_client.patch(
        url_for(
            ROUTES.MEMBERS.MODIFY_MEMBER_ROLE, utub_id=utub_id, user_id=THIRD_USER_ID
        ),
        json={_MEMBER_ROLE_FIELD: _ROLE_CO_CREATOR},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 403
    assert response.get_json()[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert _role_of(app, utub_id, THIRD_USER_ID) == Member_Role.MEMBER


def test_anonymous_is_rejected(client: FlaskClient) -> None:
    """An anonymous, tokenless request cannot mutate a member's role.

    PATCH is a state-changing method, so CSRF validation runs before the
    ``login_required`` auth redirect — an anonymous request with no CSRF token
    is blocked at the CSRF layer (403), not the 302 auth redirect a GET would
    yield. Either way the endpoint rejects the anonymous caller.
    """
    response = client.patch(
        "/utubs/1/members/2",
        json={_MEMBER_ROLE_FIELD: _ROLE_CO_CREATOR},
    )
    assert response.status_code == 403


def test_non_ajax_redirects(
    register_multiple_users,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A non-AJAX request (ajax_required=True) 302-redirects."""
    logged_in_client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        owner = Users.query.get(FIRST_USER_ID)
        member = Users.query.get(THIRD_USER_ID)
        utub = _make_utub(owner, "Target")
        _add_member(utub, member, Member_Role.MEMBER)
        utub_id = utub.id

    response = logged_in_client.patch(
        url_for(
            ROUTES.MEMBERS.MODIFY_MEMBER_ROLE, utub_id=utub_id, user_id=THIRD_USER_ID
        ),
        json={_MEMBER_ROLE_FIELD: _ROLE_CO_CREATOR},
        headers={
            "X-CSRFToken": csrf_token,
            URL_VALIDATION.X_REQUESTED_WITH: "not-ajax",
        },
    )

    assert response.status_code == 302


# ===========================================================================
# Target / input validation
# ===========================================================================


def test_target_not_a_member_404(
    register_multiple_users,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """Targeting a user who is not a member of the UTub → 404."""
    logged_in_client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        owner = Users.query.get(FIRST_USER_ID)
        utub = _make_utub(owner, "Target")
        utub_id = utub.id

    response = logged_in_client.patch(
        url_for(
            ROUTES.MEMBERS.MODIFY_MEMBER_ROLE,
            utub_id=utub_id,
            user_id=NONMEMBER_USER_ID,
        ),
        json={_MEMBER_ROLE_FIELD: _ROLE_CO_CREATOR},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 404
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert body[STD_JSON.MESSAGE] == MEMBER_FAILURE.MEMBER_NOT_IN_UTUB


def test_target_the_owner_400(
    register_multiple_users,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """Targeting the literal creator → 400 with CANNOT_MODIFY_OWNER error code."""
    logged_in_client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        owner = Users.query.get(FIRST_USER_ID)
        utub = _make_utub(owner, "Target")
        utub_id = utub.id

    response = logged_in_client.patch(
        url_for(
            ROUTES.MEMBERS.MODIFY_MEMBER_ROLE, utub_id=utub_id, user_id=FIRST_USER_ID
        ),
        json={_MEMBER_ROLE_FIELD: _ROLE_MEMBER},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert body[STD_JSON.MESSAGE] == MEMBER_FAILURE.CANNOT_MODIFY_OWNER_ROLE
    assert int(body[STD_JSON.ERROR_CODE]) == UTubMembersErrorCodes.CANNOT_MODIFY_OWNER
    # Owner role unchanged
    assert _role_of(app, utub_id, FIRST_USER_ID) == Member_Role.CREATOR


def test_locked_utub_403(
    register_multiple_users,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A locked UTub rejects the role change → 403 with UTUB_IS_LOCKED."""
    logged_in_client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        owner = Users.query.get(FIRST_USER_ID)
        member = Users.query.get(THIRD_USER_ID)
        utub = _make_utub(owner, "Target")
        _add_member(utub, member, Member_Role.MEMBER)
        utub.is_locked = True
        db.session.commit()
        utub_id = utub.id

    response = logged_in_client.patch(
        url_for(
            ROUTES.MEMBERS.MODIFY_MEMBER_ROLE, utub_id=utub_id, user_id=THIRD_USER_ID
        ),
        json={_MEMBER_ROLE_FIELD: _ROLE_CO_CREATOR},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 403
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert body[STD_JSON.MESSAGE] == UTUB_FAILURE.UTUB_IS_LOCKED
    assert int(body[STD_JSON.ERROR_CODE]) == UTubMembersErrorCodes.UTUB_IS_LOCKED
    assert _role_of(app, utub_id, THIRD_USER_ID) == Member_Role.MEMBER


@pytest.mark.parametrize(
    "bad_body",
    [
        {},
        {_MEMBER_ROLE_FIELD: "bogus"},
    ],
)
def test_missing_or_invalid_member_role_400(
    bad_body: dict,
    register_multiple_users,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """Missing or invalid `member_role` → 400 with the generic invalid-input
    envelope."""
    logged_in_client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        owner = Users.query.get(FIRST_USER_ID)
        member = Users.query.get(THIRD_USER_ID)
        utub = _make_utub(owner, "Target")
        _add_member(utub, member, Member_Role.MEMBER)
        utub_id = utub.id

    response = logged_in_client.patch(
        url_for(
            ROUTES.MEMBERS.MODIFY_MEMBER_ROLE, utub_id=utub_id, user_id=THIRD_USER_ID
        ),
        json=bad_body,
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert body[STD_JSON.MESSAGE] == MEMBER_FAILURE.UNABLE_TO_MODIFY_MEMBER_ROLE
    assert int(body[STD_JSON.ERROR_CODE]) == UTubMembersErrorCodes.INVALID_FORM_INPUT
    assert _role_of(app, utub_id, THIRD_USER_ID) == Member_Role.MEMBER
