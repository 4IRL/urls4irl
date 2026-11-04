import re

from backend.invite_links.constants import INVITE_LINK_TOKEN_PATTERN
from backend.models.utub_invite_links import Utub_Invite_Links

_TOKEN_REGEX = re.compile(INVITE_LINK_TOKEN_PATTERN)


def find_invite_by_token(token: str) -> Utub_Invite_Links | None:
    """
    Return the invite row for a token, revoked or not, else None.

    A malformed token returns None without querying the database. Revoked rows are
    dead, not missing, so callers decide what a dead row means.

    Args:
        token (str): The raw token from the request path
    """
    if not isinstance(token, str) or _TOKEN_REGEX.match(token) is None:
        return None
    return Utub_Invite_Links.query.filter_by(token=token).first()
