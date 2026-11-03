from flask_limiter.util import get_remote_address
from flask_login import current_user


def invite_link_manage_rate_key() -> str:
    """Rate-limit key for invite link create/replace: the user id, else the client IP.

    Flask-Limiter evaluates decorated-route limits in ``before_request``, before the
    view-level auth decorators run, so this must be safe for anonymous callers (an
    anonymous ``current_user`` has no ``id``). Each manager gets their own budget.
    """
    if current_user.is_authenticated:
        return str(current_user.id)
    return get_remote_address()
