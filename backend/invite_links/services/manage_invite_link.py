from __future__ import annotations

from datetime import timedelta
from enum import StrEnum

from flask_login import current_user
from sqlalchemy.exc import IntegrityError

from backend import db
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.app_logger import safe_add_many_logs, warning_log
from backend.extensions.metrics.writer import record_event
from backend.invite_links.constants import (
    INVITE_LINK_TOKEN_MAX_ATTEMPTS,
    ONE_ACTIVE_INVITE_LINK_PER_UTUB,
    UNIQUE_INVITE_LINK_TOKEN,
    InviteLinkErrorCodes,
)
from backend.invite_links.guards import lock_current_invite_for_update
from backend.invite_links.token_generator import generate_invite_token
from backend.invite_links.validity import (
    evaluate_invite,
    invite_state_to_link_status,
    is_invite_live,
)
from backend.metrics.events import EventName
from backend.models.utub_invite_links import Utub_Invite_Links
from backend.models.utubs import Utubs
from backend.schemas.errors import build_message_error_response
from backend.schemas.invite_links import InviteLinkResponseSchema, InviteLinkSchema
from backend.schemas.requests.invite_links import (
    InviteLinkSettingsRequest,
    UpdateInviteLinkRequest,
)
from backend.utils.datetime_utils import utc_now
from backend.utils.db_errors import violated_constraint
from backend.utils.strings.invite_link_strs import (
    INVITE_LINK_FAILURE,
    INVITE_LINK_SUCCESS,
)
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utubs.guards import UtubAccess, lock_and_reauthorize


class InsertFailure(StrEnum):
    """Why ``insert_invite_link`` wrote no row."""

    LIVE_LINK_EXISTS = "live_link_exists"
    TOKENS_EXHAUSTED = "tokens_exhausted"


def build_invite_link_schema(invite: Utub_Invite_Links) -> InviteLinkSchema:
    """Build the manager-facing schema for an unrevoked invite link.

    The one builder every invite link response goes through. ``status`` comes from
    ``evaluate_invite`` (first-match order) mapped to the manager-facing status.
    Pure read: writes nothing and takes no lock.
    """
    return InviteLinkSchema(
        token=invite.token,
        status=invite_state_to_link_status(evaluate_invite(invite)),
        expires_at=invite.expires_at,
        max_uses=invite.max_uses,
        use_count=invite.use_count,
        created_at=invite.created_at,
        creator_username=None if invite.creator is None else invite.creator.username,
    )


def get_unrevoked_invite(*, utub_id: int) -> Utub_Invite_Links | None:
    """Read (without locking) the UTub's unrevoked invite link, if any."""
    return Utub_Invite_Links.query.filter(
        Utub_Invite_Links.utub_id == utub_id,
        Utub_Invite_Links.revoked_at.is_(None),
    ).one_or_none()


def read_invite_link(current_utub: Utubs) -> InviteLinkResponseSchema:
    """Return the UTub's current invite link, or a null link when there is none."""
    invite = get_unrevoked_invite(utub_id=current_utub.id)
    return InviteLinkResponseSchema(
        status=STD_JSON.SUCCESS,
        invite_link=None if invite is None else build_invite_link_schema(invite),
    )


def lock_manager_and_reauthorize(current_utub: Utubs) -> FlaskResponse | None:
    """The one manager check every invite link write goes through.

    Locks the ``Utubs`` row, re-checks the caller is still a manager and rejects a
    locked UTub with ``UTUB_IS_LOCKED`` (in that order). Returns an error response,
    or None when the caller may proceed.
    """
    return lock_and_reauthorize(
        current_utub,
        required_access=UtubAccess.MANAGER,
        error_code=InviteLinkErrorCodes.UTUB_IS_LOCKED,
    )


def revoke_invite_row(invite: Utub_Invite_Links) -> None:
    """Mark one invite row revoked and flush. Takes no locks and never commits.

    The caller must already hold the ``Utubs`` lock and the row lock.
    """
    invite.revoked_at = utc_now()
    db.session.flush()


def insert_invite_link(
    *, utub_id: int, created_by: int, expires_in_days: int, max_uses: int | None
) -> Utub_Invite_Links | InsertFailure:
    """Insert a new invite row in a savepoint, retrying on a token collision.

    A ``UNIQUE_INVITE_LINK_TOKEN`` violation retries with a new token up to
    ``INVITE_LINK_TOKEN_MAX_ATTEMPTS`` times; a ``ONE_ACTIVE_INVITE_LINK_PER_UTUB``
    violation returns ``LIVE_LINK_EXISTS``; any other integrity error propagates.
    Never commits; the caller owns the transaction (and rolls back on a failure).
    """
    for _ in range(INVITE_LINK_TOKEN_MAX_ATTEMPTS):
        invite = Utub_Invite_Links(
            utub_id=utub_id,
            token=generate_invite_token(),
            created_by=created_by,
            expires_at=utc_now() + timedelta(days=expires_in_days),
            max_uses=max_uses,
        )
        try:
            with db.session.begin_nested():
                db.session.add(invite)
        except IntegrityError as integrity_error:
            constraint: str | None = violated_constraint(integrity_error)
            if constraint == UNIQUE_INVITE_LINK_TOKEN:
                continue
            if constraint == ONE_ACTIVE_INVITE_LINK_PER_UTUB:
                return InsertFailure.LIVE_LINK_EXISTS
            raise
        return invite
    return InsertFailure.TOKENS_EXHAUSTED


