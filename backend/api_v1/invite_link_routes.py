"""
Bearer-token (/api/v1) wrapper routes for UTub invite links.

Each route is an exact twin of its web counterpart (backend/invite_links/routes.py),
with three changes:
  - Session decorator → api_ equivalent
  - ajax_required=False (no X-Requested-With sentinel)
  - tags=[OPEN_API.MOBILE_API] + 401 added to status_codes

Create and replace share the web routes' per-manager rate-limit scope.
"""

from backend import limiter
from backend.api_common.auth_decorators import api_utub_manager_required
from backend.api_common.parse_request import api_route
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.api_v1.routes import api_v1
from backend.invite_links.constants import (
    INVITE_LINK_MANAGE_RATE_LIMIT,
    INVITE_LINK_MANAGE_RATE_SCOPE,
    InviteLinkErrorCodes,
)
from backend.invite_links.rate_limit import invite_link_manage_rate_key
from backend.invite_links.responses import no_store
from backend.invite_links.services.manage_invite_link import (
    create_invite_link_for_utub,
    read_invite_link,
    replace_invite_link_for_utub,
    revoke_invite_link_for_utub,
    update_invite_link_for_utub,
)
from backend.models.utubs import Utubs
from backend.schemas.base import StatusMessageResponseSchema
from backend.schemas.errors import ErrorResponse
from backend.schemas.invite_links import InviteLinkResponseSchema
from backend.schemas.requests.invite_links import (
    InviteLinkSettingsRequest,
    UpdateInviteLinkRequest,
)
from backend.utils.strings.invite_link_strs import INVITE_LINK_FAILURE
from backend.utils.strings.openapi_strs import OPEN_API


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
