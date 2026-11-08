"""Pure, format-only parser for an invite ``next`` target.

A leaf module: it imports only the stdlib and ``backend.invite_links.constants``. It
never touches the database, ``current_user`` or ``backend.splash``, so the anonymous
register POST can reuse it. It does not check that the invite is live.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from backend.invite_links.constants import (
    INVITE_LINK_TOKEN_LENGTH,
    INVITE_PATH_PREFIX,
    INVITE_REGISTER_HINT_SEGMENT,
)

InviteModalHint = Literal["login", "register"]

_INVITE_NEXT_PATTERN: re.Pattern[str] = re.compile(
    rf"^{re.escape(INVITE_PATH_PREFIX)}"
    rf"(?P<token>[A-Za-z0-9_-]{{{INVITE_LINK_TOKEN_LENGTH}}})"
    rf"(?P<register>/{re.escape(INVITE_REGISTER_HINT_SEGMENT)})?\Z"
)


@dataclass(frozen=True)
class InviteNextTarget:
    token: str
    hint: InviteModalHint


def parse_invite_next(value: object) -> InviteNextTarget | None:
    """Return the target when ``value`` is exactly an invite path, else ``None``.

    Args:
        value (object): The raw ``next`` value; any non-string returns ``None``.
    """
    if not isinstance(value, str):
        return None
    match = _INVITE_NEXT_PATTERN.match(value)
    if match is None:
        return None
    hint: InviteModalHint = "register" if match.group("register") else "login"
    return InviteNextTarget(token=match.group("token"), hint=hint)


def invite_next_redirect_path(target: InviteNextTarget) -> str:
    """The bare invite path rebuilt from the matched token (never echoes input)."""
    return f"{INVITE_PATH_PREFIX}{target.token}"