def _insert_failure_response(failure: InsertFailure, *, utub_id: int) -> FlaskResponse:
    """Roll back and build the response for a failed insert (no row, no metric)."""
    db.session.rollback()
    if failure is InsertFailure.LIVE_LINK_EXISTS:
        return build_message_error_response(
            message=INVITE_LINK_FAILURE.LIVE_LINK_EXISTS,
            error_code=InviteLinkErrorCodes.LIVE_LINK_EXISTS,
            status_code=409,
        )
    warning_log(f"Invite link token attempts exhausted | UTub.id={utub_id}")
    return build_message_error_response(
        message=INVITE_LINK_FAILURE.SOMETHING_WENT_WRONG, status_code=500
    )


def create_invite_link_for_utub(
    *, current_utub: Utubs, settings: InviteLinkSettingsRequest
) -> FlaskResponse:
    """Create the UTub's invite link, clearing a dead-unrevoked one first.

    Lock order: the ``Utubs`` row (``lock_manager_and_reauthorize``), then the UTub's
    unrevoked invite row, then the insert. A live row is a 409; a dead-unrevoked row
    is revoked and flushed before the insert so the one-active-link index never
    trips. Commits once; metrics are emitted after the commit. Every early return
    rolls back, so a failed insert also leaves the dead row unrevoked.

    Args:
        current_utub (Utubs): The UTub loaded (unlocked) by the route guard.
        settings (InviteLinkSettingsRequest): Validated expiry and use limit.

    Returns:
        FlaskResponse: 201 with the link, or the error response.
    """
    auth_error: FlaskResponse | None = lock_manager_and_reauthorize(current_utub)
    if auth_error is not None:
        db.session.rollback()
        return auth_error

    # Capture ids up front: commit and rollback both expire the instances.
    user_id: int = current_user.id
    utub_id: int = current_utub.id

    existing: Utub_Invite_Links | None = lock_current_invite_for_update(utub_id=utub_id)
    cleared_dead_row: bool = False
    if existing is not None:
        # Fail closed: only a positively live row blocks the create.
        if is_invite_live(evaluate_invite(existing)):
            db.session.rollback()
            return build_message_error_response(
                message=INVITE_LINK_FAILURE.LIVE_LINK_EXISTS,
                error_code=InviteLinkErrorCodes.LIVE_LINK_EXISTS,
                status_code=409,
            )
        revoke_invite_row(existing)
        cleared_dead_row = True

    inserted: Utub_Invite_Links | InsertFailure = insert_invite_link(
        utub_id=utub_id,
        created_by=user_id,
        expires_in_days=settings.expires_in_days,
        max_uses=settings.max_uses,
    )
    if isinstance(inserted, InsertFailure):
        return _insert_failure_response(inserted, utub_id=utub_id)

    has_use_limit: str = "true" if settings.max_uses is not None else "false"
    response: FlaskResponse = APIResponse(
        message=INVITE_LINK_SUCCESS.INVITE_LINK_CREATED,
        data=InviteLinkResponseSchema(
            status=STD_JSON.SUCCESS, invite_link=build_invite_link_schema(inserted)
        ),
        status_code=201,
    ).to_response()
    db.session.commit()

    record_event(
        EventName.INVITE_LINK_CREATED, dimensions={"has_use_limit": has_use_limit}
    )
    if cleared_dead_row:
        record_event(
            EventName.INVITE_LINK_REVOKED, dimensions={"reason": "dead_on_create"}
        )
    safe_add_many_logs(
        [
            "Created invite link",
            f"User.id={user_id}",
            f"UTub.id={utub_id}",
            f"Cleared dead link={cleared_dead_row}",
        ]
    )
    return response


def _no_link_response() -> FlaskResponse:
    """404 with ``INVITE_LINK_NOT_FOUND`` for a write on a UTub with no unrevoked link."""
    db.session.rollback()
    return build_message_error_response(
        message=INVITE_LINK_FAILURE.INVITE_LINK_NOT_FOUND,
        error_code=InviteLinkErrorCodes.INVITE_LINK_NOT_FOUND,
        status_code=404,
    )


