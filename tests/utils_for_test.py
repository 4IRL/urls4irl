import re
from logging import LogRecord
from typing import NamedTuple

from flask import Flask
import sqlalchemy

from backend import db
from backend.config import ConfigTest
from backend.models.urls import Urls
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs


class DistinctStatsSeed(NamedTuple):
    """Objects created by ``seed_distinct_stats_for_user_one`` that callers
    layer additional rows onto (e.g. noise rows) before committing."""

    home_utub: Utubs
    user_one_utub_urls: list[Utub_Urls]
    user_one_tags: list[Utub_Tags]


def seed_distinct_stats_for_user_one(
    label_prefix: str = "user1",
) -> DistinctStatsSeed:
    """Seed mutually-distinct per-user activity counts for user 1 so each
    Stats card renders a unique value (2/3/5/7/11) and a swapped card is
    caught. Assumes an ACTIVE app context and that users 1-3 already exist;
    does NOT commit — the caller commits after layering any extra rows.

      - **2** ``Utubs`` created by user 1 (each with a CREATOR membership row)
      - **3** ``Utubs`` created by others (2 by user 2, 1 by user 3); user 1
        is a MEMBER — keeps "member of" disjoint from "created"
      - **5** ``Utub_Urls`` added by user 1 (each backed by a unique ``Urls`` row)
      - **7** ``Utub_Tags`` created by user 1
      - **11** ``Utub_Url_Tags`` applied by user 1 (distinct url/tag pairs)

    ``label_prefix`` distinguishes the generated ``normalized_url`` and
    ``tag_string`` values so separate call sites keep their existing distinct
    seed data.

    Returns the created ``home_utub``/urls/tags so callers can attach further
    rows (e.g. per-user-filter noise rows) that reference them.
    """
    # 2 UTubs created by user 1, each with its own CREATOR membership row.
    user_one_utubs: list[Utubs] = []
    for utub_index in range(2):
        created_utub = Utubs(
            name=f"User1 UTub {utub_index}",
            utub_creator=1,
            utub_description="",
        )
        db.session.add(created_utub)
        db.session.flush()
        db.session.add(
            Utub_Members(
                utub_id=created_utub.id,
                user_id=1,
                member_role=Member_Role.CREATOR,
            )
        )
        user_one_utubs.append(created_utub)

    # 3 UTubs created by others (2 by user 2, 1 by user 3); user 1 is MEMBER.
    for creator_id in (2, 2, 3):
        others_utub = Utubs(
            name=f"User{creator_id} UTub",
            utub_creator=creator_id,
            utub_description="",
        )
        db.session.add(others_utub)
        db.session.flush()
        db.session.add(
            Utub_Members(
                utub_id=others_utub.id,
                user_id=creator_id,
                member_role=Member_Role.CREATOR,
            )
        )
        db.session.add(
            Utub_Members(
                utub_id=others_utub.id,
                user_id=1,
                member_role=Member_Role.MEMBER,
            )
        )

    # Everything below hangs off user 1's first created UTub.
    home_utub = user_one_utubs[0]

    # 5 Utub_Urls added by user 1, each backed by a unique Urls row.
    user_one_utub_urls: list[Utub_Urls] = []
    for url_index in range(5):
        backing_url = Urls(
            normalized_url=f"https://{label_prefix}-url-{url_index}.example.com",
            current_user_id=1,
        )
        db.session.add(backing_url)
        db.session.flush()
        utub_url = Utub_Urls()
        utub_url.utub_id = home_utub.id
        utub_url.url_id = backing_url.id
        utub_url.user_id = 1
        utub_url.url_title = f"User1 URL {url_index}"
        db.session.add(utub_url)
        db.session.flush()
        user_one_utub_urls.append(utub_url)

    # 7 Utub_Tags created by user 1.
    user_one_tags: list[Utub_Tags] = []
    for tag_index in range(7):
        created_tag = Utub_Tags(
            utub_id=home_utub.id,
            tag_string=f"{label_prefix}-tag-{tag_index}",
            created_by=1,
        )
        db.session.add(created_tag)
        db.session.flush()
        user_one_tags.append(created_tag)

    # 11 Utub_Url_Tags applied by user 1 (distinct url/tag pairs).
    applied_pairs = [
        (url_index, tag_index) for url_index in range(5) for tag_index in range(7)
    ][:11]
    for url_index, tag_index in applied_pairs:
        db.session.add(
            Utub_Url_Tags(
                utub_id=home_utub.id,
                utub_url_id=user_one_utub_urls[url_index].id,
                utub_tag_id=user_one_tags[tag_index].id,
                user_id=1,
            )
        )

    return DistinctStatsSeed(
        home_utub=home_utub,
        user_one_utub_urls=user_one_utub_urls,
        user_one_tags=user_one_tags,
    )


