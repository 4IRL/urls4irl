import pytest
from flask import Flask
from sqlalchemy import or_, select

from backend import db
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utub_urls import Utub_Urls
from backend.urls.permissions import can_act_as_url_adder
from backend.utubs.services.trash_predicates import adder_not_member_clause

pytestmark = pytest.mark.trash

UTUB_ID = 1
ADDER_ID = 1
MANAGER_ROLES = [Member_Role.CREATOR, Member_Role.CO_CREATOR]


def _clause_allows(*, viewer_id: int) -> bool:
    """Evaluate the clause embedded in a select that joins the viewer's membership,
    the shape of ``trashed_url_rows_actionable_by``."""
    statement = (
        select(Utub_Urls.id)
        .join(
            Utub_Members,
            (Utub_Members.utub_id == Utub_Urls.utub_id)
            & (Utub_Members.user_id == viewer_id),
        )
        .where(
            Utub_Urls.utub_id == UTUB_ID,
            or_(
                Utub_Urls.user_id == viewer_id,
                Utub_Members.member_role.in_(MANAGER_ROLES),
                adder_not_member_clause(),
            ),
        )
    )
    return db.session.execute(statement).first() is not None


def _python_allows(*, viewer_id: int) -> bool:
    members = Utub_Members.query.filter_by(utub_id=UTUB_ID).all()
    roles = {member.user_id: member.member_role for member in members}
    return can_act_as_url_adder(
        adder_id=ADDER_ID,
        user_id=viewer_id,
        is_manager=roles.get(viewer_id) in MANAGER_ROLES,
        member_ids=set(roles),
    )


def _remove_member(user_id: int) -> None:
    Utub_Members.query.filter_by(utub_id=UTUB_ID, user_id=user_id).delete()
    db.session.commit()


def _make_co_creator(user_id: int) -> None:
    member = Utub_Members.query.filter_by(utub_id=UTUB_ID, user_id=user_id).one()
    member.member_role = Member_Role.CO_CREATOR
    db.session.commit()


@pytest.mark.parametrize(
    "removed_member_ids, promoted_member_ids, viewer_id, expected",
    [
        pytest.param((), (), 2, False, id="adder_member_other_plain_member"),
        pytest.param((), (), 1, True, id="adder_is_viewer"),
        pytest.param((1,), (), 2, True, id="adder_removed_viewer_member"),
        pytest.param((1, 3), (), 3, False, id="adder_removed_viewer_departed"),
        pytest.param((), (2,), 2, True, id="adder_member_viewer_manager"),
        pytest.param((1,), (2,), 2, True, id="adder_removed_viewer_manager"),
    ],
)
def test_adder_not_member_clause_matches_python_predicate(
    app: Flask,
    every_user_in_every_utub,
    add_one_url_to_each_utub_no_tags,
    removed_member_ids: tuple[int, ...],
    promoted_member_ids: tuple[int, ...],
    viewer_id: int,
    expected: bool,
) -> None:
    """
    GIVEN UTub 1 with a URL added by user 1 and members 1, 2 and 3
    WHEN the given members are removed and the given members promoted to co-creator
    THEN the SQL clause, embedded in a select joining the viewer's membership, agrees
        with can_act_as_url_adder
    """
    with app.app_context():
        assert Utub_Urls.query.filter_by(utub_id=UTUB_ID).one().user_id == ADDER_ID
        for member_id in promoted_member_ids:
            _make_co_creator(member_id)
        for member_id in removed_member_ids:
            _remove_member(member_id)

        assert _clause_allows(viewer_id=viewer_id) is expected
        assert _python_allows(viewer_id=viewer_id) is expected
