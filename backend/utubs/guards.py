from __future__ import annotations

from enum import Enum

from flask import abort, g
from flask_login import current_user

from backend import db
from backend.api_common.responses import FlaskResponse
from backend.app_logger import critical_log
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utubs import Utubs
from backend.schemas.errors import build_message_error_response
from backend.utils.strings.utub_strs import UTUB_FAILURE


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
    writer (and ``GET /utubs/<id>``) also UPDATEs ``Utubs.last_updated`` via
    ``set_last_updated()``, so they queue behind the lock until commit.

    Hold-time expectations: no ``lock_timeout`` is set (Postgres defaults
    apply). Keep the work between lock and commit short, with no external I/O
    beyond what ``create_utub_member`` already does with Redis (bounded to ~1s
    by client socket timeouts). Erasure holds several UTub locks for the length
    of ``erase_user_core``; a stalled holder makes other writers to that UTub
    wait until the web worker timeout, and URL/tag writes and UTub opens wait
    too.

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


def get_fresh_membership(*, utub_id: int, user_id: int) -> Utub_Members | None:
    """Re-read a membership row, bypassing the identity-map shortcut.

    Args:
        utub_id (int): ID of the UTub.
        user_id (int): ID of the user.

    Returns:
        The refreshed membership, or None if it was deleted concurrently.
    """
    return Utub_Members.query.populate_existing().get((utub_id, user_id))


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
    utub = lock_utub_for_update(utub_id=current_utub.id)
    if utub is None or utub.is_trashed:
        abort(404)

    actor = get_fresh_membership(utub_id=utub.id, user_id=current_user.id)
    if actor is None:
        abort(404)

    g.is_manager = actor.member_role in (Member_Role.CREATOR, Member_Role.CO_CREATOR)

    if required_access is UtubAccess.OWNER and current_user.id != utub.utub_creator:
        critical_log(
            f"User={current_user.id} not owner: UTub.id={utub.id} | UTub.name={utub.name}"
        )
        return build_message_error_response(
            message=UTUB_FAILURE.NOT_AUTHORIZED, status_code=403
        )

    if required_access is UtubAccess.MANAGER and not g.is_manager:
        critical_log(
            f"User={current_user.id} not manager: UTub.id={utub.id} | UTub.name={utub.name}"
        )
        return build_message_error_response(
            message=UTUB_FAILURE.NOT_AUTHORIZED, status_code=403
        )

    return reject_if_utub_locked(utub, error_code=error_code)
