from flask import g


def is_current_utub_creator() -> bool:
    if not hasattr(g, "is_creator"):
        return False
    return g.is_creator