def update_invite_link_for_utub(
    *, current_utub: Utubs, update: UpdateInviteLinkRequest
) -> FlaskResponse:
    """Change the expiry and/or use limit of the UTub's live invite link.

    Check order: no row (404), dead-unrevoked row (409 ``DEAD_LINK_UPDATE``), then
    ``max_uses`` below the joined count (400 ``USES_BELOW_JOINED``). A rejected update
    changes neither field. An absent field is left unchanged; an explicit null
    ``max_uses`` sets the link unlimited.

    Args:
        current_utub (Utubs): The UTub loaded (unlocked) by the route guard.
        update (UpdateInviteLinkRequest): Validated partial update.

    Returns:
        FlaskResponse: 200 with the link, or the error response.
    """
    auth_error: FlaskResponse | None = lock_manager_and_reauthorize(current_utub)
    if auth_error is not None:
        db.session.rollback()
        return auth_error

    user_id: int = current_user.id
    utub_id: int = current_utub.id

    invite: Utub_Invite_Links | None = lock_current_invite_for_update(utub_id=utub_id)
    if invite is None:
        return _no_link_response()
    if not is_invite_live(evaluate_invite(invite)):
        db.session.rollback()
        return build_message_error_response(
            message=INVITE_LINK_FAILURE.DEAD_LINK_UPDATE,
            error_code=InviteLinkErrorCodes.DEAD_LINK_UPDATE,
            status_code=409,
        )

    if update.max_uses is not None and update.max_uses < invite.use_count:
        db.session.rollback()
        return build_message_error_response(
            message=INVITE_LINK_FAILURE.USES_BELOW_JOINED,
            error_code=InviteLinkErrorCodes.USES_BELOW_JOINED,
            status_code=400,
        )

    if "max_uses" in update.model_fields_set:
        invite.max_uses = update.max_uses
    if update.expires_in_days is not None:
        invite.expires_at = utc_now() + timedelta(days=update.expires_in_days)
    db.session.flush()

    response: FlaskResponse = APIResponse(
        message=INVITE_LINK_SUCCESS.INVITE_LINK_UPDATED,
        data=InviteLinkResponseSchema(
            status=STD_JSON.SUCCESS, invite_link=build_invite_link_schema(invite)
        ),
        status_code=200,
    ).to_response()
    db.session.commit()

    safe_add_many_logs(
        ["Updated invite link", f"User.id={user_id}", f"UTub.id={utub_id}"]
    )
    return response


def replace_invite_link_for_utub(
    *, current_utub: Utubs, settings: InviteLinkSettingsRequest
) -> FlaskResponse:
    """Revoke the UTub's unrevoked link (live or dead) and insert a fresh one.

    The revoke and insert share one transaction, so a failed insert rolls the revoke
    back and the old link stays as it was. Metrics are emitted after the commit.

    Args:
        current_utub (Utubs): The UTub loaded (unlocked) by the route guard.
        settings (InviteLinkSettingsRequest): Validated expiry and use limit.

    Returns:
        FlaskResponse: 201 with the new link, or the error response.
    """
    auth_error: FlaskResponse | None = lock_manager_and_reauthorize(current_utub)
    if auth_error is not None:
        db.session.rollback()
        return auth_error

    user_id: int = current_user.id
    utub_id: int = current_utub.id

    existing: Utub_Invite_Links | None = lock_current_invite_for_update(utub_id=utub_id)
    if existing is None:
        return _no_link_response()
    revoke_invite_row(existing)

    inserted: Utub_Invite_Links | InsertFailure = insert_invite_link(
        utub_id=utub_id,
        created_by=user_id,
        expires_in_days=settings.expires_in_days,
        max_uses=settings.max_uses,
    )
    if isinstance(inserted, InsertFailure):
        return _insert_failure_response(inserted, utub_id=utub_id)

    has_use_limit: str = "true" if settings.max_uses is not None else "false"
    response: FlaskResponse = APIResponse(
        message=INVITE_LINK_SUCCESS.INVITE_LINK_REPLACED,
        data=InviteLinkResponseSchema(
            status=STD_JSON.SUCCESS, invite_link=build_invite_link_schema(inserted)
        ),
        status_code=201,
    ).to_response()
    db.session.commit()

    record_event(
        EventName.INVITE_LINK_CREATED, dimensions={"has_use_limit": has_use_limit}
    )
    record_event(EventName.INVITE_LINK_REVOKED, dimensions={"reason": "replaced"})
    safe_add_many_logs(
        ["Replaced invite link", f"User.id={user_id}", f"UTub.id={utub_id}"]
    )
    return response


def revoke_invite_link_for_utub(*, current_utub: Utubs) -> FlaskResponse:
    """Revoke the UTub's unrevoked link (live or dead); the row is retained.

    Args:
        current_utub (Utubs): The UTub loaded (unlocked) by the route guard.

    Returns:
        FlaskResponse: 200 message, or the error response.
    """
    auth_error: FlaskResponse | None = lock_manager_and_reauthorize(current_utub)
    if auth_error is not None:
        db.session.rollback()
        return auth_error

    user_id: int = current_user.id
    utub_id: int = current_utub.id

    invite: Utub_Invite_Links | None = lock_current_invite_for_update(utub_id=utub_id)
    if invite is None:
        return _no_link_response()
    revoke_invite_row(invite)

    response: FlaskResponse = APIResponse(
        message=INVITE_LINK_SUCCESS.INVITE_LINK_REVOKED, status_code=200
    ).to_response()
    db.session.commit()

    record_event(EventName.INVITE_LINK_REVOKED, dimensions={"reason": "manual"})
    safe_add_many_logs(
        ["Revoked invite link", f"User.id={user_id}", f"UTub.id={utub_id}"]
    )
    return response
