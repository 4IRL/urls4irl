from __future__ import annotations

from enum import Enum

from flask import abort, g
from flask_login import current_user
from sqlalchemy import and_

from backend import db
from backend.api_common.responses import FlaskResponse
from backend.app_logger import critical_log
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utubs import Utubs
from backend.schemas.errors import build_message_error_response
from backend.utils.strings.trash_strs import TRASH_FAILURE
from backend.utils.strings.utub_strs import UTUB_FAILURE
from backend.utubs.constants import UTubErrorCodes


class UtubAccess(Enum):
    """Minimum role a caller must still hold once the UTub row is locked."""

    MEMBER = "member"
    MANAGER = "manager"
    OWNER = "owner"


def reject_if_utub_locked(utub: Utubs, *, error_code: int) -> FlaskResponse | None:
    """Return a 403 'UTub is locked' response when the UTub is locked, else None.

    Shared write-guard for every user-facing mutation of a UTub and its contents —
    adding, editing, and deleting URLs / members / tags, plus renaming or deleting
    the UTub itself. Admin-dashboard actions bypass this guard entirely (they route
    through backend/admin/action_routes.py). Callers pass their own domain error_code
    so the API contract per domain is unchanged. Mirrors the reject_* guard helpers
    in backend/admin/guards.py.
    """
    if utub.is_locked:
        return build_message_error_response(
            message=UTUB_FAILURE.UTUB_IS_LOCKED,
            error_code=error_code,
            status_code=403,
        )
    return None


def lock_utub_for_update(*, utub_id: int) -> Utubs | None:
    """Take the per-UTub row lock and refresh the UTub and its member rows.

    This is the serialization point every owner/role writer takes first (lock
    order: the ``Utubs`` row before any ``UtubMembers`` row). It must be called
    before any mutation in the transaction. The lock is held until the
    transaction commits or rolls back, and is unrelated to the admin
    ``is_locked`` flag.

    ``key_share=True`` renders ``SELECT ... FOR NO KEY UPDATE``, the weakest row
    lock that still serializes writers of the ``Utubs`` row. It does not block
    the FK ``KEY SHARE`` check taken by child inserts, but every URL/tag/member
    writer also UPDATEs ``Utubs.last_updated`` via ``set_last_updated()``, so
    they queue behind the lock until commit. ``GET /utubs/<id>`` does not: an
    open updates only the caller's ``UtubMembers.lastOpenedAt`` row, takes no
    ``Utubs`` lock, and cannot deadlock against ``lock_and_reauthorize`` because
    it never locks ``Utubs``.

    Hold-time expectations: no ``lock_timeout`` is set (Postgres defaults
    apply). Keep the work between lock and commit short, with no external I/O
    beyond what ``create_utub_member`` already does with Redis (bounded to ~1s
    by client socket timeouts). Erasure holds several UTub locks for the length
    of ``erase_user_core``; a stalled holder makes other writers to that UTub
    wait until the web worker timeout, and URL/tag writes wait too (UTub opens
    do not: they never touch the ``Utubs`` row).

    ``populate_existing()`` is required because the auth guard already loaded
    these rows into the session identity map; without it the re-query returns
    the cached, possibly stale, instances.

    Args:
        utub_id (int): ID of the UTub to lock.

    Returns:
        The locked, refreshed ``Utubs`` row, or None if it does not exist.
    """
    utub: Utubs | None = (
        Utubs.query.populate_existing()
        .with_for_update(key_share=True)
        .filter(Utubs.id == utub_id)
        .one_or_none()
    )
    if utub is None:
        return None

    Utub_Members.query.populate_existing().filter(Utub_Members.utub_id == utub_id).all()
    db.session.expire(utub, ["members"])
    return utub


def lock_live_utub_or_abort(*, utub_id: int) -> Utubs:
    """Take the per-UTub row lock for a writer that already passed its route guard.

    For URL trash and address-edit writers: they lock ``Utubs`` before any
    ``UtubUrls`` row so they take the same order as the short-link mint
    (``Utubs`` -> ``UtubUrls`` -> ``ShortLinks``) and cannot deadlock with it. Unlike
    ``lock_and_reauthorize`` this does not re-check membership or role; the route
    decorators did that.

    Args:
        utub_id (int): ID of the UTub to lock.

    Returns:
        The locked, refreshed ``Utubs`` row. Aborts 404 (after rolling back) when it
        is gone or was trashed concurrently.
    """
    utub: Utubs | None = lock_utub_for_update(utub_id=utub_id)
    if utub is None or utub.is_trashed:
        db.session.rollback()
        abort(404)
    return utub


def get_fresh_membership(*, utub_id: int, user_id: int) -> Utub_Members | None:
    """Re-read a membership row, bypassing the identity-map shortcut.

    Args:
        utub_id (int): ID of the UTub.
        user_id (int): ID of the user.

    Returns:
        The refreshed membership, or None if it was deleted concurrently.
    """
    return Utub_Members.query.populate_existing().get((utub_id, user_id))


def get_utub_member_ids(*, utub_id: int) -> set[int]:
    """Return the user ids of every member of a UTub.

    Args:
        utub_id (int): ID of the UTub.

    Returns:
        The set of member user ids.
    """
    return {
        member_id
        for (member_id,) in db.session.query(Utub_Members.user_id).filter(
            Utub_Members.utub_id == utub_id
        )
    }


