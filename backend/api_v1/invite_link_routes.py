"""
Bearer-token (/api/v1) wrapper routes for UTub invite links.

Each route is an exact twin of its web counterpart (backend/invite_links/routes.py),
with three changes:
  - Session decorator → api_ equivalent
  - ajax_required=False (no X-Requested-With sentinel)
  - tags=[OPEN_API.MOBILE_API] + 401 added to status_codes

Create and replace share the web routes' per-manager rate-limit scope.
"""

from flask_login import current_user

from backend import limiter
from backend.api_common.auth_decorators import (
    api_email_validation_required,
    api_utub_manager_required,
)
from backend.api_common.parse_request import api_route
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.api_v1.routes import api_v1
from backend.invite_links.constants import (
    INVITE_LINK_JOIN_RATE_LIMIT,
    INVITE_LINK_JOIN_RATE_SCOPE,
    INVITE_LINK_MANAGE_RATE_LIMIT,
    INVITE_LINK_MANAGE_RATE_SCOPE,
    InviteJoinOutcome,
    InviteLinkErrorCodes,
)
from backend.invite_links.data_models import InviteJoinResult
from backend.invite_links.lookup import find_invite_by_token
from backend.invite_links.rate_limit import (
    invite_link_join_rate_key,
    invite_link_manage_rate_key,
)
from backend.invite_links.responses import no_store
from backend.invite_links.services.join_via_invite import join_via_invite
from backend.invite_links.services.manage_invite_link import (
    create_invite_link_for_utub,
    read_invite_link,
    replace_invite_link_for_utub,
    revoke_invite_link_for_utub,
    update_invite_link_for_utub,
)
from backend.models.utubs import Utubs
from backend.schemas.base import StatusMessageResponseSchema
from backend.schemas.errors import ErrorResponse, build_message_error_response
from backend.schemas.invite_links import (
    InviteLinkResponseSchema,
    JoinViaInviteResponseSchema,
)
from backend.schemas.requests.invite_links import (
    InviteLinkSettingsRequest,
    UpdateInviteLinkRequest,
)
from backend.utils.strings.api_auth_strs import API_AUTH_FAILURE
from backend.utils.strings.invite_link_strs import (
    INVITE_LINK_FAILURE,
    INVITE_LINK_SUCCESS,
)
from backend.utils.strings.json_strs import FAILURE_GENERAL
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.openapi_strs import OPEN_API


def map_join_result(result: InviteJoinResult) -> FlaskResponse:
    """Map a join outcome to its response. Fails closed: anything unhandled is the
    uniform dead 404, never a success."""
    outcome = result.outcome
    if outcome == InviteJoinOutcome.JOINED and result.utub_id is not None:
        return APIResponse(
            message=INVITE_LINK_SUCCESS.JOINED,
            status_code=200,
            data=JoinViaInviteResponseSchema(
                status=STD_JSON.SUCCESS,
                message=INVITE_LINK_SUCCESS.JOINED,
                utub_id=result.utub_id,
                already_member=False,
            ),
        ).to_response()
    if outcome == InviteJoinOutcome.ALREADY_MEMBER and result.utub_id is not None:
        return APIResponse(
            message=INVITE_LINK_SUCCESS.ALREADY_MEMBER,
            status_code=200,
            data=JoinViaInviteResponseSchema(
                status=STD_JSON.SUCCESS,
                message=INVITE_LINK_SUCCESS.ALREADY_MEMBER,
                utub_id=result.utub_id,
                already_member=True,
            ),
        ).to_response()
    if outcome == InviteJoinOutcome.ACTOR_UNVALIDATED:
        return build_message_error_response(
            message=API_AUTH_FAILURE.EMAIL_VALIDATION_REQUIRED, status_code=403
        )
    return build_message_error_response(
        message=FAILURE_GENERAL.NOT_FOUND, status_code=404
    )


@api_v1.route("/invite/<token>/join", methods=["POST"])
@api_email_validation_required
@api_route(
    response_schema=JoinViaInviteResponseSchema,
    ajax_required=False,
    tags=[OPEN_API.MOBILE_API],
    description=(
        "Join the UTub an invite link belongs to. Every dead, unknown or malformed "
        "link is the same 404."
    ),
    status_codes={
        200: JoinViaInviteResponseSchema,
        401: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
        429: ErrorResponse,
    },
)
@limiter.shared_limit(
    INVITE_LINK_JOIN_RATE_LIMIT,
    scope=INVITE_LINK_JOIN_RATE_SCOPE,
    key_func=invite_link_join_rate_key,
    methods=["POST"],
)
def api_v1_join_via_invite(token: str) -> FlaskResponse:
    """Join the caller to the invite's UTub."""
    invite = find_invite_by_token(token)
    if invite is None:
        return map_join_result(
            InviteJoinResult(outcome=InviteJoinOutcome.DEAD, utub_id=None)
        )
    return map_join_result(join_via_invite(current_user, invite))


