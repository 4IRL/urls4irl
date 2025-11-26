from flask import g


def is_current_utub_creator() -> bool:
    if not hasattr(g, "is_creator"):
        return False
    return g.is_creator


def is_adder_of_utub_url() -> bool:
    if not hasattr(g, "user_added_url"):
        return False
    return g.user_added_url
