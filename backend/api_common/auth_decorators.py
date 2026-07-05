from typing import Callable
from flask import abort, g, redirect, session, url_for
from flask_login import login_required, current_user
from functools import wraps

from backend.api_common.request_utils import is_current_utub_creator
from backend.schemas.errors import build_message_error_response
from backend.app_logger import critical_log, warning_log
from backend.models.users import User_Role
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.utils.all_routes import ROUTES
from backend.utils.strings.api_auth_strs import API_AUTH_FAILURE
from backend.utils.strings.email_validation_strs import EMAILS
from backend.utils.strings.utub_strs import UTUB_FAILURE

_NOT_AUTHENTICATED_MESSAGE: str = "Authentication required."
_NOT_FOUND_MESSAGE: str = "Not found."


def no_authenticated_users_allowed(func: Callable) -> Callable:
    @wraps(func)
    def decorated_view(*args, **kwargs) -> Callable:
        if current_user.is_authenticated:
            if not current_user.email_validated:
                warning_log(
                    f"User={current_user.id} registered but not email validated"
                )
                return redirect(url_for(ROUTES.SPLASH.CONFIRM_EMAIL))
            warning_log(f"User={current_user.id} already logged in")
            return redirect(url_for(ROUTES.UTUBS.HOME))

        return func(*args, **kwargs)

    decorated_view._auth_decorator = no_authenticated_users_allowed.__name__
    return decorated_view


def email_validation_required(func: Callable) -> Callable:
    @wraps(func)
    @login_required
    def decorated_view(*args, **kwargs) -> Callable:
        is_email_validated: bool | None = session.get(EMAILS.EMAIL_VALIDATED_SESS_KEY)

        if is_email_validated is None:
            session[EMAILS.EMAIL_VALIDATED_SESS_KEY] = current_user.email_validated
            is_email_validated = session[EMAILS.EMAIL_VALIDATED_SESS_KEY]

        if not is_email_validated:
            return redirect(url_for(ROUTES.SPLASH.SPLASH_PAGE))

        return func(*args, **kwargs)

    decorated_view._auth_decorator = email_validation_required.__name__
    return decorated_view


def utub_membership_required(func: Callable) -> Callable:
    @wraps(func)
    @email_validation_required
    def decorated_view(*args, **kwargs):
        utub_id: int | None = kwargs.get("utub_id")
        if utub_id is None:
            abort(404)

        member: Utub_Members = Utub_Members.query.get_or_404((utub_id, current_user.id))
        g.is_creator = member.member_role in (
            Member_Role.CREATOR,
            Member_Role.CO_CREATOR,
        )
        utub: Utubs = Utubs.query.get_or_404(utub_id)
        g.utub_id = utub.id
        kwargs["current_utub"] = utub

        return func(*args, **kwargs)

    decorated_view._auth_decorator = utub_membership_required.__name__
    return decorated_view


def utub_creator_required(func: Callable) -> Callable:
    @wraps(func)
    @utub_membership_required
    def decorated_view(*args, **kwargs):
        if not is_current_utub_creator():
            utub_id: int = kwargs["utub_id"]
            current_utub: Utubs = kwargs["current_utub"]
            critical_log(
                f"User={current_user.id} not creator: UTub.id={utub_id} | UTub.name={current_utub.name}"
            )

            return build_message_error_response(
                message=UTUB_FAILURE.NOT_AUTHORIZED,
                status_code=403,
            )

        return func(*args, **kwargs)

    decorated_view._auth_decorator = utub_creator_required.__name__
    return decorated_view


def utub_membership_with_valid_url_in_utub_required(func: Callable) -> Callable:
    @wraps(func)
    @utub_membership_required
    def decorated_view(*args, **kwargs):
        utub_url_id: int | None = kwargs.get("utub_url_id")
        if utub_url_id is None:
            abort(404)

        current_utub_url: Utub_Urls = Utub_Urls.query.get_or_404(utub_url_id)
        if current_utub_url.utub_id != g.utub_id:
            critical_log(
                f"Invalid UTubURL.id={utub_url_id} for UTub.id={g.utub_id} by UTubUser={current_user.id}"
            )
            abort(404)

        kwargs["current_utub_url"] = current_utub_url
        g.user_added_url = current_utub_url.user_id == current_user.id

        return func(*args, **kwargs)

    decorated_view._auth_decorator = (
        utub_membership_with_valid_url_in_utub_required.__name__
    )
    return decorated_view


