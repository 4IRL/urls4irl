from http import HTTPStatus

from flask import Blueprint, Response, url_for
from flask_login import current_user

from backend import limiter
from backend.api_common.auth_decorators import utub_manager_required
from backend.api_common.parse_request import api_route
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.extensions.metrics.writer import record_event
from backend.invite_links.constants import (
    INVITE_LINK_JOIN_RATE_LIMIT,
    INVITE_LINK_JOIN_RATE_SCOPE,
    INVITE_LINK_MANAGE_RATE_LIMIT,
    INVITE_LINK_MANAGE_RATE_SCOPE,
    INVITE_LINK_PAGE_RATE_LIMIT,
    InviteJoinOutcome,
    InviteLinkErrorCodes,
)
from backend.invite_links.data_models import (
    InviteJoinResult,
    InvitePageResolution,
    InvitePageState,
)
from backend.invite_links.lookup import find_invite_by_token
from backend.invite_links.page_response import (
    InvitePageView,
    build_invite_splash_urls,
    invite_redirect,
    render_invite_page,
)
from backend.invite_links.rate_limit import (
    invite_link_join_rate_key,
    invite_link_manage_rate_key,
)
from backend.invite_links.responses import no_store
from backend.invite_links.services.invite_page import resolve_invite_page
from backend.invite_links.services.join_via_invite import join_via_invite
from backend.invite_links.services.manage_invite_link import (
    create_invite_link_for_utub,
    read_invite_link,
    replace_invite_link_for_utub,
    revoke_invite_link_for_utub,
    update_invite_link_for_utub,
)
from backend.metrics.events import EventName
from backend.models.users import Users
from backend.models.utubs import Utubs
from backend.schemas.base import HtmlErrorPageSchema, StatusMessageResponseSchema
from backend.schemas.errors import ErrorResponse
from backend.schemas.invite_links import InviteLinkResponseSchema
from backend.schemas.requests.invite_links import (
    InviteLinkSettingsRequest,
    UpdateInviteLinkRequest,
)
from backend.utils.all_routes import INVITE_LINK_ROUTES
from backend.utils.strings.invite_link_strs import INVITE_LINK_FAILURE, INVITE_LINK_PAGE
from backend.utils.strings.openapi_strs import OPEN_API

invite_links = Blueprint("invite_links", __name__)


def _build_page_view(
    *,
    resolution: InvitePageResolution,
    token: str,
    show_login_message: bool = False,
) -> InvitePageView:
    """Map a classifier resolution to the view the template renders (never a member).

    Args:
        resolution (InvitePageResolution): The classifier's result.
        token (str): The raw token from the request path (for the splash URLs).
        show_login_message (bool): Whether state 2 carries the "log in" message
            (the join POST re-render for a logged-out visitor).
    """
    invite = resolution.invite
    if resolution.state in (
        InvitePageState.JOIN_READY,
        InvitePageState.LOGIN_REQUIRED,
    ) and (invite is not None and invite.creator is not None):
        login_url, register_url = build_invite_splash_urls(token)
        is_join_ready = resolution.state == InvitePageState.JOIN_READY
        login_message = (
            INVITE_LINK_PAGE.LOGIN_MESSAGE
            if show_login_message and not is_join_ready
            else None
        )
        return InvitePageView(
            kind="join_ready" if is_join_ready else "login_required",
            page_title=INVITE_LINK_PAGE.TITLE_JOIN,
            inviter=invite.creator.username,
            utub_name=invite.utub.name,
            utub_description=invite.utub.utub_description or None,
            login_url=None if is_join_ready else login_url,
            register_url=None if is_join_ready else register_url,
            join_url=(
                url_for(INVITE_LINK_ROUTES.JOIN_INVITE_PAGE, token=token)
                if is_join_ready
                else None
            ),
            message=login_message,
            message_role="status" if login_message else None,
        )
    # Fail closed: every other state, and any state missing its details, is dead.
    return InvitePageView(
        kind="dead",
        page_title=INVITE_LINK_PAGE.TITLE_DEAD,
        show_home_link=True,
    )


