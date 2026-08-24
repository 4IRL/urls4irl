from __future__ import annotations

from typing import Tuple

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient

from backend import db
from backend.metrics.events import EventName
from backend.models.users import Users
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utubs import Utubs
from backend.utils.all_routes import ROUTES
from backend.utils.strings.model_strs import MODELS as M
from tests.integration.system.metrics_helpers import (
    count_counter_keys,
    find_counter_keys,
    parse_dims,
)

pytestmark = pytest.mark.members

FIRST_USER_ID = 1
SECOND_USER_ID = 2
_HAS_RESULTS_DIM_KEY = "has_results"


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


def _add_member(utub: Utubs, user: Users) -> None:
    membership = Utub_Members()
    membership.utub_id = utub.id
    membership.user_id = user.id
    db.session.add(membership)
    db.session.commit()


def test_candidates_with_results_records_metric_has_results_true(
    metrics_enabled_app,
    provide_metrics_redis,
    register_multiple_users,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A load that surfaces >=1 candidate writes exactly one
    MEMBER_ADD_CANDIDATES_LOADED counter with has_results='true'."""
    logged_in_client, _, _, app = login_first_user_without_register

    with app.app_context():
        requester = Users.query.get(FIRST_USER_ID)
        second = Users.query.get(SECOND_USER_ID)
        target = _make_utub(requester, "Target")
        shared = _make_utub(requester, "Shared")
        _add_member(shared, second)
        target_id = target.id

    assert (
        count_counter_keys(
            provide_metrics_redis, EventName.MEMBER_ADD_CANDIDATES_LOADED
        )
        == 0
    )

    response = logged_in_client.get(
        url_for(ROUTES.MEMBERS.CO_MEMBER_CANDIDATES, utub_id=target_id)
    )

    assert response.status_code == 200
    assert len(response.get_json()[M.MEMBERS]) > 0

    counter_keys = find_counter_keys(
        provide_metrics_redis, EventName.MEMBER_ADD_CANDIDATES_LOADED
    )
    assert len(counter_keys) == 1
    assert parse_dims(counter_keys[0])[_HAS_RESULTS_DIM_KEY] == "true"


def test_candidates_with_no_results_records_metric_has_results_false(
    metrics_enabled_app,
    provide_metrics_redis,
    register_multiple_users,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A load with no candidates writes exactly one
    MEMBER_ADD_CANDIDATES_LOADED counter with has_results='false'."""
    logged_in_client, _, _, app = login_first_user_without_register

    with app.app_context():
        requester = Users.query.get(FIRST_USER_ID)
        target = _make_utub(requester, "Target")
        target_id = target.id

    assert (
        count_counter_keys(
            provide_metrics_redis, EventName.MEMBER_ADD_CANDIDATES_LOADED
        )
        == 0
    )

    response = logged_in_client.get(
        url_for(ROUTES.MEMBERS.CO_MEMBER_CANDIDATES, utub_id=target_id)
    )

    assert response.status_code == 200
    assert response.get_json()[M.MEMBERS] == []

    counter_keys = find_counter_keys(
        provide_metrics_redis, EventName.MEMBER_ADD_CANDIDATES_LOADED
    )
    assert len(counter_keys) == 1
    assert parse_dims(counter_keys[0])[_HAS_RESULTS_DIM_KEY] == "false"
