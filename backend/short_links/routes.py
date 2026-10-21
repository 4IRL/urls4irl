from http import HTTPStatus

from flask import Blueprint, Response, make_response, render_template

from backend import limiter
from backend.api_common.parse_request import api_route
from backend.extensions.metrics.writer import record_event
from backend.metrics.events import EventName
from backend.schemas.base import HtmlErrorPageSchema
from backend.short_links.constants import SHORT_LINK_RESOLVE_RATE_LIMIT
from backend.short_links.services.resolve_short_link import (
    ShortLinkDestination,
    find_live_destination,
)
from backend.utils.constants import provide_config_for_constants
from backend.utils.strings.config_strs import CONFIG_ENVS
from backend.utils.strings.openapi_strs import OPEN_API

short_links = Blueprint("short_links", __name__)

_SHORT_LINK_PAGE_TEMPLATE = "pages/short_link.html"


@short_links.context_processor
def provide_constants() -> dict:
    # The share page renders one neutral shell for every viewer (anonymous or logged
    # in), so the per-user parts (theme, config) are forced to the anonymous values.
    return provide_config_for_constants(anonymous=True)


def _share_page_response(
    *, status_code: int, destination: ShortLinkDestination | None = None
) -> Response:
    """Render the share page and stamp the privacy headers on it.

    Args:
        status_code (int): 200 for the confirmation page, 404 for the dead-link page.
        destination (ShortLinkDestination | None): What the confirmation page shows.
            Only its URL and host reach the template; nothing about the UTub does.
    """
    context: dict[str, str] = (
        {
            "destination_url": destination.destination_url,
            "destination_host": destination.destination_host,
        }
        if destination is not None
        else {}
    )
    response: Response = make_response(
        render_template(_SHORT_LINK_PAGE_TEMPLATE, is_short_link_page=True, **context),
        status_code,
    )
    response.headers[CONFIG_ENVS.REFERRER_POLICY] = CONFIG_ENVS.NO_REFERRER_POLICY_VALUE
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    response.headers["Cache-Control"] = "no-store"
    return response


@short_links.route("/s/<code>", methods=["GET"])
@api_route(
    ajax_required=False,
    tags=[OPEN_API.URLS],
    description=(
        "Public share-link landing page. Shows a confirmation page (200) with the "
        "destination and a Continue link for a live link, never a redirect. Every "
        "dead, malformed, expired, trashed or locked code returns the same 404 page."
    ),
    status_codes={200: HtmlErrorPageSchema, 404: HtmlErrorPageSchema},
)
@limiter.limit(SHORT_LINK_RESOLVE_RATE_LIMIT)
def resolve_short_link(code: str) -> Response:
    """Public share-link landing route (no login).

    Args:
        code (str): The short link code from the URL.
    """
    destination: ShortLinkDestination | None = find_live_destination(code)
    if destination is None:
        return _share_page_response(status_code=HTTPStatus.NOT_FOUND)
    record_event(EventName.SHORT_LINK_RESOLVED)
    return _share_page_response(status_code=HTTPStatus.OK, destination=destination)
