"""Integration tests for the web-blueprint ownership-transfer endpoint:

    PATCH /utubs/<utub_id>/owner   body: {"new_owner_id": <int>}

Owner-only: reassigns ``Utubs.utub_creator`` to a chosen member, promotes them
to ``CREATOR``, and demotes the outgoing owner to ``CO_CREATOR`` (the outgoing
owner stays in the UTub — DD-3). Emits a single dimensionless
``OWNERSHIP_TRANSFERRED`` metric per successful transfer; a rejected transfer
emits nothing.

Conventions mirror test_modify_member_role_route.py (authz matrix, metric-emit
shape, locked/400/404 branches).
"""

from __future__ import annotations

from typing import Tuple

from flask import Flask, g, url_for
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
from backend.utils.strings.model_strs import MODELS as M
from backend.utils.strings.url_validation_strs import URL_VALIDATION
from backend.utils.strings.user_strs import MEMBER_FAILURE, MEMBER_SUCCESS
from backend.utils.strings.utub_strs import UTUB_FAILURE, UTUB_ID
from tests.conftest import AjaxFlaskLoginClient
from tests.integration.system.metrics_helpers import (
    count_counter_keys,
    find_counter_keys,
    parse_dims,
)
from tests.utils_for_test import get_csrf_token, set_member_role

pytestmark = pytest.mark.members

FIRST_USER_ID = 1
SECOND_USER_ID = 2
# THIRD_USER_ID and NONMEMBER_USER_ID are INTENTIONALLY the same user id (3).
# It is the same "third user" viewed under two setups: in the not-added tests
# user 3 is a non-member of the UTub (transfer target must 404), while in the
# added-member tests user 3 has been added as a plain member (transfer target
# succeeds). Keep these two constants equal — desyncing them would silently
# point the two test groups at different users and break that shared framing.
THIRD_USER_ID = 3
NONMEMBER_USER_ID = 3


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


def _clear_shared_request_caches() -> None:
    """Drop the per-request caches that leak across sequential test clients.

    The integration harness keeps ONE app context alive for the whole test, so
    request-scoped values stashed on ``g`` persist across sequential test-client
    requests and identities. Two must be cleared before each new client:

    * ``g._login_user`` — Flask-Login's per-request user cache; otherwise the
      next request reuses the earlier user instead of reloading from its own
      session cookie.
    * ``g.csrf_token`` — Flask-WTF's per-request CSRF-token cache. If left set,
      ``generate_csrf()`` short-circuits and returns the FIRST client's token
      without seeding a matching token into the NEXT client's session, so that
      client's mutating request 403s with "CSRF session token is missing".
    """
    for cached_attr in ("_login_user", "csrf_token"):
        if hasattr(g, cached_attr):
            delattr(g, cached_attr)


# ===========================================================================
# (a)/(b) Happy paths — promote a plain member / an existing co-owner
# ===========================================================================


