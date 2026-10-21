import secrets
import string

from backend.models.short_links import SHORT_LINK_CODE_LENGTH

_ALPHABET: str = string.ascii_letters + string.digits


def generate_short_link_code() -> str:
    """Return a random 10-character ``[A-Za-z0-9]`` code drawn from a CSPRNG."""
    return "".join(secrets.choice(_ALPHABET) for _ in range(SHORT_LINK_CODE_LENGTH))
