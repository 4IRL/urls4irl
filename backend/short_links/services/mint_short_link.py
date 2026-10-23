from flask import abort, g, url_for
from flask_login import current_user
from sqlalchemy.exc import IntegrityError

from backend import db
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.app_logger import safe_add_many_logs, warning_log
from backend.extensions.metrics.writer import record_event
from backend.metrics.events import EventName
from backend.models.short_links import Short_Links
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.schemas.errors import build_message_error_response
from backend.schemas.short_links import ShortLinkResponseSchema
from backend.short_links.code_generator import generate_short_link_code
from backend.short_links.constants import (
    SHORT_LINK_MINT_MAX_ATTEMPTS,
    SHORT_LINK_TTL,
    UNIQUE_SHORT_LINK_CODE,
    UNIQUE_SHORT_LINK_PER_UTUB_URL,
)
from backend.urls.constants import URLErrorCodes
from backend.urls.permissions import can_revoke_short_link
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.short_link_strs import (
    SHORT_LINK_FAILURE,
    SHORT_LINK_SUCCESS,
)
from backend.utubs.guards import (
    UtubAccess,
    get_utub_member_ids,
    lock_and_reauthorize,
)


def _lock_existing_short_link(*, utub_url_id: int) -> Short_Links | None:
    """Select the URL's ``ShortLinks`` row ``FOR UPDATE``, refreshing any cached copy."""
    return (
        Short_Links.query.populate_existing()
        .with_for_update()
        .filter(Short_Links.utub_url_id == utub_url_id)
        .one_or_none()
    )


def _violated_constraint(error: IntegrityError) -> str | None:
    """Return the name of the constraint a Postgres ``IntegrityError`` violated, if known."""
    diagnostics = getattr(error.orig, "diag", None)
    return getattr(diagnostics, "constraint_name", None)


def _build_short_link_response(
    *,
    short_link: Short_Links,
    utub_url: Utub_Urls,
    created: bool,
) -> FlaskResponse:
    member_ids: set[int] = get_utub_member_ids(utub_id=utub_url.utub_id)
    can_revoke: bool = can_revoke_short_link(
        adder_id=utub_url.user_id,
        minter_id=short_link.created_by,
        user_id=current_user.id,
        is_manager=g.is_manager,
        member_ids=member_ids,
    )
    return APIResponse(
        message=(
            SHORT_LINK_SUCCESS.SHORT_LINK_CREATED
            if created
            else SHORT_LINK_SUCCESS.SHORT_LINK_REUSED
        ),
        data=ShortLinkResponseSchema(
            short_url=url_for(
                "short_links.resolve_short_link",
                code=short_link.code,
                _external=True,
            ),
            expires_at=short_link.expires_at,
            can_revoke=can_revoke,
            created=created,
        ),
    ).to_response()


def mint_short_link_for_utub_url(
    *, current_utub: Utubs, current_utub_url: Utub_Urls
) -> FlaskResponse:
    """Return the active share link for a UTub URL, making one when none is active.

    Lock order (pinned, matches the repo's documented order): the ``Utubs`` row first
    (``lock_and_reauthorize``: fresh membership, trashed -> 404, locked -> 403), then
    the ``Utub_Urls`` row ``FOR UPDATE`` (re-checked for trash), then the ``ShortLinks``
    row. Holding the first two serializes the mint against UTub trash, URL trash and
    URL address edits, so a link can never be inserted after the transaction that kills
    it has deleted the URL's links.

    Outcomes: an active row is returned unchanged (``created`` false); an expired row is
    overwritten with a new code and TTL; no row inserts one. The insert runs in a
    savepoint: a ``unique_short_link_per_utub_url`` violation (a concurrent first mint)
    returns the winner's row with ``created`` false, a ``unique_short_link_code``
    violation retries with a new code up to ``SHORT_LINK_MINT_MAX_ATTEMPTS`` times, and
    any other integrity error propagates.

    Args:
        current_utub (Utubs): The UTub loaded (unlocked) by the route guard.
        current_utub_url (Utub_Urls): The URL loaded (unlocked) by the route guard.

    Returns:
        FlaskResponse: 200 with the link, a 403 when the UTub is locked, or the generic
        500 when every code attempt collided (no row written).
    """
    locked_response: FlaskResponse | None = lock_and_reauthorize(
        current_utub,
        required_access=UtubAccess.MEMBER,
        error_code=URLErrorCodes.UTUB_IS_LOCKED,
    )
    if locked_response is not None:
        db.session.rollback()
        return locked_response

    utub_url: Utub_Urls | None = (
        Utub_Urls.query.populate_existing()
        .with_for_update()
        .filter(
            Utub_Urls.id == current_utub_url.id,
            Utub_Urls.utub_id == current_utub.id,
        )
        .one_or_none()
    )
    if utub_url is None or utub_url.is_trashed:
        db.session.rollback()
        abort(404)

    existing: Short_Links | None = _lock_existing_short_link(utub_url_id=utub_url.id)
    if existing is not None and not existing.is_expired():
        response = _build_short_link_response(
            short_link=existing, utub_url=utub_url, created=False
        )
        db.session.rollback()
        return response

    # Capture ids up front: commit and rollback both expire the instances.
    user_id: int = current_user.id
    utub_id: int = current_utub.id
    utub_url_id: int = utub_url.id

    for _ in range(SHORT_LINK_MINT_MAX_ATTEMPTS):
        now = utc_now()
        code: str = generate_short_link_code()
        try:
            with db.session.begin_nested():
                if existing is not None:
                    existing.code = code
                    existing.created_by = current_user.id
                    existing.created_at = now
                    existing.expires_at = now + SHORT_LINK_TTL
                    short_link = existing
                else:
                    short_link = Short_Links(
                        utub_url_id=utub_url.id,
                        code=code,
                        created_by=current_user.id,
                        expires_at=now + SHORT_LINK_TTL,
                    )
                    db.session.add(short_link)
        except IntegrityError as integrity_error:
            constraint: str | None = _violated_constraint(integrity_error)
            if constraint == UNIQUE_SHORT_LINK_CODE:
                continue
            if constraint != UNIQUE_SHORT_LINK_PER_UTUB_URL:
                db.session.rollback()
                raise
            # A concurrent first mint inserted the row: return the winner's link.
            # Defense in depth: the Utub_Urls row lock above already serializes mints.
            existing = _lock_existing_short_link(utub_url_id=utub_url.id)
            if existing is not None and not existing.is_expired():
                response = _build_short_link_response(
                    short_link=existing, utub_url=utub_url, created=False
                )
                db.session.rollback()
                return response
            continue

        response = _build_short_link_response(
            short_link=short_link, utub_url=utub_url, created=True
        )
        db.session.commit()
        record_event(EventName.SHORT_LINK_MINTED)
        safe_add_many_logs(
            [
                "Minted short link",
                f"User.id={user_id}",
                f"UTub.id={utub_id}",
                f"UTubURL.id={utub_url_id}",
            ]
        )
        return response

    db.session.rollback()
    warning_log(
        f"Short link code attempts exhausted | UTub.id={utub_id} "
        f"| UTubURL.id={utub_url_id}"
    )
    return build_message_error_response(
        message=SHORT_LINK_FAILURE.SOMETHING_WENT_WRONG, status_code=500
    )
