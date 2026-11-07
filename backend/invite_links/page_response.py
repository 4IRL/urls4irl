"""Response helpers for the public invite page.

A leaf module: it imports only flask, ``backend.utils.*`` and
``backend.invite_links.constants`` so the global error handlers can import it without a
cycle. Keep ``backend.invite_links.services`` and the models out of it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from urllib.parse import quote, urlencode

from flask import Response, make_response, redirect, render_template, request

from backend.utils.constants import provide_config_for_constants
from backend.utils.strings.config_strs import CONFIG_ENVS
from backend.utils.strings.invite_link_strs import INVITE_LINK_PAGE

_INVITE_PAGE_TEMPLATE = "pages/invite.html"
_INVITE_PATH_PREFIX = "/invite/"

InvitePageKind = Literal["join_ready", "login_required", "dead", "error"]


@dataclass(frozen=True)
class InvitePageView:
    """Everything ``pages/invite.html`` renders; no UTub detail unless set here."""

    kind: InvitePageKind
    page_title: str
    inviter: str | None = None
    utub_name: str | None = None
    utub_description: str | None = None
    login_url: str | None = None
    register_url: str | None = None
    join_url: str | None = None
    message: str | None = None
    message_role: Literal["alert", "status"] | None = None
    heading: str | None = None
    back_url: str | None = None
    show_home_link: bool = False


def _stamp_privacy_headers(response: Response) -> Response:
    response.headers[CONFIG_ENVS.REFERRER_POLICY] = CONFIG_ENVS.NO_REFERRER_POLICY_VALUE
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    response.headers["Cache-Control"] = "no-store"
    return response


def render_invite_page(*, page: InvitePageView, status_code: int) -> Response:
    """Render the invite page and stamp the privacy headers on it.

    The anonymous shell constants are passed explicitly (not via a blueprint context
    processor, since this blueprint also serves JSON routes).

    Args:
        page (InvitePageView): What the page shows.
        status_code (int): The HTTP status of the response.
    """
    response: Response = make_response(
        render_template(
            _INVITE_PAGE_TEMPLATE,
            is_invite_page=True,
            page=page,
            page_title=page.page_title,
            invite_strings=INVITE_LINK_PAGE,
            **provide_config_for_constants(anonymous=True),
        ),
        status_code,
    )
    return _stamp_privacy_headers(response)


def invite_redirect(location: str) -> Response:
    """A 302 to ``location`` carrying the same privacy headers as the page."""
    return _stamp_privacy_headers(redirect(location, code=302))


def back_to_invite_url() -> str:
    """The invite page URL for the current join request: its path minus ``/join``.

    Derived from the request path only (never ``view_args``), so it is the viewer's
    own URL and never a link to ``/``.
    """
    return quote(request.path.removesuffix("/join"), safe="/")


def build_join_error_view(*, status_code: int) -> InvitePageView:
    """The invite-scoped CSRF (403) or rate-limit (429) page: no invite details.

    Args:
        status_code (int): 403 for a CSRF failure; anything else is the 429 page.
    """
    is_csrf = status_code == 403
    return InvitePageView(
        kind="error",
        page_title=INVITE_LINK_PAGE.TITLE_CSRF
        if is_csrf
        else INVITE_LINK_PAGE.TITLE_RATE_LIMIT,
        heading=INVITE_LINK_PAGE.CSRF_HEADING
        if is_csrf
        else INVITE_LINK_PAGE.RATE_LIMIT_HEADING,
        message=INVITE_LINK_PAGE.CSRF_MESSAGE
        if is_csrf
        else INVITE_LINK_PAGE.RATE_LIMIT_MESSAGE,
        message_role="alert",
        back_url=back_to_invite_url(),
    )


def build_invite_splash_urls(token: str) -> tuple[str, str]:
    """Return the (log in, create account) splash URLs that carry the invite.

    Args:
        token (str): The invite token from the request path.
    """
    login_path = f"{_INVITE_PATH_PREFIX}{token}"
    register_path = f"{login_path}/register"
    return (
        "/?" + urlencode({"next": login_path}, safe="/"),
        "/?" + urlencode({"next": register_path}, safe="/"),
    )
