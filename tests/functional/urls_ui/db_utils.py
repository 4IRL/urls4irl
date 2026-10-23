import re
from typing import NamedTuple

from flask import Flask

from backend import db
from backend.models.short_links import Short_Links
from backend.models.users import Users
from backend.short_links.code_generator import generate_short_link_code
from backend.short_links.constants import SHORT_LINK_TTL
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.url_strs import URL_ADDED_BY, URL_ADDED_BY_FORMER_MEMBER
from tests.functional.db_utils import (
    add_url_to_utub_as_other_member,
    get_plain_members_excluding,
    get_utub_this_user_did_not_create,
    remove_user_from_utub,
)

ORPHANED_URL_STRING = "https://orphaned.example.com/path"
ORPHANED_URL_TITLE = "Orphaned URL"
CONTROL_URL_STRING = "https://control-member.example.com/path"
CONTROL_URL_TITLE = "Control URL"
FORMER_MEMBER_BADGE_PREFIX = f"{URL_ADDED_BY} {URL_ADDED_BY_FORMER_MEMBER} · "
# Default DateFormat preference is ISO (YYYY-MM-DD)
FORMER_MEMBER_BADGE_PATTERN = re.compile(
    rf"^{re.escape(FORMER_MEMBER_BADGE_PREFIX)}\d{{4}}-\d{{2}}-\d{{2}}$"
)


class OrphanedUrlScenario(NamedTuple):
    utub_id: int
    orphaned_utub_url_id: int
    control_utub_url_id: int
    departed_user_id: int
    departed_username: str


def seed_orphaned_url_scenario(*, app: Flask, user_id: int) -> OrphanedUrlScenario:
    """Seed a UTub ``user_id`` is a plain member of (not creator) with two URLs: one
    added by another plain member who is then removed from the UTub (orphaned), and a
    control added by the UTub's creator (still a member). Requires
    ``create_test_utubmembers`` so every user belongs to every UTub."""
    utub = get_utub_this_user_did_not_create(app, user_id)
    assert utub.utub_creator != user_id, "Test premise violated: user created the UTub"
    departing_candidates = get_plain_members_excluding(
        app, utub.id, [user_id, utub.utub_creator]
    )
    assert departing_candidates, "Test premise violated: no other plain member"
    departed_user_id = departing_candidates[0]

    orphaned_id = add_url_to_utub_as_other_member(
        app, utub.id, departed_user_id, ORPHANED_URL_STRING, ORPHANED_URL_TITLE
    )
    control_id = add_url_to_utub_as_other_member(
        app, utub.id, utub.utub_creator, CONTROL_URL_STRING, CONTROL_URL_TITLE
    )
    with app.app_context():
        departed_username = Users.query.get(departed_user_id).username
    remove_user_from_utub(app, departed_user_id, utub.id)
    return OrphanedUrlScenario(
        departed_username=departed_username,
        utub_id=utub.id,
        orphaned_utub_url_id=orphaned_id,
        control_utub_url_id=control_id,
        departed_user_id=departed_user_id,
    )


def mint_short_link_in_db(*, app: Flask, utub_url_id: int, created_by: int) -> str:
    """Insert an active (7-day) ``ShortLinks`` row for ``utub_url_id`` minted by
    ``created_by`` and return its code, so a test can start from a link another
    member already made without driving that member's browser."""
    code = generate_short_link_code()
    with app.app_context():
        db.session.add(
            Short_Links(
                utub_url_id=utub_url_id,
                code=code,
                created_by=created_by,
                expires_at=utc_now() + SHORT_LINK_TTL,
            )
        )
        db.session.commit()
    return code


def get_short_link_code(*, app: Flask, utub_url_id: int) -> str | None:
    """The code of the URL's ``ShortLinks`` row, or None when it has none."""
    with app.app_context():
        short_link: Short_Links | None = Short_Links.query.filter(
            Short_Links.utub_url_id == utub_url_id
        ).first()
        return None if short_link is None else short_link.code
