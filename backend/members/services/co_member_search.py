from __future__ import annotations

from sqlalchemy import func

from backend import db
from backend.extensions.metrics.writer import record_event
from backend.metrics.events import EventName
from backend.models.users import Users
from backend.models.utub_members import Utub_Members
from backend.models.utubs import Utubs
from backend.schemas.users import CoMemberListSchema, CoMemberSchema


def get_co_member_candidates(
    current_user_id: int, current_utub: Utubs
) -> CoMemberListSchema:
    """Return the target UTub's co-member add candidates.

    A candidate is a user who shares >=1 *other* UTub with the requester,
    excluding the requester themselves and excluding the target UTub's existing
    members. Each candidate carries ``shared_utub_count`` — the number of the
    requester's UTubs the candidate also belongs to. Ordered case-insensitively
    by username (Utub_Members has no added-at column to order by recency).

    Emits the ``MEMBER_ADD_CANDIDATES_LOADED`` domain metric.
    """
    requester_utub_ids = db.session.query(Utub_Members.utub_id).filter(
        Utub_Members.user_id == current_user_id
    )
    target_member_ids = db.session.query(Utub_Members.user_id).filter(
        Utub_Members.utub_id == current_utub.id
    )

    candidate_counts = (
        db.session.query(
            Utub_Members.user_id,
            func.count(func.distinct(Utub_Members.utub_id)).label("shared_count"),
        )
        .filter(
            Utub_Members.utub_id.in_(requester_utub_ids),
            Utub_Members.user_id != current_user_id,
            Utub_Members.user_id.notin_(target_member_ids),
        )
        .group_by(Utub_Members.user_id)
        .subquery()
    )

    rows = (
        db.session.query(Users, candidate_counts.c.shared_count)
        .join(candidate_counts, Users.id == candidate_counts.c.user_id)
        .order_by(func.lower(Users.username).asc())
        .all()
    )

    members = [
        CoMemberSchema(
            id=user.id,
            username=user.username,
            shared_utub_count=shared_count,
        )
        for user, shared_count in rows
    ]

    record_event(
        EventName.MEMBER_ADD_CANDIDATES_LOADED,
        dimensions={"has_results": "true" if members else "false"},
    )

    return CoMemberListSchema(members=members)