@invite_links.route("/invite/<token>", methods=["GET"])
@api_route(
    ajax_required=False,
    tags=[OPEN_API.MEMBERS],
    description=(
        "Public invite-link landing page. Shows who invited the visitor to which "
        "UTub (200) for a live link and redirects a member into the UTub (302). "
        "Every dead, unknown or malformed token returns the same 404 page."
    ),
    status_codes={
        200: HtmlErrorPageSchema,
        302: HtmlErrorPageSchema,
        404: HtmlErrorPageSchema,
        429: HtmlErrorPageSchema,
    },
)
@limiter.limit(INVITE_LINK_PAGE_RATE_LIMIT)
def invite_page(token: str) -> Response:
    """Public invite landing route (no login required); never mutates.

    Args:
        token (str): The invite token from the URL.
    """
    visitor: Users | None = current_user if current_user.is_authenticated else None
    resolution = resolve_invite_page(visitor=visitor, token=token)

    if resolution.state == InvitePageState.MEMBER_REDIRECT:
        viewer_state = "member"
    elif visitor is not None:
        viewer_state = "logged_in"
    else:
        viewer_state = "logged_out"
    record_event(
        EventName.INVITE_LINK_VIEWED,
        dimensions={
            "viewer_state": viewer_state,
            "outcome": "valid" if resolution.link_live else "dead",
        },
    )

    if resolution.state == InvitePageState.MEMBER_REDIRECT:
        return invite_redirect(f"/home?UTubID={resolution.utub_id}")

    page = _build_page_view(resolution=resolution, token=token)
    status_code = HTTPStatus.NOT_FOUND if page.kind == "dead" else HTTPStatus.OK
    return render_invite_page(page=page, status_code=status_code)


def _dead_page_response() -> Response:
    page = InvitePageView(
        kind="dead", page_title=INVITE_LINK_PAGE.TITLE_DEAD, show_home_link=True
    )
    return render_invite_page(page=page, status_code=HTTPStatus.NOT_FOUND)


def _join_outcome_response(result: InviteJoinResult) -> Response:
    """Map a join outcome to its response; anything unhandled is the dead page."""
    if (
        result.outcome in (InviteJoinOutcome.JOINED, InviteJoinOutcome.ALREADY_MEMBER)
        and result.utub_id is not None
    ):
        return invite_redirect(f"/home?UTubID={result.utub_id}")
    return _dead_page_response()


@invite_links.route("/invite/<token>/join", methods=["POST"])
@api_route(
    ajax_required=False,
    tags=[OPEN_API.MEMBERS],
    description=(
        "Join the UTub an invite link belongs to from the public invite page's plain "
        "form (CSRF-protected). Redirects into the UTub (302); a dead, unknown or "
        "malformed token is the uniform 404 page, and a logged-out visitor the "
        "log-in page (401)."
    ),
    status_codes={
        302: HtmlErrorPageSchema,
        401: HtmlErrorPageSchema,
        404: HtmlErrorPageSchema,
        429: HtmlErrorPageSchema,
    },
)
@limiter.shared_limit(
    INVITE_LINK_JOIN_RATE_LIMIT,
    scope=INVITE_LINK_JOIN_RATE_SCOPE,
    key_func=invite_link_join_rate_key,
    methods=["POST"],
)
def join_invite_page(token: str) -> Response:
    """Join the logged-in visitor to the invite's UTub; renders every non-success.

    Args:
        token (str): The invite token from the URL.
    """
    if not current_user.is_authenticated:
        resolution = resolve_invite_page(visitor=None, token=token)
        page = _build_page_view(
            resolution=resolution,
            token=token,
            show_login_message=True,
        )
        if page.kind == "login_required":
            return render_invite_page(page=page, status_code=HTTPStatus.UNAUTHORIZED)
        return render_invite_page(page=page, status_code=HTTPStatus.NOT_FOUND)

    invite = find_invite_by_token(token)
    if invite is None:
        return _dead_page_response()
    return _join_outcome_response(join_via_invite(current_user, invite))


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
    return no_store(
        APIResponse(data=read_invite_link(current_utub), status_code=200).to_response()
    )


