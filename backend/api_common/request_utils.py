from flask import g
from flask_login import current_user

from backend.models.utubs import Utubs


def is_current_utub_manager() -> bool:
    if not hasattr(g, "is_manager"):
        return False
    return g.is_manager


def is_current_utub_owner(current_utub: Utubs) -> bool:
    """Return whether the current user is the UTub's literal owner (creator).

    This is the strict owner check: it compares ``current_user.id`` against
    ``current_utub.utub_creator`` directly and does NOT consult the
    co-creator-inclusive ``g.is_manager`` flag. A co-creator (co-owner) is
    therefore NOT an owner by this predicate, unlike
    :func:`is_current_utub_manager`.

    Args:
        current_utub (Utubs): The UTub whose ownership is being checked.

    Returns:
        bool: ``True`` only when an authenticated current user is the literal
            creator of ``current_utub``.
    """
    return (
        current_user.is_authenticated and current_user.id == current_utub.utub_creator
    )
