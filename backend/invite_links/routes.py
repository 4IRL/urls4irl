from flask import Blueprint

from backend.api_common.auth_decorators import utub_manager_required
from backend.api_common.parse_request import api_route
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.invite_links.constants import InviteLinkErrorCodes
from backend.invite_links.services.manage_invite_link import read_invite_link
from backend.models.utubs import Utubs
from backend.schemas.errors import ErrorResponse
from backend.schemas.invite_links import InviteLinkResponseSchema
from backend.utils.strings.openapi_strs import OPEN_API

invite_links = Blueprint("invite_links", __name__)


def _no_store(response: FlaskResponse) -> FlaskResponse:
    """Stamp ``Cache-Control: no-store`` on a response that carries a token."""
    flask_response, status_code = response
    flask_response.headers["Cache-Control"] = "no-store"
    return flask_response, status_code


@invite_links.route("/utubs/<int:utub_id>/invite-link", methods=["GET"])
@utub_manager_required
@api_route(
    response_schema=InviteLinkResponseSchema,
    ajax_required=True,
    error_code=InviteLinkErrorCodes.INVALID_FORM_INPUT,
    tags=[OPEN_API.MEMBERS],
    description=(
        "Get the UTub's current invite link and its status, or null when there is "
        "none (owner and co-owner only)"
    ),
    status_codes={
        200: InviteLinkResponseSchema,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def get_invite_link(utub_id: int, current_utub: Utubs) -> FlaskResponse:
    """
    Return the UTub's unrevoked invite link, readable in any UTub state.

    Args:
        utub_id (int): The UTub whose invite link is read
    """
    return _no_store(
        APIResponse(data=read_invite_link(current_utub), status_code=200).to_response()
    )