def url_adder_or_creator_required(message: str) -> Callable:
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        @utub_membership_with_valid_url_in_utub_required
        def decorated_view(*args, **kwargs):
            if not (g.user_added_url or g.is_creator):
                critical_log(
                    f"User={current_user.id} not URL adder or UTub creator: "
                    f"UTubURL.id={kwargs['utub_url_id']} in UTub.id={kwargs['utub_id']}"
                )
                return build_message_error_response(message=message, status_code=403)
            return func(*args, **kwargs)

        decorated_view._auth_decorator = url_adder_or_creator_required.__name__
        return decorated_view

    return decorator


def _verify_and_get_utub_tag(**kwargs) -> Utub_Tags:
    utub_tag_id: int | None = kwargs.get("utub_tag_id")
    if utub_tag_id is None:
        abort(404)

    current_utub_tag: Utub_Tags = Utub_Tags.query.get_or_404(utub_tag_id)
    if current_utub_tag.utub_id != g.utub_id:
        critical_log(
            f"Invalid UTubTag.id={utub_tag_id} for UTub.id={g.utub_id} by UTubUser={current_user.id}"
        )
        abort(404)

    return current_utub_tag


def utub_membership_with_valid_utub_tag(func: Callable) -> Callable:
    @wraps(func)
    @utub_membership_required
    def decorated_view(*args, **kwargs):
        kwargs["current_utub_tag"] = _verify_and_get_utub_tag(**kwargs)

        return func(*args, **kwargs)

    decorated_view._auth_decorator = utub_membership_with_valid_utub_tag.__name__
    return decorated_view


def utub_membership_with_valid_url_tag(func: Callable) -> Callable:
    @wraps(func)
    @utub_membership_with_valid_url_in_utub_required
    def decorated_view(*args, **kwargs):
        current_utub_tag = _verify_and_get_utub_tag(**kwargs)
        utub_url_id: int | None = kwargs.get("utub_url_id")
        kwargs["current_utub_tag"] = current_utub_tag

        current_url_tag: Utub_Url_Tags = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == g.utub_id,
            Utub_Url_Tags.utub_url_id == utub_url_id,
            Utub_Url_Tags.utub_tag_id == current_utub_tag.id,
        ).first_or_404()

        if current_url_tag.utub_id != g.utub_id:
            critical_log(
                f"Invalid UTubURLTag.id={current_url_tag.id} for UTub.id={g.utub_id} by UTubUser={current_user.id}"
            )
            abort(404)

        kwargs["current_url_tag"] = current_url_tag

        return func(*args, **kwargs)

    decorated_view._auth_decorator = utub_membership_with_valid_url_tag.__name__
    return decorated_view


# Auth decorators that require an active session (used by OpenAPI spec generator)
SESSION_AUTH_DECORATORS: frozenset[str] = frozenset(
    {
        email_validation_required.__name__,
        url_adder_or_creator_required.__name__,
        utub_creator_required.__name__,
        utub_membership_required.__name__,
        utub_membership_with_valid_url_in_utub_required.__name__,
        utub_membership_with_valid_url_tag.__name__,
        utub_membership_with_valid_utub_tag.__name__,
    }
)


def admin_required(func: Callable) -> Callable:
    """Gate a view on `current_user.role == User_Role.ADMIN`.

    Anonymous requests receive a 401 JSON envelope (not a 302 redirect) so
    AJAX callers never follow Flask-Login's HTML splash redirect.
    Authenticated non-admin requests receive a 404 JSON envelope to avoid
    advertising the surface.

    The wrapper stashes `_auth_decorator = admin_required.__name__` so the
    OpenAPI spec generator (`backend/cli/openapi.py`) can introspect the
    auth requirement at codegen time.

    Intended for JSON/AJAX API routes. For server-rendered HTML routes that
    should redirect unauthenticated visitors, use `admin_login_required`.
    """

    @wraps(func)
    def decorated_view(*args, **kwargs):
        if not current_user.is_authenticated:
            return build_message_error_response(
                message=_NOT_AUTHENTICATED_MESSAGE,
                status_code=401,
            )
        if current_user.role != User_Role.ADMIN:
            return build_message_error_response(
                message=_NOT_FOUND_MESSAGE,
                status_code=404,
            )
        return func(*args, **kwargs)

    decorated_view._auth_decorator = admin_required.__name__
    return decorated_view