def test_transfer_to_plain_member_as_owner(
    register_multiple_users,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """(a) Owner transfers to a plain member → 200; creator reassigns, target
    becomes CREATOR, outgoing owner becomes CO_CREATOR."""
    logged_in_client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        owner = Users.query.get(FIRST_USER_ID)
        member = Users.query.get(THIRD_USER_ID)
        utub = _make_utub(owner, "Target")
        _add_member(utub, member, Member_Role.MEMBER)
        utub_id = utub.id

    response = logged_in_client.patch(
        url_for(ROUTES.MEMBERS.TRANSFER_UTUB_OWNERSHIP, utub_id=utub_id),
        json={"new_owner_id": THIRD_USER_ID},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert body[STD_JSON.MESSAGE] == MEMBER_SUCCESS.OWNERSHIP_TRANSFERRED

    with app.app_context():
        assert Utubs.query.get(utub_id).utub_creator == THIRD_USER_ID
    assert _role_of(app, utub_id, THIRD_USER_ID) == Member_Role.CREATOR
    assert _role_of(app, utub_id, FIRST_USER_ID) == Member_Role.CO_CREATOR

    assert body[UTUB_ID] == utub_id
    assert body[M.NEW_OWNER][M.MEMBER_ROLE] == Member_Role.CREATOR.value
    assert body[M.NEW_OWNER][M.ID] == THIRD_USER_ID
    assert body[M.PREVIOUS_OWNER][M.MEMBER_ROLE] == Member_Role.CO_CREATOR.value
    assert body[M.PREVIOUS_OWNER][M.ID] == FIRST_USER_ID


def test_transfer_to_existing_co_owner_as_owner(
    register_multiple_users,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """(b) Owner transfers to an existing co-owner → 200; same three-way
    invariant (target→CREATOR, old owner→CO_CREATOR)."""
    logged_in_client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        owner = Users.query.get(FIRST_USER_ID)
        co_creator = Users.query.get(SECOND_USER_ID)
        utub = _make_utub(owner, "Target")
        _add_member(utub, co_creator, Member_Role.MEMBER)
        utub_id = utub.id

    set_member_role(app, utub_id, SECOND_USER_ID, Member_Role.CO_CREATOR)

    response = logged_in_client.patch(
        url_for(ROUTES.MEMBERS.TRANSFER_UTUB_OWNERSHIP, utub_id=utub_id),
        json={"new_owner_id": SECOND_USER_ID},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS

    with app.app_context():
        assert Utubs.query.get(utub_id).utub_creator == SECOND_USER_ID
    assert _role_of(app, utub_id, SECOND_USER_ID) == Member_Role.CREATOR
    assert _role_of(app, utub_id, FIRST_USER_ID) == Member_Role.CO_CREATOR


# ===========================================================================
# (c)/(d) Metric emission
# ===========================================================================


def test_transfer_emits_ownership_transferred_metric(
    metrics_enabled_app,
    provide_metrics_redis,
    register_multiple_users,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """(c) A successful transfer writes exactly one dimensionless
    OWNERSHIP_TRANSFERRED counter (only the auto device_type dim)."""
    logged_in_client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        owner = Users.query.get(FIRST_USER_ID)
        member = Users.query.get(THIRD_USER_ID)
        utub = _make_utub(owner, "Target")
        _add_member(utub, member, Member_Role.MEMBER)
        utub_id = utub.id

    assert (
        count_counter_keys(provide_metrics_redis, EventName.OWNERSHIP_TRANSFERRED) == 0
    )

    response = logged_in_client.patch(
        url_for(ROUTES.MEMBERS.TRANSFER_UTUB_OWNERSHIP, utub_id=utub_id),
        json={"new_owner_id": THIRD_USER_ID},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    keys = find_counter_keys(provide_metrics_redis, EventName.OWNERSHIP_TRANSFERRED)
    assert len(keys) == 1
    # Dimensionless: only the auto-injected device_type key is present.
    assert len(parse_dims(keys[0])) == 1


def test_rejected_transfer_emits_no_metric(
    metrics_enabled_app,
    provide_metrics_redis,
    register_multiple_users,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """(d) A guard-failing transfer (target not a member) leaves the
    OWNERSHIP_TRANSFERRED counter unchanged (0)."""
    logged_in_client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        owner = Users.query.get(FIRST_USER_ID)
        utub = _make_utub(owner, "Target")
        utub_id = utub.id

    before = count_counter_keys(provide_metrics_redis, EventName.OWNERSHIP_TRANSFERRED)

    response = logged_in_client.patch(
        url_for(ROUTES.MEMBERS.TRANSFER_UTUB_OWNERSHIP, utub_id=utub_id),
        json={"new_owner_id": NONMEMBER_USER_ID},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 404
    after = count_counter_keys(provide_metrics_redis, EventName.OWNERSHIP_TRANSFERRED)
    assert after == before == 0


# ===========================================================================
# (e) Authorization matrix
# ===========================================================================


def test_co_creator_actor_forbidden(
    register_multiple_users,
    login_second_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """(e) A co-creator (not the literal owner) cannot transfer ownership →
    403 NOT_AUTHORIZED, and utub_creator is unchanged."""
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
        url_for(ROUTES.MEMBERS.TRANSFER_UTUB_OWNERSHIP, utub_id=utub_id),
        json={"new_owner_id": THIRD_USER_ID},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 403
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert body[STD_JSON.MESSAGE] == UTUB_FAILURE.NOT_AUTHORIZED
    with app.app_context():
        assert Utubs.query.get(utub_id).utub_creator == FIRST_USER_ID


def test_plain_member_actor_forbidden(
    register_multiple_users,
    login_second_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """(e) A plain member cannot transfer ownership → 403."""
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
        url_for(ROUTES.MEMBERS.TRANSFER_UTUB_OWNERSHIP, utub_id=utub_id),
        json={"new_owner_id": THIRD_USER_ID},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 403
    assert response.get_json()[STD_JSON.STATUS] == STD_JSON.FAILURE
    with app.app_context():
        assert Utubs.query.get(utub_id).utub_creator == FIRST_USER_ID


def test_anonymous_is_rejected(client: FlaskClient) -> None:
    """(e) An anonymous, tokenless request cannot transfer ownership.

    PATCH is state-changing, so CSRF validation runs before the
    ``login_required`` auth redirect — an anonymous request with no CSRF token
    is blocked at the CSRF layer (403), not the 302 auth redirect a GET yields.
    """
    response = client.patch(
        "/utubs/1/owner",
        json={"new_owner_id": SECOND_USER_ID},
    )
    assert response.status_code == 403


def test_non_ajax_redirects(
    register_multiple_users,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """(e) A non-AJAX request (ajax_required=True) 302-redirects."""
    logged_in_client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        owner = Users.query.get(FIRST_USER_ID)
        member = Users.query.get(THIRD_USER_ID)
        utub = _make_utub(owner, "Target")
        _add_member(utub, member, Member_Role.MEMBER)
        utub_id = utub.id

    response = logged_in_client.patch(
        url_for(ROUTES.MEMBERS.TRANSFER_UTUB_OWNERSHIP, utub_id=utub_id),
        json={"new_owner_id": THIRD_USER_ID},
        headers={
            "X-CSRFToken": csrf_token,
            URL_VALIDATION.X_REQUESTED_WITH: "not-ajax",
        },
    )

    assert response.status_code == 302


# ===========================================================================
# (f)/(g)/(h)/(i) Target / input validation
# ===========================================================================


def test_target_not_a_member_404(
    register_multiple_users,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """(f) Transferring to a user who is not a member of the UTub → 404 with
    TARGET_NOT_A_MEMBER."""
    logged_in_client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        owner = Users.query.get(FIRST_USER_ID)
        utub = _make_utub(owner, "Target")
        utub_id = utub.id

    response = logged_in_client.patch(
        url_for(ROUTES.MEMBERS.TRANSFER_UTUB_OWNERSHIP, utub_id=utub_id),
        json={"new_owner_id": NONMEMBER_USER_ID},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 404
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert body[STD_JSON.MESSAGE] == MEMBER_FAILURE.MEMBER_NOT_IN_UTUB
    assert int(body[STD_JSON.ERROR_CODE]) == UTubMembersErrorCodes.TARGET_NOT_A_MEMBER


def test_target_already_owner_400(
    register_multiple_users,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """(g) Transferring to oneself (target already the owner) → 400 with
    TARGET_ALREADY_OWNER, and utub_creator unchanged."""
    logged_in_client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        owner = Users.query.get(FIRST_USER_ID)
        utub = _make_utub(owner, "Target")
        utub_id = utub.id

    response = logged_in_client.patch(
        url_for(ROUTES.MEMBERS.TRANSFER_UTUB_OWNERSHIP, utub_id=utub_id),
        json={"new_owner_id": FIRST_USER_ID},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert body[STD_JSON.MESSAGE] == MEMBER_FAILURE.TARGET_ALREADY_OWNER
    assert int(body[STD_JSON.ERROR_CODE]) == UTubMembersErrorCodes.TARGET_ALREADY_OWNER
    with app.app_context():
        assert Utubs.query.get(utub_id).utub_creator == FIRST_USER_ID
    assert _role_of(app, utub_id, FIRST_USER_ID) == Member_Role.CREATOR


def test_locked_utub_403(
    register_multiple_users,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """(h) A locked UTub rejects the transfer → 403 with UTUB_IS_LOCKED."""
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
        url_for(ROUTES.MEMBERS.TRANSFER_UTUB_OWNERSHIP, utub_id=utub_id),
        json={"new_owner_id": THIRD_USER_ID},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 403
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert body[STD_JSON.MESSAGE] == UTUB_FAILURE.UTUB_IS_LOCKED
    assert int(body[STD_JSON.ERROR_CODE]) == UTubMembersErrorCodes.UTUB_IS_LOCKED
    with app.app_context():
        assert Utubs.query.get(utub_id).utub_creator == FIRST_USER_ID


@pytest.mark.parametrize(
    "bad_body",
    [
        {},
        {"new_owner_id": "bogus"},
    ],
)
def test_missing_or_invalid_new_owner_id_400(
    bad_body: dict,
    register_multiple_users,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """(i) Missing or non-integer `new_owner_id` → 400 with the generic
    invalid-input envelope."""
    logged_in_client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        owner = Users.query.get(FIRST_USER_ID)
        member = Users.query.get(THIRD_USER_ID)
        utub = _make_utub(owner, "Target")
        _add_member(utub, member, Member_Role.MEMBER)
        utub_id = utub.id

    response = logged_in_client.patch(
        url_for(ROUTES.MEMBERS.TRANSFER_UTUB_OWNERSHIP, utub_id=utub_id),
        json=bad_body,
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert body[STD_JSON.MESSAGE] == MEMBER_FAILURE.UNABLE_TO_TRANSFER_OWNERSHIP
    assert int(body[STD_JSON.ERROR_CODE]) == UTubMembersErrorCodes.INVALID_FORM_INPUT
    with app.app_context():
        assert Utubs.query.get(utub_id).utub_creator == FIRST_USER_ID


# ===========================================================================
# (j)/(k) Ownership-following guards (master Phase-1-interaction note)
# ===========================================================================


def test_new_owner_can_remove_demoted_former_owner(
    register_multiple_users,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """(j) After transfer, the new owner can remove the now-demoted former owner.

    Confirms ``_someone_removing_the_owner`` keys on the reassigned
    ``utub_creator``, not the original creator: the former owner is now an
    ordinary co-owner and can be removed by the new (literal) owner.
    """
    logged_in_client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        owner = Users.query.get(FIRST_USER_ID)
        target = Users.query.get(SECOND_USER_ID)
        utub = _make_utub(owner, "Target")
        _add_member(utub, target, Member_Role.MEMBER)
        utub_id = utub.id

    transfer_response = logged_in_client.patch(
        url_for(ROUTES.MEMBERS.TRANSFER_UTUB_OWNERSHIP, utub_id=utub_id),
        json={"new_owner_id": SECOND_USER_ID},
        headers={"X-CSRFToken": csrf_token},
    )
    assert transfer_response.status_code == 200

    with app.app_context():
        new_owner_user: Users = Users.query.get(SECOND_USER_ID)

    # Act as the promoted new owner in a fresh client. The harness keeps one app
    # context alive for the whole test, so Flask-Login's cached ``g._login_user``
    # and Flask-WTF's ``g.csrf_token`` from the first client must be cleared or
    # the second client is misidentified / its CSRF token unseeded.
    app.test_client_class = AjaxFlaskLoginClient
    _clear_shared_request_caches()
    with app.test_client(user=new_owner_user) as new_owner_client:
        new_owner_csrf = get_csrf_token(
            new_owner_client.get("/home").get_data(), meta_tag=True
        )
        remove_response = new_owner_client.delete(
            url_for(
                ROUTES.MEMBERS.REMOVE_MEMBER,
                utub_id=utub_id,
                user_id=FIRST_USER_ID,
            ),
            headers={"X-CSRFToken": new_owner_csrf},
        )

    assert remove_response.status_code == 200
    with app.app_context():
        assert Utub_Members.query.get((utub_id, FIRST_USER_ID)) is None


def test_former_owner_can_no_longer_transfer(
    register_multiple_users,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """(k) After transfer, the former owner (now a co-owner) can no longer
    transfer ownership → 403 (owner-only now belongs to the new owner)."""
    logged_in_client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        owner = Users.query.get(FIRST_USER_ID)
        target = Users.query.get(SECOND_USER_ID)
        third = Users.query.get(THIRD_USER_ID)
        utub = _make_utub(owner, "Target")
        _add_member(utub, target, Member_Role.MEMBER)
        _add_member(utub, third, Member_Role.MEMBER)
        utub_id = utub.id

    transfer_response = logged_in_client.patch(
        url_for(ROUTES.MEMBERS.TRANSFER_UTUB_OWNERSHIP, utub_id=utub_id),
        json={"new_owner_id": SECOND_USER_ID},
        headers={"X-CSRFToken": csrf_token},
    )
    assert transfer_response.status_code == 200

    # The former owner (still logged in as user 1, now a CO_CREATOR) tries to
    # transfer again — the owner-only guard now belongs to the new owner.
    second_transfer = logged_in_client.patch(
        url_for(ROUTES.MEMBERS.TRANSFER_UTUB_OWNERSHIP, utub_id=utub_id),
        json={"new_owner_id": THIRD_USER_ID},
        headers={"X-CSRFToken": csrf_token},
    )

    assert second_transfer.status_code == 403
    assert second_transfer.get_json()[STD_JSON.STATUS] == STD_JSON.FAILURE
    with app.app_context():
        assert Utubs.query.get(utub_id).utub_creator == SECOND_USER_ID