def lock_and_reauthorize(
    current_utub: Utubs, *, required_access: UtubAccess, error_code: int
) -> FlaskResponse | None:
    """Lock the UTub row, then re-check the caller's authorization on fresh state.

    Check order (authorization precedes the locked-UTub check, so a
    non-authorized caller never learns the UTub is locked and a revoked actor
    gets the same response as the decorators give):

    1. Lock the UTub row via ``lock_utub_for_update``; abort 404 if it is gone
       or trashed.
    2. Re-read the caller's membership; abort 404 if it is gone. Recompute
       ``g.is_manager`` from the fresh role.
    3. Check the required role (OWNER: caller is the fresh ``utub_creator``;
       MANAGER: fresh ``g.is_manager``); on failure log critically and return
       403 ``NOT_AUTHORIZED``.
    4. Last, ``reject_if_utub_locked``.

    Args:
        current_utub (Utubs): The UTub loaded (unlocked) by the route guard.
        required_access (UtubAccess): Minimum role the caller must still hold.
        error_code (int): Domain error code for the locked-UTub response.

    Returns:
        An error response tuple to return from the service, or None when the
        caller is still authorized and the UTub is not locked.
    """
    utub: Utubs | None = lock_utub_for_update(utub_id=current_utub.id)
    if utub is None or utub.is_trashed:
        abort(404)

    actor: Utub_Members | None = get_fresh_membership(
        utub_id=utub.id, user_id=current_user.id
    )
    if actor is None:
        abort(404)

    g.is_manager = actor.member_role in (Member_Role.CREATOR, Member_Role.CO_CREATOR)

    # Fail closed: only an explicitly handled access level can authorize.
    authorized: bool = False
    role_label: str = ""
    if required_access is UtubAccess.OWNER:
        authorized = current_user.id == utub.utub_creator
        role_label = "owner"
    elif required_access is UtubAccess.MANAGER:
        authorized = g.is_manager
        role_label = "manager"
    elif required_access is UtubAccess.MEMBER:
        # Current membership was already verified by the fresh lookup above.
        authorized = True
        role_label = "member"

    if not authorized:
        critical_log(
            f"User={current_user.id} not {role_label}: UTub.id={utub.id} | UTub.name={utub.name}"
        )
        return build_message_error_response(
            message=UTUB_FAILURE.NOT_AUTHORIZED, status_code=403
        )

    return reject_if_utub_locked(utub, error_code=error_code)


def _trashed_utub_not_actionable_response() -> FlaskResponse:
    """The one masked 404 every non-actionable trashed-UTub case answers with."""
    return build_message_error_response(
        message=TRASH_FAILURE.NOT_IN_TRASH,
        error_code=UTubErrorCodes.NOT_IN_TRASH,
        status_code=404,
    )


def lock_trashed_utub_for_creator(
    *, utub_id: int, reject_locked: bool = True
) -> Utubs | FlaskResponse:
    """Lock a TRASHED UTub row and re-authorize its creator on fresh state.

    Counterpart of ``lock_and_reauthorize`` for the Trash flows, where the UTub is
    expected to be trashed (so the live-UTub 404 does not apply) and only its
    creator may act.

    Check order (authorization precedes both the lock and the locked-UTub check, so
    a non-creator never learns whether a UTub is locked or even exists, and never
    takes the row lock):

    1. Authorize before locking: a plain non-locking read must show the UTub
       trashed, created by the caller, with the caller's membership row still
       present. Anything else gets the masked 404 without touching the row lock, so
       an arbitrary authenticated user cannot queue writers behind another UTub.
    2. Only then lock the UTub row via ``lock_utub_for_update`` and re-check the
       same conditions on fresh state under the lock (the pre-check is a filter,
       not the authority).
    3. Mask every non-actionable case with the same 404 ``NOT_IN_TRASH``: the
       UTub is missing, live (not trashed), the caller is no longer a member, or
       the caller is not the creator.
    4. Last, when ``reject_locked`` is set, ``reject_if_utub_locked`` (403
       ``UTUB_IS_LOCKED``).

    Args:
        utub_id (int): ID of the UTub to lock.
        reject_locked (bool): Whether a locked UTub is refused with a 403.

    Returns:
        The locked, refreshed trashed ``Utubs`` row (with ``g.is_manager`` set),
        or an error response to return from the service.
    """
    # Fail closed: the cheap pre-check lets only a plausible actor reach the lock.
    prefilter_hit = (
        db.session.query(Utubs.id)
        .join(
            Utub_Members,
            and_(
                Utub_Members.utub_id == Utubs.id,
                Utub_Members.user_id == current_user.id,
            ),
        )
        .filter(
            Utubs.id == utub_id,
            Utubs.deleted_at.isnot(None),
            Utubs.utub_creator == current_user.id,
        )
        .first()
    )
    if prefilter_hit is None:
        return _trashed_utub_not_actionable_response()

    utub: Utubs | None = lock_utub_for_update(utub_id=utub_id)
    actor: Utub_Members | None = get_fresh_membership(
        utub_id=utub_id, user_id=current_user.id
    )

    # Fail closed: any unmet condition denies with the same masked 404.
    if (
        utub is None
        or not utub.is_trashed
        or actor is None
        or utub.utub_creator != current_user.id
    ):
        return _trashed_utub_not_actionable_response()

    if reject_locked:
        locked_response: FlaskResponse | None = reject_if_utub_locked(
            utub, error_code=UTubErrorCodes.UTUB_IS_LOCKED
        )
        if locked_response is not None:
            return locked_response

    g.is_manager = True
    return utub
