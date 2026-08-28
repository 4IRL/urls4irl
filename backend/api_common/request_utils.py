from flask import g
from flask_login import current_user

from backend.models.utubs import Utubs


def is_current_utub_creator() -> bool:
    if not hasattr(g, "is_creator"):
        return False
    return g.is_creator


def is_current_utub_true_owner(current_utub: Utubs) -> bool:
    """Return whether the current user is the UTub's literal owner (creator).

    This is the strict owner check: it compares ``current_user.id`` against
    ``current_utub.utub_creator`` directly and does NOT consult the
    co-creator-inclusive ``g.is_creator`` flag. A co-creator (co-owner) is
    therefore NOT a true owner by this predicate, unlike
    :func:`is_current_utub_creator`.

    Args:
        current_utub (Utubs): The UTub whose ownership is being checked.

    Returns:
        bool: ``True`` only when an authenticated current user is the literal
            creator of ``current_utub``.
    """
    return (
        current_user.is_authenticated and current_user.id == current_utub.utub_creator
    )
