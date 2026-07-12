"""Admin content-moderation service: audited, admin-gated mutation functions.

Each function:
  - accepts keyword-only args, carries full typehints, returns FlaskResponse
  - audits exactly once per successful state-changing action
  - lands the mutation and audit row in a single db.session.commit()
  - returns 404 via build_message_error_response when the target does not exist
  - no-ops idempotent state actions with a clear 200 message and no audit row
"""

from __future__ import annotations

from backend import db
from backend.admin.constants import AdminActionErrorCodes
from backend.api_common.responses import FlaskResponse
from backend.extensions import audit
from backend.models.urls import Urls
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.schemas.admin_actions import AdminActionResponseSchema
from backend.schemas.errors import build_message_error_response
from backend.utils.strings.admin_portal_strs import (
    ADMIN_ACTION_STRINGS,
    ADMIN_AUDIT_ACTIONS,
)
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON


def select_ownership_transfer_target(
    *, other_members: list[Utub_Members]
) -> Utub_Members:
    """Pick the deterministic new owner for a UTub whose creator is departing.

    Prefers the CO_CREATOR with the lowest user id; falls back to the lowest
    user id among all remaining members. Shared by admin member removal and
    account erasure so both resolve creator departure identically.

    Args:
        other_members: Remaining memberships, excluding the departing creator.
            Must be non-empty.

    Returns:
        The membership row of the chosen new owner.
    """
    co_creators: list[Utub_Members] = [
        member
        for member in other_members
        if member.member_role == Member_Role.CO_CREATOR
    ]
    if co_creators:
        return min(co_creators, key=lambda member: member.user_id)
    return min(other_members, key=lambda member: member.user_id)


def lock_utub(*, actor_id: int, utub_id: int, reason: str) -> FlaskResponse:
    """Lock a UTub, preventing new content from being added.

    Idempotent: if the UTub is already locked, returns a clear no-op 200
    with no audit row. Otherwise sets ``is_locked=True``, audits, and commits.

    Args:
        actor_id: ID of the admin user performing the action.
        utub_id: Primary key of the UTub to lock.
        reason: Required human-readable reason recorded in the audit log.

    Returns:
        200 JSON envelope on success or no-op.
        404 when the UTub does not exist.
    """
    utub: Utubs | None = Utubs.query.get(utub_id)
    if utub is None:
        return build_message_error_response(
            message=ADMIN_ACTION_STRINGS.MOD_TARGET_NOT_FOUND,
            error_code=AdminActionErrorCodes.TARGET_NOT_FOUND,
            status_code=404,
        )
    if utub.is_locked:
        return AdminActionResponseSchema(
            status=STD_JSON.SUCCESS,
            message=ADMIN_ACTION_STRINGS.MOD_UTUB_LOCK_NOOP,
        ).to_response()

    utub.is_locked = True
    audit.record(
        actor_id=actor_id,
        action=ADMIN_AUDIT_ACTIONS.UTUB_LOCK,
        target_type="Utub",
        target_id=str(utub_id),
        metadata={"reason": reason},
    )
    db.session.commit()
    return AdminActionResponseSchema(
        status=STD_JSON.SUCCESS,
        message=ADMIN_ACTION_STRINGS.MOD_UTUB_LOCK_SUCCESS,
    ).to_response()


