from flask import g
from flask_login import current_user

from backend import db
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.app_logger import critical_log, safe_add_many_logs
from backend.extensions.metrics.writer import record_event
from backend.metrics.events import EventName
from backend.models.short_links import Short_Links
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.schemas.errors import build_message_error_response
from backend.schemas.short_links import ShortLinkRevokedResponseSchema
from backend.short_links.constants import ShortLinkErrorCodes
from backend.urls.permissions import can_revoke_short_link
from backend.utils.strings.short_link_strs import (
    SHORT_LINK_FAILURE,
    SHORT_LINK_SUCCESS,
)
from backend.utubs.guards import get_utub_member_ids


def revoke_short_link_for_utub_url(
    *, current_utub: Utubs, current_utub_url: Utub_Urls
) -> FlaskResponse:
    """Hard-delete a UTub URL's share link when the caller is allowed to revoke it.

    Allowed on admin-locked UTubs (revoking is the safe direction), so there is no
    lock check. The route guard already proved membership and that the URL is live.

    Args:
        current_utub (Utubs): The UTub loaded by the route guard.
        current_utub_url (Utub_Urls): The URL loaded by the route guard.

    Returns:
        FlaskResponse: 200 when revoked; 404 with ``SHORT_LINK_NOT_FOUND`` when there
        is no active link; 403 when the caller may not revoke it.
    """
    short_link: Short_Links | None = (
        Short_Links.query.populate_existing()
        .with_for_update()
        .filter(Short_Links.utub_url_id == current_utub_url.id)
        .one_or_none()
    )
    if short_link is None or short_link.is_expired():
        db.session.rollback()
        return build_message_error_response(
            message=SHORT_LINK_FAILURE.SHORT_LINK_NOT_FOUND,
            error_code=ShortLinkErrorCodes.SHORT_LINK_NOT_FOUND,
            status_code=404,
        )

    member_ids: set[int] = get_utub_member_ids(utub_id=current_utub.id)
    if not can_revoke_short_link(
        adder_id=current_utub_url.user_id,
        minter_id=short_link.created_by,
        user_id=current_user.id,
        is_manager=g.is_manager,
        member_ids=member_ids,
    ):
        db.session.rollback()
        critical_log(
            f"User={current_user.id} not allowed to revoke short link: "
            f"UTubURL.id={current_utub_url.id} in UTub.id={current_utub.id}"
        )
        return build_message_error_response(
            message=SHORT_LINK_FAILURE.UNABLE_TO_REVOKE, status_code=403
        )

    # Capture ids before commit: commit expires the instances.
    utub_url_id: int = current_utub_url.id
    utub_id: int = current_utub.id
    user_id: int = current_user.id
    db.session.delete(short_link)
    db.session.commit()

    record_event(EventName.SHORT_LINK_REVOKED)
    safe_add_many_logs(
        [
            "Revoked short link",
            f"User.id={user_id}",
            f"UTub.id={utub_id}",
            f"UTubURL.id={utub_url_id}",
        ]
    )

    return APIResponse(
        message=SHORT_LINK_SUCCESS.SHORT_LINK_REVOKED,
        data=ShortLinkRevokedResponseSchema(utub_url_id=utub_url_id),
    ).to_response()
