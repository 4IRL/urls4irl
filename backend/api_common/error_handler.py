from flask import render_template, request
from flask_login import current_user
from flask_wtf.csrf import CSRFError
from werkzeug.exceptions import NotFound

from backend.app_logger import warning_log
from backend.schemas.errors import build_message_error_response
from backend.utils.constants import build_frontend_config
from backend.utils.strings.api_auth_strs import API_V1_URL_PREFIX
from backend.utils.strings.html_identifiers import IDENTIFIERS
from backend.utils.strings.json_strs import FAILURE_GENERAL, STD_JSON_RESPONSE
from backend.utils.strings.url_validation_strs import URL_VALIDATION


def _is_api_v1_request() -> bool:
    """True when the current request targets the bearer-token /api/v1 surface.

    Checked in the app-level handlers because an unmatched /api/v1 path never
    enters any blueprint, so blueprint-scoped errorhandlers cannot catch it —
    API clients must receive JSON regardless of their Accept header.
    """
    return request.path.startswith(API_V1_URL_PREFIX)


def _render_error_page(*, error_code: int, header: str) -> tuple[str, int]:
    """Render the standalone HTML error page.

    CONFIG is passed explicitly: the page's `error.ts` imports metrics-client →
    `lib/config.ts`, which throws at import time without `#app-config`, and an
    app-level error handler (e.g. a 404 on an unmatched path) has no blueprint
    context processor to supply it.
    """
    return (
        render_template(
            "error_pages/error_response.html",
            error_code=error_code,
            header=header,
            CONFIG=build_frontend_config(),
            reload_safe=_is_reload_safe_request(),
        ),
        error_code,
    )


def _is_reload_safe_request() -> bool:
    """Whether the error page's refresh button can simply reload the current URL.

    A full-page GET/HEAD can be re-requested. An AJAX request's error page is
    written over the GET-loaded page that issued it, so the browser URL is that
    page and reloading it is safe too. Only a full-page non-GET navigation (e.g.
    a form POST to /login) leaves the browser on a URL that would 405 on reload.
    """
    return request.method in ("GET", "HEAD") or (
        request.headers.get(URL_VALIDATION.X_REQUESTED_WITH)
        == URL_VALIDATION.XMLHTTPREQUEST
    )


def handle_403_response_from_csrf(csrf_error: CSRFError):
    user_id = -1 if not current_user.is_authenticated else current_user.id
    warning_log(f"CSRF validation failed for User={user_id}: {csrf_error.description}")
    if _is_api_v1_request():
        return build_message_error_response(
            message=FAILURE_GENERAL.NOT_AUTHORIZED, status_code=403
        )
    return _render_error_page(error_code=403, header=IDENTIFIERS.HTML_403)


def handle_404_response(_: NotFound):
    if _is_api_v1_request() or (
        request.headers.get(URL_VALIDATION.X_REQUESTED_WITH)
        == URL_VALIDATION.XMLHTTPREQUEST
    ):
        return build_message_error_response(
            message=FAILURE_GENERAL.NOT_FOUND, status_code=404
        )

    return _render_error_page(error_code=404, header=IDENTIFIERS.HTML_404)


def handle_429_response_default_ratelimit(_):
    # Only /api/v1 (bearer-token) clients get a JSON 429. Web AJAX requests
    # deliberately receive the HTML 429 page: the global `$.ajaxPrefilter` in
    # `frontend/lib/csrf.ts` detects a text/html 429 and performs a full-page
    # replacement (`showNewPageOnAJAXHTMLResponse`), which every splash/home/utub
    # form's `.fail()` handler and the `*_rate_limits` UI tests rely on. Returning
    # JSON here (as a 404-style dual-check would) leaves the page unreplaced and
    # the rate-limit UX silently broken. Unlike 404, 429 has no JSON web consumer.
    if _is_api_v1_request():
        return build_message_error_response(
            message=STD_JSON_RESPONSE.TOO_MANY_REQUESTS, status_code=429
        )
    return _render_error_page(error_code=429, header=IDENTIFIERS.HTML_429)