@api_v1.route("/utubs/<int:utub_id>/invite-link", methods=["GET"])
@api_utub_manager_required
@api_route(
    response_schema=InviteLinkResponseSchema,
    ajax_required=False,
    error_code=InviteLinkErrorCodes.INVALID_FORM_INPUT,
    tags=[OPEN_API.MOBILE_API],
    description=(
        "Get the UTub's current invite link and its status, or null when there is "
        "none (owner and co-owner only)"
    ),
    status_codes={
        200: InviteLinkResponseSchema,
        401: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def api_v1_get_invite_link(utub_id: int, current_utub: Utubs) -> FlaskResponse:
    """Return the UTub's unrevoked invite link, readable in any UTub state."""
    return no_store(
        APIResponse(data=read_invite_link(current_utub), status_code=200).to_response()
    )


@api_v1.route("/utubs/<int:utub_id>/invite-link", methods=["POST"])
@api_utub_manager_required
@api_route(
    request_schema=InviteLinkSettingsRequest,
    response_schema=InviteLinkResponseSchema,
    ajax_required=False,
    error_message=INVITE_LINK_FAILURE.INVALID_FORM_INPUT,
    error_code=InviteLinkErrorCodes.INVALID_FORM_INPUT,
    tags=[OPEN_API.MOBILE_API],
    description=(
        "Create the UTub's invite link with an expiry and an optional use limit "
        "(owner and co-owner only). A dead unrevoked link is revoked first."
    ),
    status_codes={
        201: InviteLinkResponseSchema,
        400: ErrorResponse,
        401: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
        409: ErrorResponse,
        429: ErrorResponse,
    },
)
@limiter.shared_limit(
    INVITE_LINK_MANAGE_RATE_LIMIT,
    scope=INVITE_LINK_MANAGE_RATE_SCOPE,
    key_func=invite_link_manage_rate_key,
    methods=["POST"],
)
def api_v1_create_invite_link(
    utub_id: int,
    current_utub: Utubs,
    invite_link_settings_request: InviteLinkSettingsRequest,
) -> FlaskResponse:
    """Create the UTub's invite link."""
    return no_store(
        create_invite_link_for_utub(
            current_utub=current_utub, settings=invite_link_settings_request
        )
    )


@api_v1.route("/utubs/<int:utub_id>/invite-link", methods=["PATCH"])
@api_utub_manager_required
@api_route(
    request_schema=UpdateInviteLinkRequest,
    response_schema=InviteLinkResponseSchema,
    ajax_required=False,
    error_message=INVITE_LINK_FAILURE.INVALID_FORM_INPUT,
    error_code=InviteLinkErrorCodes.INVALID_FORM_INPUT,
    tags=[OPEN_API.MOBILE_API],
    description=(
        "Change the expiry and/or use limit of the UTub's live invite link "
        "(owner and co-owner only). An absent field is unchanged; a null "
        "max_uses means unlimited."
    ),
    status_codes={
        200: InviteLinkResponseSchema,
        400: ErrorResponse,
        401: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
        409: ErrorResponse,
    },
)
def api_v1_update_invite_link(
    utub_id: int,
    current_utub: Utubs,
    update_invite_link_request: UpdateInviteLinkRequest,
) -> FlaskResponse:
    """Update the UTub's live invite link."""
    return no_store(
        update_invite_link_for_utub(
            current_utub=current_utub, update=update_invite_link_request
        )
    )


@api_v1.route("/utubs/<int:utub_id>/invite-link/replace", methods=["POST"])
@api_utub_manager_required
@api_route(
    request_schema=InviteLinkSettingsRequest,
    response_schema=InviteLinkResponseSchema,
    ajax_required=False,
    error_message=INVITE_LINK_FAILURE.INVALID_FORM_INPUT,
    error_code=InviteLinkErrorCodes.INVALID_FORM_INPUT,
    tags=[OPEN_API.MOBILE_API],
    description=(
        "Revoke the UTub's invite link and create a new one with the given "
        "settings (owner and co-owner only)"
    ),
    status_codes={
        201: InviteLinkResponseSchema,
        400: ErrorResponse,
        401: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
        429: ErrorResponse,
    },
)
@limiter.shared_limit(
    INVITE_LINK_MANAGE_RATE_LIMIT,
    scope=INVITE_LINK_MANAGE_RATE_SCOPE,
    key_func=invite_link_manage_rate_key,
    methods=["POST"],
)
def api_v1_replace_invite_link(
    utub_id: int,
    current_utub: Utubs,
    invite_link_settings_request: InviteLinkSettingsRequest,
) -> FlaskResponse:
    """Replace the UTub's invite link with a new one."""
    return no_store(
        replace_invite_link_for_utub(
            current_utub=current_utub, settings=invite_link_settings_request
        )
    )


@api_v1.route("/utubs/<int:utub_id>/invite-link", methods=["DELETE"])
@api_utub_manager_required
@api_route(
    response_schema=StatusMessageResponseSchema,
    ajax_required=False,
    error_code=InviteLinkErrorCodes.INVITE_LINK_NOT_FOUND,
    tags=[OPEN_API.MOBILE_API],
    description="Revoke the UTub's invite link (owner and co-owner only)",
    status_codes={
        200: StatusMessageResponseSchema,
        401: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def api_v1_revoke_invite_link(utub_id: int, current_utub: Utubs) -> FlaskResponse:
    """Revoke the UTub's invite link."""
    return revoke_invite_link_for_utub(current_utub=current_utub)