def unlock_utub(*, actor_id: int, utub_id: int, reason: str) -> FlaskResponse:
    """Unlock a UTub, allowing new content to be added again.

    Idempotent: if the UTub is already unlocked, returns a clear no-op 200
    with no audit row. Otherwise sets ``is_locked=False``, audits, and commits.

    Args:
        actor_id: ID of the admin user performing the action.
        utub_id: Primary key of the UTub to unlock.
        reason: Required human-readable reason recorded in the audit log.

    Returns:
        200 JSON envelope on success or no-op.
        404 when the UTub does not exist.
    """
    utub: Utubs | None = Utubs.query.get(utub_id)
    if utub is None:
        return build_message_error_response(
            message=ADMIN_ACTION_STRINGS.MOD_TARGET_NOT_FOUND,
            error_code=AdminActionErrorCodes.TARGET_NOT_FOUND,
            status_code=404,
        )
    if not utub.is_locked:
        return AdminActionResponseSchema(
            status=STD_JSON.SUCCESS,
            message=ADMIN_ACTION_STRINGS.MOD_UTUB_UNLOCK_NOOP,
        ).to_response()

    utub.is_locked = False
    audit.record(
        actor_id=actor_id,
        action=ADMIN_AUDIT_ACTIONS.UTUB_UNLOCK,
        target_type="Utub",
        target_id=str(utub_id),
        metadata={"reason": reason},
    )
    db.session.commit()
    return AdminActionResponseSchema(
        status=STD_JSON.SUCCESS,
        message=ADMIN_ACTION_STRINGS.MOD_UTUB_UNLOCK_SUCCESS,
    ).to_response()


def delete_utub_admin(*, actor_id: int, utub_id: int, reason: str) -> FlaskResponse:
    """Delete a UTub and all its children (members, URLs, tags) via ORM cascade.

    Args:
        actor_id: ID of the admin user performing the action.
        utub_id: Primary key of the UTub to delete.
        reason: Required human-readable reason recorded in the audit log.

    Returns:
        200 JSON envelope on success.
        404 when the UTub does not exist.
    """
    utub: Utubs | None = Utubs.query.get(utub_id)
    if utub is None:
        return build_message_error_response(
            message=ADMIN_ACTION_STRINGS.MOD_TARGET_NOT_FOUND,
            error_code=AdminActionErrorCodes.TARGET_NOT_FOUND,
            status_code=404,
        )

    utub_name: str = utub.name
    db.session.delete(utub)
    audit.record(
        actor_id=actor_id,
        action=ADMIN_AUDIT_ACTIONS.UTUB_DELETE,
        target_type="Utub",
        target_id=str(utub_id),
        metadata={"reason": reason, "utub_name": utub_name},
    )
    db.session.commit()
    return AdminActionResponseSchema(
        status=STD_JSON.SUCCESS,
        message=ADMIN_ACTION_STRINGS.MOD_UTUB_DELETE_SUCCESS,
    ).to_response()


def remove_member_admin(
    *, actor_id: int, utub_id: int, target_user_id: int, reason: str
) -> FlaskResponse:
    """Remove a member from a UTub, with special handling for creator removal.

    Three cases:
    a. Target is not the creator: delete the membership row and audit.
    b. Target is the creator with other members: transfer ownership to the
       lowest-user-id CO_CREATOR (or lowest-user-id MEMBER if none), delete
       the old creator's membership, and audit with ownership_transferred_to.
    c. Target is the creator and is the sole member: delete the whole UTub via
       ORM cascade and audit with utub_deleted=True.

    Args:
        actor_id: ID of the admin user performing the action.
        utub_id: Primary key of the UTub.
        target_user_id: ID of the user to remove from the UTub.
        reason: Required human-readable reason recorded in the audit log.

    Returns:
        200 JSON envelope on success.
        404 when the membership (utub_id, target_user_id) does not exist.
    """
    membership: Utub_Members | None = Utub_Members.query.get((utub_id, target_user_id))
    if membership is None:
        return build_message_error_response(
            message=ADMIN_ACTION_STRINGS.MOD_TARGET_NOT_FOUND,
            error_code=AdminActionErrorCodes.TARGET_NOT_FOUND,
            status_code=404,
        )

    utub: Utubs = membership.to_utub

    if utub.utub_creator != target_user_id:
        # Case a: non-creator removal
        db.session.delete(membership)
        utub.set_last_updated()
        audit.record(
            actor_id=actor_id,
            action=ADMIN_AUDIT_ACTIONS.MEMBER_REMOVE,
            target_type="User",
            target_id=str(target_user_id),
            metadata={"reason": reason, "utub_id": utub_id},
        )
        db.session.commit()
        return AdminActionResponseSchema(
            status=STD_JSON.SUCCESS,
            message=ADMIN_ACTION_STRINGS.MOD_MEMBER_REMOVE_SUCCESS,
        ).to_response()

    # Target is the creator — check for other members.
    other_members: list[Utub_Members] = [
        member for member in utub.members if member.user_id != target_user_id
    ]

    if not other_members:
        # Case c: sole member is the creator — delete the whole UTub.
        db.session.delete(utub)
        audit.record(
            actor_id=actor_id,
            action=ADMIN_AUDIT_ACTIONS.MEMBER_REMOVE,
            target_type="User",
            target_id=str(target_user_id),
            metadata={"reason": reason, "utub_id": utub_id, "utub_deleted": True},
        )
        db.session.commit()
        return AdminActionResponseSchema(
            status=STD_JSON.SUCCESS,
            message=ADMIN_ACTION_STRINGS.MOD_MEMBER_REMOVE_UTUB_DELETED,
        ).to_response()

    # Case b: creator with other members — transfer ownership.
    new_owner_membership: Utub_Members = select_ownership_transfer_target(
        other_members=other_members
    )
    new_owner_id: int = new_owner_membership.user_id
    utub.utub_creator = new_owner_id
    new_owner_membership.member_role = Member_Role.CREATOR
    db.session.delete(membership)
    utub.set_last_updated()
    audit.record(
        actor_id=actor_id,
        action=ADMIN_AUDIT_ACTIONS.MEMBER_REMOVE,
        target_type="User",
        target_id=str(target_user_id),
        metadata={
            "reason": reason,
            "utub_id": utub_id,
            "ownership_transferred_to": new_owner_id,
        },
    )
    db.session.commit()
    return AdminActionResponseSchema(
        status=STD_JSON.SUCCESS,
        message=ADMIN_ACTION_STRINGS.MOD_MEMBER_REMOVE_TRANSFERRED.format(
            user_id=new_owner_id
        ),
    ).to_response()


