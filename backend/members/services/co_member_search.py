from __future__ import annotations

from collections import defaultdict

from sqlalchemy import func
from sqlalchemy.orm import aliased

from backend import db
from backend.extensions.metrics.writer import record_event
from backend.members.member_visibility import (
    member_list_hidden_for,
    viewer_is_manager_from_role,
)
from backend.metrics.events import EventName
from backend.models.users import Users
from backend.models.utub_members import Utub_Members
from backend.models.utubs import Utubs
from backend.schemas.users import CoMemberListSchema, CoMemberSchema


def get_co_member_candidates(
    current_user_id: int, current_utub: Utubs, *, viewer_is_manager: bool | None
) -> CoMemberListSchema:
    """Return the target UTub's co-member add candidates.

    A candidate is a user who shares >=1 *other* UTub with the requester,
    excluding the requester themselves and excluding the target UTub's existing
    members. Each candidate carries ``shared_utub_count`` — the number of the
    requester's UTubs the candidate also belongs to. Ordered case-insensitively
    by username (Utub_Members has no added-at column to order by recency).
    Trashed UTubs do not count as shared.

    Hidden-list rules: when the target UTub's list is hidden from the requester
    (``viewer_is_manager`` is the decorator-resolved role, one request stale
    like the add-refusal pre-check) the result is empty. A source UTub whose
    list is hidden from the requester contributes only its owner and co-owners.

    The per-source filter runs in Python over ONE bounded query (one row per
    shared (candidate, source UTub) pair, carrying the roles and settings), so
    the statement count is independent of how many source UTubs are hidden.

    Emits the ``MEMBER_ADD_CANDIDATES_LOADED`` domain metric.
    """
    members: list[CoMemberSchema] = []

    if not member_list_hidden_for(
        settings=current_utub.settings, viewer_is_manager=viewer_is_manager
    ):
        members = _visible_candidates(current_user_id, current_utub)

    record_event(
        EventName.MEMBER_ADD_CANDIDATES_LOADED,
        dimensions={"has_results": "true" if members else "false"},
    )

    return CoMemberListSchema(members=members)


def _visible_candidates(
    current_user_id: int, current_utub: Utubs
) -> list[CoMemberSchema]:
    requester_membership = aliased(Utub_Members)
    candidate_membership = aliased(Utub_Members)
    target_member_ids = db.session.query(Utub_Members.user_id).filter(
        Utub_Members.utub_id == current_utub.id
    )

    shared_rows = (
        db.session.query(
            candidate_membership.user_id,
            candidate_membership.utub_id,
            candidate_membership.member_role,
            requester_membership.member_role,
            Utubs.settings,
        )
        .join(
            requester_membership,
            requester_membership.utub_id == candidate_membership.utub_id,
        )
        .join(Utubs, Utubs.id == candidate_membership.utub_id)
        .filter(
            requester_membership.user_id == current_user_id,
            Utubs.deleted_at.is_(None),
            candidate_membership.user_id != current_user_id,
            candidate_membership.user_id.notin_(target_member_ids),
        )
        .all()
    )

    shared_utubs_by_candidate: dict[int, set[int]] = defaultdict(set)
    for (
        candidate_id,
        source_utub_id,
        candidate_role,
        requester_role,
        source_settings,
    ) in shared_rows:
        # The requester sees the candidate in this source when they manage it,
        # its list is not hidden from them, or the candidate is its owner/co-owner.
        candidate_visible = viewer_is_manager_from_role(
            candidate_role.value
        ) is True or not member_list_hidden_for(
            settings=source_settings,
            viewer_is_manager=viewer_is_manager_from_role(requester_role.value),
        )
        if candidate_visible:
            shared_utubs_by_candidate[candidate_id].add(source_utub_id)

    if not shared_utubs_by_candidate:
        return []

    users = (
        db.session.query(Users)
        .filter(Users.id.in_(shared_utubs_by_candidate.keys()))
        .order_by(func.lower(Users.username).asc())
        .all()
    )
    return [
        CoMemberSchema(
            id=user.id,
            username=user.username,
            shared_utub_count=len(shared_utubs_by_candidate[user.id]),
        )
        for user in users
    ]