def admin_login_required(func: Callable) -> Callable:
    """Gate a server-rendered HTML view on an authenticated admin session.

    Unauthenticated requests are redirected (302) to the login page via
    Flask-Login's standard ``login_required`` flow.  Authenticated
    non-admin requests receive a 403 response.

    Use this decorator on HTML page routes (e.g. ``/admin/metrics``).
    For JSON/AJAX API routes, use ``admin_required`` instead.
    """

    @wraps(func)
    def decorated_view(*args, **kwargs):
        if current_user.role != User_Role.ADMIN:
            abort(403)
        return func(*args, **kwargs)

    # Wrap explicitly so login_required's own @wraps(func) does not
    # overwrite our outer wrapper's metadata. Matches admin_required's
    # construction style and keeps __wrapped__ pointing at our handler.
    decorated_view = login_required(decorated_view)
    decorated_view._auth_decorator = admin_login_required.__name__
    return decorated_view


# Auth decorators that require admin privileges (additive on top of session auth).
ADMIN_AUTH_DECORATORS: frozenset[str] = frozenset(
    {admin_required.__name__, admin_login_required.__name__}
)


# --- Bearer-token JSON auth decorators for the mobile /api/v1 surface ---
#
# These parallel the session decorator chain above but NEVER redirect: every
# failure is a JSON ErrorResponse envelope (401 unauthenticated / 403
# forbidden / 404 not found via abort, caught by the api_v1 blueprint's JSON
# errorhandler). They read `current_user.email_validated` from the model —
# never the EMAIL_VALIDATED session key, which bearer requests never populate.
# `admin_required` above is the JSON 401 template these follow.


def api_authentication_required(func: Callable) -> Callable:
    """Gate an /api/v1 view on an authenticated bearer identity (401 JSON).

    Base of the /api/v1 decorator chain — deliberately does NOT require a
    validated email, so endpoints like `/me` and `/auth/resend-validation`
    remain reachable by unvalidated accounts (design-doc gating decision).
    """

    @wraps(func)
    def decorated_view(*args, **kwargs):
        if not current_user.is_authenticated:
            return build_message_error_response(
                message=API_AUTH_FAILURE.AUTHENTICATION_REQUIRED,
                status_code=401,
            )
        return func(*args, **kwargs)

    decorated_view._auth_decorator = api_authentication_required.__name__
    return decorated_view


def api_email_validation_required(func: Callable) -> Callable:
    @wraps(func)
    @api_authentication_required
    def decorated_view(*args, **kwargs):
        if not current_user.email_validated:
            warning_log(
                f"User={current_user.id} attempted /api/v1 access without validated email"
            )
            return build_message_error_response(
                message=API_AUTH_FAILURE.EMAIL_VALIDATION_REQUIRED,
                status_code=403,
            )
        return func(*args, **kwargs)

    decorated_view._auth_decorator = api_email_validation_required.__name__
    return decorated_view


def api_utub_membership_required(func: Callable) -> Callable:
    @wraps(func)
    @api_email_validation_required
    def decorated_view(*args, **kwargs):
        utub_id: int | None = kwargs.get("utub_id")
        if utub_id is None:
            abort(404)

        member: Utub_Members = Utub_Members.query.get_or_404((utub_id, current_user.id))
        g.is_creator = member.member_role in (
            Member_Role.CREATOR,
            Member_Role.CO_CREATOR,
        )
        utub: Utubs = Utubs.query.get_or_404(utub_id)
        g.utub_id = utub.id
        kwargs["current_utub"] = utub

        return func(*args, **kwargs)

    decorated_view._auth_decorator = api_utub_membership_required.__name__
    return decorated_view