def delete_url_in_utub_admin(
    *, actor_id: int, utub_id: int, utub_url_id: int, reason: str
) -> FlaskResponse:
    """Delete a specific URL association from a UTub.

    Removes the Utub_Url_Tags rows for that association, then the Utub_Urls
    row, keeping the audit and delete in a single atomic commit. The Urls table
    row is preserved (other UTubs may still reference the same URL).

    Args:
        actor_id: ID of the admin user performing the action.
        utub_id: Primary key of the UTub containing the URL.
        utub_url_id: Primary key of the Utub_Urls row to delete.
        reason: Required human-readable reason recorded in the audit log.

    Returns:
        200 JSON envelope on success.
        404 when no Utub_Urls row matches both utub_url_id and utub_id.
    """
    utub_url: Utub_Urls | None = Utub_Urls.query.filter_by(
        id=utub_url_id, utub_id=utub_id
    ).first()
    if utub_url is None:
        return build_message_error_response(
            message=ADMIN_ACTION_STRINGS.MOD_TARGET_NOT_FOUND,
            error_code=AdminActionErrorCodes.TARGET_NOT_FOUND,
            status_code=404,
        )

    url_id: int = utub_url.url_id
    containing_utub: Utubs = utub_url.utub
    db.session.query(Utub_Url_Tags).filter(
        Utub_Url_Tags.utub_url_id == utub_url_id,
        Utub_Url_Tags.utub_id == utub_id,
    ).delete()
    db.session.delete(utub_url)
    containing_utub.set_last_updated()
    audit.record(
        actor_id=actor_id,
        action=ADMIN_AUDIT_ACTIONS.URL_DELETE,
        target_type="UtubUrl",
        target_id=str(utub_url_id),
        metadata={"reason": reason, "utub_id": utub_id, "url_id": url_id},
    )
    db.session.commit()
    return AdminActionResponseSchema(
        status=STD_JSON.SUCCESS,
        message=ADMIN_ACTION_STRINGS.MOD_URL_DELETE_SUCCESS,
    ).to_response()


