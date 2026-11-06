from flask import abort
from flask_login import current_user
from sqlalchemy import func, text

from backend import db
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.app_logger import safe_add_many_logs
from backend.models.utub_members import Utub_Members
from backend.models.utubs import Utubs
from backend.schemas.utubs import UtubPinUpdatedResponseSchema
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.utub_strs import (
    UTUB_FAILURE,
    UTUB_PIN_NO_CHANGE,
    UTUB_PINNED,
    UTUB_UNPINNED,
)
from backend.utubs.constants import (
    MAX_PINNED_UTUBS,
    PIN_CAP_ADVISORY_LOCK_NAMESPACE,
    UTubErrorCodes,
)


def count_live_pinned_utubs(user_id: int) -> int:
    """Count the user's pinned memberships on live (not trashed) UTubs.

    Module-level on purpose: the concurrency test patches it to widen the race
    window between the count and the commit.
    """
    return (
        db.session.query(func.count())
        .select_from(Utub_Members)
        .join(Utubs, Utubs.id == Utub_Members.utub_id)
        .filter(
            Utub_Members.user_id == user_id,
            Utub_Members.pinned_at.is_not(None),
            Utubs.deleted_at.is_(None),
        )
        .scalar()
        or 0
    )


def _pin_response(
    *, status: str, message: str, utub_id: int, is_pinned: bool, pinned_count: int
) -> FlaskResponse:
    return APIResponse(
        data=UtubPinUpdatedResponseSchema(
            status=status,  # type: ignore[arg-type]
            message=message,
            utub_id=utub_id,
            is_pinned=is_pinned,
            pinned_count=pinned_count,
        )
    ).to_response()


def update_utub_pin_if_changed(current_utub: Utubs, pinned: bool) -> FlaskResponse:
    """
    Pin or unpin a UTub for the caller, enforcing the per-user pin cap.

    Not lock-gated: a pin is a private list preference (stored on the caller's
    own membership row), like member settings. Idempotent: a request that
    matches the stored state rolls back and commits nothing, even at the cap.

    Lock order: a per-user transaction advisory lock first (serializes this
    user's pin writes so two pins of different UTubs cannot both pass the
    count), then the caller's membership row, then the count. The advisory lock
    is not a row lock, so it cannot form a cycle with ``erase_user_core``; it
    is released on commit or rollback, so every early return rolls back.

    Args:
        current_utub (Utubs): The UTub being pinned or unpinned
        pinned (bool): The requested state

    Returns:
        FlaskResponse: 200 with the resulting state, 409 at the cap, or 404
    """
    user_id: int = current_user.id
    utub_id: int = current_utub.id
    db.session.execute(
        text("SELECT pg_advisory_xact_lock(:namespace, :user_id)"),
        {"namespace": PIN_CAP_ADVISORY_LOCK_NAMESPACE, "user_id": user_id},
    )

    # Join Utubs so a UTub trashed after the decorator check is a 404; lock only
    # the membership row.
    membership: Utub_Members | None = (
        Utub_Members.query.join(Utubs, Utubs.id == Utub_Members.utub_id)
        .filter(
            Utub_Members.utub_id == utub_id,
            Utub_Members.user_id == user_id,
            Utubs.deleted_at.is_(None),
        )
        .populate_existing()
        .with_for_update(of=Utub_Members)
        .one_or_none()
    )
    if membership is None:
        # Removed or trashed concurrently: release the locks, then mask as not found.
        db.session.rollback()
        abort(404)

    if (membership.pinned_at is not None) == pinned:
        pinned_count = count_live_pinned_utubs(user_id)
        db.session.rollback()
        safe_add_many_logs(
            [
                "No change in UTub pin",
                f"UTub.id={utub_id}",
                f"Pinned={pinned}",
            ]
        )
        return _pin_response(
            status=STD_JSON.NO_CHANGE,
            message=UTUB_PIN_NO_CHANGE,
            utub_id=utub_id,
            is_pinned=pinned,
            pinned_count=pinned_count,
        )

    if not pinned:
        membership.pinned_at = None
        pinned_count = count_live_pinned_utubs(user_id)
    else:
        pinned_count = count_live_pinned_utubs(user_id)
        if pinned_count >= MAX_PINNED_UTUBS:
            db.session.rollback()
            safe_add_many_logs(
                [
                    "User hit the UTub pin cap",
                    f"UTub.id={utub_id}",
                    f"Pinned count={pinned_count}",
                ]
            )
            return APIResponse(
                status_code=409,
                message=UTUB_FAILURE.UTUB_PINS_CAP_REACHED,
                error_code=UTubErrorCodes.PIN_LIMIT_REACHED,
            ).to_response()
        membership.pinned_at = utc_now()
        pinned_count += 1

    db.session.commit()
    safe_add_many_logs(
        [
            "User pinned a UTub" if pinned else "User unpinned a UTub",
            f"UTub.id={utub_id}",
            f"Pinned count={pinned_count}",
        ]
    )
    return _pin_response(
        status=STD_JSON.SUCCESS,
        message=UTUB_PINNED if pinned else UTUB_UNPINNED,
        utub_id=utub_id,
        is_pinned=pinned,
        pinned_count=pinned_count,
    )
