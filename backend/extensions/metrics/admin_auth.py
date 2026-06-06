from functools import wraps
from typing import Callable

from flask_login import current_user

from backend.models.users import User_Role
from backend.schemas.errors import build_message_error_response

_NOT_AUTHENTICATED_MESSAGE: str = "Authentication required."
_NOT_FOUND_MESSAGE: str = "Not found."


def metrics_admin_required(func: Callable) -> Callable:
    """Gate a view on `current_user.role == User_Role.ADMIN`.

    Anonymous requests receive a 401 JSON envelope (not a 302 redirect) so
    AJAX callers — including the metrics dashboard's polling loop — never
    follow Flask-Login's HTML splash redirect. Authenticated non-admin
    requests receive a 404 JSON envelope to avoid advertising the surface.

    The wrapper stashes `_auth_decorator = metrics_admin_required.__name__`
    so the OpenAPI spec generator (`backend/cli/openapi.py`) can introspect
    the auth requirement at codegen time.
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

    decorated_view._auth_decorator = metrics_admin_required.__name__
    return decorated_view