def purge_url_globally(*, actor_id: int, url_id: int, reason: str) -> FlaskResponse:
    """Remove a URL from every UTub it appears in, keeping the Urls row.

    For each Utub_Urls association of the given url_id, deletes the associated
    Utub_Url_Tags rows and then the association row. The Urls record is
    intentionally preserved so existing external references remain valid.

    Audits once with count=number of UTub associations removed. A URL with
    zero UTub associations still results in a 200 response with count=0
    (the Urls row was confirmed present).

    Args:
        actor_id: ID of the admin user performing the action.
        url_id: Primary key of the Urls row to purge from all UTubs.
        reason: Required human-readable reason recorded in the audit log.

    Returns:
        200 JSON envelope with count=UTubs affected on success.
        404 when the Urls row does not exist.
    """
    url: Urls | None = Urls.query.get(url_id)
    if url is None:
        return build_message_error_response(
            message=ADMIN_ACTION_STRINGS.MOD_TARGET_NOT_FOUND,
            error_code=AdminActionErrorCodes.TARGET_NOT_FOUND,
            status_code=404,
        )

    utub_urls: list[Utub_Urls] = Utub_Urls.query.filter_by(url_id=url_id).all()
    utub_count: int = len(utub_urls)

    for utub_url in utub_urls:
        db.session.query(Utub_Url_Tags).filter(
            Utub_Url_Tags.utub_url_id == utub_url.id,
        ).delete()
        utub_url.utub.set_last_updated()
        db.session.delete(utub_url)

    audit.record(
        actor_id=actor_id,
        action=ADMIN_AUDIT_ACTIONS.URL_PURGE,
        target_type="Url",
        target_id=str(url_id),
        metadata={"reason": reason, "utub_count": utub_count},
    )
    db.session.commit()
    return AdminActionResponseSchema(
        status=STD_JSON.SUCCESS,
        message=ADMIN_ACTION_STRINGS.MOD_URL_PURGE_SUCCESS.format(count=utub_count),
        count=utub_count,
    ).to_response()


def delete_utub_tag_admin(
    *, actor_id: int, utub_id: int, utub_tag_id: int, reason: str
) -> FlaskResponse:
    """Delete a tag from a UTub's tag vocabulary, cascading its applications.

    Deletes one Utub_Tags row. The ORM cascade
    (``Utub_Tags.utub_url_tag_associations``) removes every Utub_Url_Tags row
    that referenced the tag, so the tag is unapplied from all URLs it was on.
    Audits with the count of URL applications removed.

    Args:
        actor_id: ID of the admin user performing the action.
        utub_id: Primary key of the UTub owning the tag vocabulary.
        utub_tag_id: Primary key of the Utub_Tags row to delete.
        reason: Required human-readable reason recorded in the audit log.

    Returns:
        200 JSON envelope with count=URL applications removed on success.
        404 when no Utub_Tags row matches both utub_tag_id and utub_id.
    """
    utub_tag: Utub_Tags | None = Utub_Tags.query.filter_by(
        id=utub_tag_id, utub_id=utub_id
    ).first()
    if utub_tag is None:
        return build_message_error_response(
            message=ADMIN_ACTION_STRINGS.MOD_TARGET_NOT_FOUND,
            error_code=AdminActionErrorCodes.TARGET_NOT_FOUND,
            status_code=404,
        )

    associations_removed: int = Utub_Url_Tags.query.filter_by(
        utub_tag_id=utub_tag_id, utub_id=utub_id
    ).count()
    containing_utub: Utubs = Utubs.query.get(utub_id)
    db.session.delete(utub_tag)
    containing_utub.set_last_updated()
    audit.record(
        actor_id=actor_id,
        action=ADMIN_AUDIT_ACTIONS.UTUB_TAG_DELETE,
        target_type="UtubTag",
        target_id=str(utub_tag_id),
        metadata={
            "reason": reason,
            "utub_id": utub_id,
            "associations_removed": associations_removed,
        },
    )
    db.session.commit()
    return AdminActionResponseSchema(
        status=STD_JSON.SUCCESS,
        message=ADMIN_ACTION_STRINGS.MOD_UTUB_TAG_DELETE_SUCCESS.format(
            count=associations_removed
        ),
        count=associations_removed,
    ).to_response()