@invite_links.route("/utubs/<int:utub_id>/invite-link", methods=["POST"])
@utub_manager_required
@api_route(
    request_schema=InviteLinkSettingsRequest,
    response_schema=InviteLinkResponseSchema,
    ajax_required=True,
    error_message=INVITE_LINK_FAILURE.INVALID_FORM_INPUT,
    error_code=InviteLinkErrorCodes.INVALID_FORM_INPUT,
    tags=[OPEN_API.MEMBERS],
    description=(
        "Create the UTub's invite link with an expiry and an optional use limit "
        "(owner and co-owner only). A dead unrevoked link is revoked first."
    ),
    status_codes={
        201: InviteLinkResponseSchema,
        400: ErrorResponse,
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
def create_invite_link(
    utub_id: int,
    current_utub: Utubs,
    invite_link_settings_request: InviteLinkSettingsRequest,
) -> FlaskResponse:
    """
    Create the UTub's invite link.

    Args:
        utub_id (int): The UTub the invite link is created for
    """
    return no_store(
        create_invite_link_for_utub(
            current_utub=current_utub, settings=invite_link_settings_request
        )
    )


@invite_links.route("/utubs/<int:utub_id>/invite-link", methods=["PATCH"])
@utub_manager_required
@api_route(
    request_schema=UpdateInviteLinkRequest,
    response_schema=InviteLinkResponseSchema,
    ajax_required=True,
    error_message=INVITE_LINK_FAILURE.INVALID_FORM_INPUT,
    error_code=InviteLinkErrorCodes.INVALID_FORM_INPUT,
    tags=[OPEN_API.MEMBERS],
    description=(
        "Change the expiry and/or use limit of the UTub's live invite link "
        "(owner and co-owner only). An absent field is unchanged; a null "
        "max_uses means unlimited."
    ),
    status_codes={
        200: InviteLinkResponseSchema,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
        409: ErrorResponse,
    },
)
def update_invite_link(
    utub_id: int,
    current_utub: Utubs,
    update_invite_link_request: UpdateInviteLinkRequest,
) -> FlaskResponse:
    """
    Update the UTub's live invite link.

    Args:
        utub_id (int): The UTub whose invite link is updated
    """
    return no_store(
        update_invite_link_for_utub(
            current_utub=current_utub, update=update_invite_link_request
        )
    )


@invite_links.route("/utubs/<int:utub_id>/invite-link/replace", methods=["POST"])
@utub_manager_required
@api_route(
    request_schema=InviteLinkSettingsRequest,
    response_schema=InviteLinkResponseSchema,
    ajax_required=True,
    error_message=INVITE_LINK_FAILURE.INVALID_FORM_INPUT,
    error_code=InviteLinkErrorCodes.INVALID_FORM_INPUT,
    tags=[OPEN_API.MEMBERS],
    description=(
        "Revoke the UTub's invite link and create a new one with the given "
        "settings (owner and co-owner only)"
    ),
    status_codes={
        201: InviteLinkResponseSchema,
        400: ErrorResponse,
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
def replace_invite_link(
    utub_id: int,
    current_utub: Utubs,
    invite_link_settings_request: InviteLinkSettingsRequest,
) -> FlaskResponse:
    """
    Replace the UTub's invite link with a new one.

    Args:
        utub_id (int): The UTub whose invite link is replaced
    """
    return no_store(
        replace_invite_link_for_utub(
            current_utub=current_utub, settings=invite_link_settings_request
        )
    )


@invite_links.route("/utubs/<int:utub_id>/invite-link", methods=["DELETE"])
@utub_manager_required
@api_route(
    response_schema=StatusMessageResponseSchema,
    ajax_required=True,
    error_code=InviteLinkErrorCodes.INVITE_LINK_NOT_FOUND,
    tags=[OPEN_API.MEMBERS],
    description="Revoke the UTub's invite link (owner and co-owner only)",
    status_codes={
        200: StatusMessageResponseSchema,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def revoke_invite_link(utub_id: int, current_utub: Utubs) -> FlaskResponse:
    """
    Revoke the UTub's invite link.

    Args:
        utub_id (int): The UTub whose invite link is revoked
    """
    return revoke_invite_link_for_utub(current_utub=current_utub)
