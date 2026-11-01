import secrets

from backend.invite_links.constants import INVITE_LINK_TOKEN_BYTES


def generate_invite_token() -> str:
    """Return a URL-safe token carrying INVITE_LINK_TOKEN_BYTES of CSPRNG randomness."""
    return secrets.token_urlsafe(INVITE_LINK_TOKEN_BYTES)