def api_utub_creator_required(func: Callable) -> Callable:
    @wraps(func)
    @api_utub_membership_required
    def decorated_view(*args, **kwargs):
        if not is_current_utub_creator():
            utub_id: int = kwargs["utub_id"]
            current_utub: Utubs = kwargs["current_utub"]
            critical_log(
                f"User={current_user.id} not creator: UTub.id={utub_id} | UTub.name={current_utub.name}"
            )

            return build_message_error_response(
                message=UTUB_FAILURE.NOT_AUTHORIZED,
                status_code=403,
            )

        return func(*args, **kwargs)

    decorated_view._auth_decorator = api_utub_creator_required.__name__
    return decorated_view


def api_utub_membership_with_valid_url_in_utub_required(func: Callable) -> Callable:
    @wraps(func)
    @api_utub_membership_required
    def decorated_view(*args, **kwargs):
        utub_url_id: int | None = kwargs.get("utub_url_id")
        if utub_url_id is None:
            abort(404)

        current_utub_url: Utub_Urls = Utub_Urls.query.get_or_404(utub_url_id)
        if current_utub_url.utub_id != g.utub_id:
            critical_log(
                f"Invalid UTubURL.id={utub_url_id} for UTub.id={g.utub_id} by UTubUser={current_user.id}"
            )
            abort(404)

        kwargs["current_utub_url"] = current_utub_url
        g.user_added_url = current_utub_url.user_id == current_user.id

        return func(*args, **kwargs)

    decorated_view._auth_decorator = (
        api_utub_membership_with_valid_url_in_utub_required.__name__
    )
    return decorated_view


def api_url_adder_or_creator_required(message: str) -> Callable:
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        @api_utub_membership_with_valid_url_in_utub_required
        def decorated_view(*args, **kwargs):
            if not (g.user_added_url or g.is_creator):
                critical_log(
                    f"User={current_user.id} not URL adder or UTub creator: "
                    f"UTubURL.id={kwargs['utub_url_id']} in UTub.id={kwargs['utub_id']}"
                )
                return build_message_error_response(message=message, status_code=403)
            return func(*args, **kwargs)

        decorated_view._auth_decorator = api_url_adder_or_creator_required.__name__
        return decorated_view

    return decorator


def api_utub_membership_with_valid_utub_tag(func: Callable) -> Callable:
    @wraps(func)
    @api_utub_membership_required
    def decorated_view(*args, **kwargs):
        kwargs["current_utub_tag"] = _verify_and_get_utub_tag(**kwargs)

        return func(*args, **kwargs)

    decorated_view._auth_decorator = api_utub_membership_with_valid_utub_tag.__name__
    return decorated_view


def api_utub_membership_with_valid_url_tag(func: Callable) -> Callable:
    @wraps(func)
    @api_utub_membership_with_valid_url_in_utub_required
    def decorated_view(*args, **kwargs):
        current_utub_tag = _verify_and_get_utub_tag(**kwargs)
        utub_url_id: int | None = kwargs.get("utub_url_id")
        kwargs["current_utub_tag"] = current_utub_tag

        current_url_tag: Utub_Url_Tags = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == g.utub_id,
            Utub_Url_Tags.utub_url_id == utub_url_id,
            Utub_Url_Tags.utub_tag_id == current_utub_tag.id,
        ).first_or_404()

        if current_url_tag.utub_id != g.utub_id:
            critical_log(
                f"Invalid UTubURLTag.id={current_url_tag.id} for UTub.id={g.utub_id} by UTubUser={current_user.id}"
            )
            abort(404)

        kwargs["current_url_tag"] = current_url_tag

        return func(*args, **kwargs)

    decorated_view._auth_decorator = api_utub_membership_with_valid_url_tag.__name__
    return decorated_view


# Bearer-token auth decorators for /api/v1 (used by the OpenAPI spec generator
# to emit `bearerAuth` security — and never `csrfToken`, since the api_v1
# blueprint is CSRF-exempt).
API_AUTH_DECORATORS: frozenset[str] = frozenset(
    {
        api_authentication_required.__name__,
        api_email_validation_required.__name__,
        api_url_adder_or_creator_required.__name__,
        api_utub_creator_required.__name__,
        api_utub_membership_required.__name__,
        api_utub_membership_with_valid_url_in_utub_required.__name__,
        api_utub_membership_with_valid_url_tag.__name__,
        api_utub_membership_with_valid_utub_tag.__name__,
    }
)