def set_member_role(app: Flask, utub_id: int, user_id: int, role: Member_Role) -> None:
    """Promote/demote an existing UTub member to the given role, in place.

    Loads the ``Utub_Members`` row by its composite primary key
    ``(utub_id, user_id)`` and sets its ``member_role``. Use this to change the
    role of a member already seeded onto a UTub (e.g. promoting a plain member
    to ``Member_Role.CO_CREATOR`` mid-test), as distinct from the
    ``add_co_creator_to_utub_without_logging_in`` fixture, which seeds a fresh
    UTub with a CO_CREATOR member from the start. The member row must already
    exist for the given ``(utub_id, user_id)``.

    Args:
        app (Flask): The Flask client for providing an app context
        utub_id (int): The ID of the UTub the member belongs to
        user_id (int): The ID of the member User to update
        role (Member_Role): The role to assign to the member
    """
    with app.app_context():
        member: Utub_Members = Utub_Members.query.get((utub_id, user_id))
        member.member_role = role
        db.session.commit()


def get_csrf_token(html_page: bytes, meta_tag: bool = False) -> str:
    """
    Reads in the html byte response from a GET of a page, finds the CSRF token using regex, returns it.

    Args:
        html_page (bytes): Byte data of html page
        meta_tag (bool): If it's in a meta tag or not

    Returns:
        str: CSRF from parsed HTML page
    """
    if meta_tag:
        all_html_data = str(
            [val for val in html_page.splitlines() if b'name="csrf-token"' in val][0]
        )
        result = re.search('<meta name="csrf-token" content="(.*)">', all_html_data)
    else:
        all_html_data = str(
            [val for val in html_page.splitlines() if b'name="csrf_token"' in val][0]
        )
        result = re.search(
            '<input id="csrf_token" name="csrf_token" type="hidden" value="(.*)">',
            all_html_data,
        )

    assert result is not None
    return result.group(1)


def clear_database(test_config: ConfigTest):
    engine = sqlalchemy.create_engine(test_config.SQLALCHEMY_DATABASE_URI)
    meta = sqlalchemy.MetaData(engine)
    meta.reflect()
    meta.drop_all()
    meta.create_all()


def trim_and_parse_logs(logs: list[LogRecord]) -> list[str]:
    """
    Remove first and last logs for an endpoint's logs as they do not contain unique data to test for

    Request: GET /home                                      # Not being tested for
    [BEGIN] Returning user's UTubs on home page load [END]  # Being tested for
    Response: 200 completed in 109.63ms                     # Not being tested for

    Args:
        logs (list[LogRecord]): Raw LogRecords for a request

    Returns:
        list[str]: Log messages that aren't the first or last log
    """
    return [record.getMessage() for record in logs]


def is_string_in_logs(needle: str, log_records: list[LogRecord]) -> bool:
    logs = trim_and_parse_logs(log_records)
    return any([needle in haystack for haystack in logs])


def is_string_in_logs_regex(needle: str, log_records: list[LogRecord]) -> bool:
    logs = trim_and_parse_logs(log_records)
    return any([re.match(needle, haystack) is not None for haystack in logs])


def count_tag_instances_in_utub(utub_id: int, utub_tag_id: int) -> int:
    return Utub_Url_Tags.query.filter(
        Utub_Url_Tags.utub_id == utub_id, Utub_Url_Tags.utub_tag_id == utub_tag_id
    ).count()
