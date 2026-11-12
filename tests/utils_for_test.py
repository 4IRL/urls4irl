import json
import re
from datetime import datetime
from logging import Handler, Logger, LogRecord, getLogger
from typing import Any, NamedTuple

import sqlalchemy
from flask import Flask
from sqlalchemy import event
from sqlalchemy.engine import Connection

from backend import create_app, db, oauth
from backend.config import ConfigTest
from backend.invite_links.constants import INVITE_LINK_DEFAULT_TTL
from backend.invite_links.token_generator import generate_invite_token
from backend.models.short_links import Short_Links
from backend.models.urls import Urls
from backend.models.users import Users
from backend.models.utub_invite_links import Utub_Invite_Links
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.schemas.urls import UtubUrlSchema
from backend.short_links.code_generator import generate_short_link_code
from backend.short_links.constants import SHORT_LINK_TTL
from backend.urls.services.trashed_url_tags import build_tag_name_snapshot_from_ids
from backend.utils.datetime_utils import utc_now


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


def trash_utub(app: Flask, utub_id: int, deleted_by: int) -> None:
    """Soft-delete (trash) an existing UTub in place.

    Sets ``deleted_at`` to now and ``deleted_by`` to the given user, mirroring
    what the UTub delete service does, without going through the route. The
    UTub's URLs, tags and members are left untouched.

    Args:
        app (Flask): The Flask client for providing an app context
        utub_id (int): The ID of the UTub to trash
        deleted_by (int): The ID of the User recorded as having trashed it
    """
    with app.app_context():
        utub: Utubs = Utubs.query.get(utub_id)
        utub.deleted_at = utc_now()
        utub.deleted_by = deleted_by
        db.session.commit()


def trash_utub_url(
    app: Flask,
    utub_url_id: int,
    deleted_by: int,
    trashed_tag_ids: list[int] | None = None,
    record_tag_names: bool = True,
) -> None:
    """Soft-delete (trash) an existing UTub URL in place.

    Sets ``deleted_at`` to now, ``deleted_by`` to the given user and
    ``trashed_tag_ids`` plus ``trashed_tag_names`` to the snapshot, mirroring what
    the URL delete service does, without going through the route. The URL's
    ``Utub_Url_Tags`` rows are left untouched.

    Args:
        app (Flask): The Flask client for providing an app context
        utub_url_id (int): The ID of the Utub_Urls row to trash
        deleted_by (int): The ID of the User recorded as having trashed it
        trashed_tag_ids (list[int] | None): The tag ids to snapshot. Defaults to
            the row's current associated tag ids, sorted
        record_tag_names (bool): False leaves ``trashed_tag_names`` NULL, simulating
            a row trashed before tag names were saved
    """
    with app.app_context():
        utub_url: Utub_Urls = Utub_Urls.query.get(utub_url_id)
        utub_url.deleted_at = utc_now()
        utub_url.deleted_by = deleted_by
        utub_url.trashed_tag_ids = (
            list(trashed_tag_ids)
            if trashed_tag_ids is not None
            else sorted(utub_url.associated_tag_ids)
        )
        utub_url.trashed_tag_names = (
            build_tag_name_snapshot_from_ids(utub_url.trashed_tag_ids)
            if record_tag_names
            else None
        )
        db.session.commit()


def lock_utub(app: Flask, utub_id: int) -> None:
    """Freeze an existing UTub to mutations, in place.

    Args:
        app (Flask): The Flask client for providing an app context
        utub_id (int): The ID of the UTub to lock
    """
    with app.app_context():
        utub: Utubs = Utubs.query.get(utub_id)
        utub.is_locked = True
        db.session.commit()


def unlock_utub(app: Flask, utub_id: int) -> None:
    """Unfreeze a locked UTub, in place.

    Args:
        app (Flask): The Flask client for providing an app context
        utub_id (int): The ID of the UTub to unlock
    """
    with app.app_context():
        utub: Utubs = Utubs.query.get(utub_id)
        utub.is_locked = False
        db.session.commit()


def statements_while(action: Any) -> list[str]:
    """Run ``action`` and return the SQL statements emitted on the session connection."""
    statements: list[str] = []

    def capture(
        conn: Connection,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        statements.append(statement)

    connection = db.session.connection()
    event.listen(connection, "before_cursor_execute", capture)
    try:
        action()
    finally:
        event.remove(connection, "before_cursor_execute", capture)
    return statements


def set_members_settings(app: Flask, utub_id: int, members: dict[str, bool]) -> None:
    """Seed a UTub's stored ``members`` settings section, in place.

    Args:
        app (Flask): The Flask client for providing an app context
        utub_id (int): The ID of the UTub to update
        members (dict[str, bool]): Stored overrides, e.g. {"co_owners_can_remove": True}
    """
    with app.app_context():
        utub: Utubs = Utubs.query.get(utub_id)
        utub.settings = {"members": members}
        db.session.commit()


def set_tags_settings(app: Flask, utub_id: int, tags: dict[str, Any]) -> None:
    """Seed a UTub's stored ``tags`` settings section, in place.

    Args:
        app (Flask): The Flask client for providing an app context
        utub_id (int): The ID of the UTub to update
        tags (dict[str, Any]): Stored overrides, e.g. {"members_can_tag": False}
    """
    with app.app_context():
        utub: Utubs = Utubs.query.get(utub_id)
        utub.settings = {"tags": tags}
        db.session.commit()


class HideListSeed(NamedTuple):
    """Ids of the shared 5-user hide-list UTub shape (see ``seed_hide_list_utub``)."""

    utub_id: int
    owner_id: int
    co_owner_id: int
    member_a_id: int
    member_b_id: int
    former_member_id: int
    usernames: dict[int, str]
    utub_url_ids: dict[int, int]  # adder user id -> Utub_Urls id

    @property
    def current_member_ids(self) -> set[int]:
        return {self.owner_id, self.co_owner_id, self.member_a_id, self.member_b_id}


def seed_hide_list_utub(app: Flask, hide_member_list: bool | None) -> HideListSeed:
    """Seed one UTub with an owner, a co-owner, two plain members and a former member.

    Every one of the five users added one URL; the former member's membership row is
    then deleted, so their URL is orphaned. ``hide_member_list`` is stored through
    ``set_members_settings`` (``None`` leaves the UTub without any stored settings).

    Args:
        app (Flask): The Flask client for providing an app context
        hide_member_list (bool | None): The stored ``hide_member_list`` value, or None

    Returns:
        HideListSeed: The UTub id, the five user ids, usernames and URL ids
    """
    labels = ("owner", "coowner", "membera", "memberb", "former")
    with app.app_context():
        users: list[Users] = []
        for label in labels:
            user = Users(
                username=f"hide_{label}",
                email=f"hide_{label}@urls4irl.app",
                plaintext_password=f"hide_{label}@urls4irl.app",
            )
            user.email_validated = True
            db.session.add(user)
            users.append(user)
        db.session.commit()

        owner, co_owner, member_a, member_b, former = users
        utub = Utubs(name="Hide list UTub", utub_creator=owner.id, utub_description="")
        roles = (
            Member_Role.CREATOR,
            Member_Role.CO_CREATOR,
            Member_Role.MEMBER,
            Member_Role.MEMBER,
            Member_Role.MEMBER,
        )
        for user, role in zip(users, roles):
            membership = Utub_Members(member_role=role)
            membership.to_user = user
            utub.members.append(membership)
        db.session.add(utub)
        db.session.commit()

        utub_url_ids: dict[int, int] = {}
        for user in users:
            url = Urls(
                normalized_url=f"https://hide-list-{user.id}.example.com",
                current_user_id=user.id,
            )
            db.session.add(url)
            db.session.commit()
            utub_url = Utub_Urls()
            utub_url.user_id = user.id
            utub_url.url_title = f"Hide list URL {user.id}"
            utub_url.url_id = url.id
            utub_url.utub_id = utub.id
            db.session.add(utub_url)
            db.session.commit()
            utub_url_ids[user.id] = utub_url.id

        db.session.delete(Utub_Members.query.get((utub.id, former.id)))
        db.session.commit()

        seed = HideListSeed(
            utub_id=utub.id,
            owner_id=owner.id,
            co_owner_id=co_owner.id,
            member_a_id=member_a.id,
            member_b_id=member_b.id,
            former_member_id=former.id,
            usernames={user.id: user.username for user in users},
            utub_url_ids=utub_url_ids,
        )

    if hide_member_list is not None:
        set_members_settings(app, seed.utub_id, {"hide_member_list": hide_member_list})
    return seed


def assert_hidden_list_detail(
    payload: dict[str, Any], seed: HideListSeed, viewer_id: int
) -> None:
    """Assert a UTub detail payload honors the hide-list rule for ``viewer_id``.

    A plain-member viewer sees exactly the owner, the co-owner and themself, hidden
    current members' URLs carry a null adder, and no hidden username appears anywhere
    in the serialized body. Former-member URLs keep their id. Owner and co-owner see
    every current member and real adder ids.
    """
    members = {member["id"] for member in payload["members"]}
    adders = {url["utubUrlID"]: url["addedByUserID"] for url in payload["urls"]}
    plain_viewer = viewer_id in {seed.member_a_id, seed.member_b_id}
    if plain_viewer:
        visible = {seed.owner_id, seed.co_owner_id, viewer_id}
        hidden = seed.current_member_ids - visible
        assert members == visible
        body = json.dumps(payload)
        for hidden_id in hidden:
            assert seed.usernames[hidden_id] not in body
            assert adders[seed.utub_url_ids[hidden_id]] is None
        for visible_id in visible:
            assert adders[seed.utub_url_ids[visible_id]] == visible_id
    else:
        assert members == seed.current_member_ids
        for user_id in seed.current_member_ids:
            assert adders[seed.utub_url_ids[user_id]] == user_id
    assert adders[seed.utub_url_ids[seed.former_member_id]] == seed.former_member_id


def add_short_link(
    app: Flask,
    utub_url_id: int,
    minted_by: int | None,
    code: str | None = None,
    expires_at: datetime | None = None,
) -> int:
    """Seed a ``ShortLinks`` row for a UTub URL directly, bypassing the mint route.

    Args:
        app (Flask): The Flask client for providing an app context
        utub_url_id (int): The ID of the Utub_Urls row to link
        minted_by (int | None): The ID of the User recorded as the minter, or None
        code (str | None): The link code. Defaults to a freshly generated one
        expires_at (datetime | None): Expiry. Defaults to now plus the link TTL; pass a
            past value to seed an expired link

    Returns:
        int: The new ShortLinks row ID
    """
    with app.app_context():
        link = Short_Links(
            utub_url_id=utub_url_id,
            code=code if code is not None else generate_short_link_code(),
            created_by=minted_by,
            expires_at=(
                expires_at if expires_at is not None else utc_now() + SHORT_LINK_TTL
            ),
        )
        db.session.add(link)
        db.session.commit()
        return link.id


def add_invite_link(
    app: Flask,
    utub_id: int,
    created_by: int | None,
    expires_at: datetime | None = None,
    max_uses: int | None = None,
    use_count: int = 0,
    revoked: bool = False,
) -> int:
    """Seed a ``UtubInviteLinks`` row directly, bypassing the manage routes.

    Args:
        app (Flask): The Flask client for providing an app context
        utub_id (int): The ID of the UTub the link belongs to
        created_by (int | None): The ID of the creating User, or None
        expires_at (datetime | None): Expiry. Defaults to now plus the default TTL; pass a
            past value to seed an expired link
        max_uses (int | None): Use limit, or None for unlimited
        use_count (int): How many joins the link already has
        revoked (bool): Whether to stamp ``revoked_at`` so the row is revoked

    Returns:
        int: The new UtubInviteLinks row ID
    """
    with app.app_context():
        invite = Utub_Invite_Links(
            utub_id=utub_id,
            token=generate_invite_token(),
            created_by=created_by,
            expires_at=(
                expires_at
                if expires_at is not None
                else utc_now() + INVITE_LINK_DEFAULT_TTL
            ),
            max_uses=max_uses,
        )
        invite.use_count = use_count
        if revoked:
            invite.revoked_at = utc_now()
        db.session.add(invite)
        db.session.commit()
        return invite.id


UNKNOWN_INVITE_TOKEN = "Z" * 22


def seed_invite_token_on_foreign_utub(app: Flask, *, revoked: bool = False) -> str:
    """Create a UTub owned by a separate user (so a logging-in user is a non-member)
    plus an invite link on it.

    Args:
        app (Flask): The Flask client for providing an app context
        revoked (bool): Whether the invite link is revoked

    Returns:
        str: The invite link token
    """
    with app.app_context():
        owner = Users(
            username="inviteowner",
            email="inviteowner@example.com",
            plaintext_password="P@ssword123!",
        )
        owner.email_validated = True
        db.session.add(owner)
        db.session.flush()
        new_utub = Utubs(
            name="OAuth Next Target", utub_creator=owner.id, utub_description=""
        )
        creator_to_utub = Utub_Members(member_role=Member_Role.CREATOR)
        creator_to_utub.to_user = owner
        new_utub.members.append(creator_to_utub)
        db.session.add(new_utub)
        db.session.commit()
        utub_id, creator_id = new_utub.id, owner.id
    invite_id = add_invite_link(app, utub_id, creator_id, revoked=revoked)
    with app.app_context():
        return db.session.get(Utub_Invite_Links, invite_id).token


def remove_member(app: Flask, utub_id: int, user_id: int) -> None:
    """Remove a member from a UTub, in place, leaving their Utub_Urls rows behind.

    Args:
        app (Flask): The Flask client for providing an app context
        utub_id (int): The ID of the UTub to remove the member from
        user_id (int): The ID of the member to remove
    """
    with app.app_context():
        member: Utub_Members = Utub_Members.query.get((utub_id, user_id))
        db.session.delete(member)
        db.session.commit()


def url_schema_for_viewer(
    utub_url: Utub_Urls, viewer_id: int, viewer_is_manager: bool
) -> UtubUrlSchema:
    """Serialize a Utub_Urls row for a viewer with the real member-id set of its UTub.

    Must be called inside an app context (reads ``Utub_Members``).

    Args:
        utub_url (Utub_Urls): The URL row to serialize
        viewer_id (int): The viewing user's ID
        viewer_is_manager (bool): Whether the viewer is the UTub's creator or co-creator

    Returns:
        (UtubUrlSchema): The wire schema, with ``canDelete`` per the orphan rule
    """
    member_ids: frozenset[int] = frozenset(
        member.user_id
        for member in Utub_Members.query.filter(
            Utub_Members.utub_id == utub_url.utub_id
        ).all()
    )
    return UtubUrlSchema.from_orm_url(
        utub_url,
        viewer_id,
        viewer_is_manager,
        member_ids,
        visible_member_ids=None,
    )


def get_utub_url_id(app: Flask, utub_id: int, url_id: int) -> int:
    """Look up the Utub_Urls row ID for a URL inside a UTub.

    Args:
        app (Flask): The Flask client for providing an app context
        utub_id (int): The ID of the UTub holding the URL
        url_id (int): The ID of the standalone URL

    Returns:
        (int): The ID of the Utub_Urls row
    """
    with app.app_context():
        utub_url: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id, Utub_Urls.url_id == url_id
        ).one()
        return utub_url.id


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
    # Recreate model tables from the model metadata: reflection skips
    # expression-based indexes (MetricFlows' lower("displayName") unique index).
    reflected_only_tables = [
        table for name, table in meta.tables.items() if name not in db.metadata.tables
    ]
    meta.create_all(tables=reflected_only_tables)
    db.metadata.create_all(engine)


def create_secondary_app(config: type[ConfigTest]) -> Flask:
    """
    Build a second full app without clobbering the shared test app's
    process-wide state (the session-scoped `build_app` in tests/conftest.py).

    `create_app` mutates two process-wide singletons that every app built in
    the same xdist worker shares:
      - the `backend` app logger (and `cli_logger`): `configure_logging` sets
        `propagate = False` and adds a StreamHandler, undoing `build_app`'s
        `propagate = True` and silently emptying `caplog.records` for every
        later test in that worker;
      - Authlib's module-level `oauth` registry: `oauth.init_app` and
        `oauth.register` overwrite the `google`/`github` clients `build_app`
        registered with dummy credentials.
    Snapshot both before the call and restore them afterwards.

    `limiter` and `metrics_writer` are also module-level singletons that
    `create_app` re-initializes, but for `ConfigTest` both end in the same
    state `build_app` leaves them (limiter disabled, metrics disabled), so
    they are not restored here. Extend the snapshot if `config` diverges.
    """
    touched_loggers: list[Logger] = [getLogger("backend"), getLogger("cli_logger")]
    saved_logger_states: list[tuple[Logger, bool, int, list[Handler]]] = [
        (logger, logger.propagate, logger.level, list(logger.handlers))
        for logger in touched_loggers
    ]
    # Authlib keeps registrations in private instance attributes: `register`
    # mutates the `_registry`/`_clients` dicts in place (so copy them), while
    # `init_app` rebinds `app` (so keep the original reference, never a copy).
    saved_oauth_state: dict[str, Any] = {
        attribute: dict(value) if isinstance(value, dict) else value
        for attribute, value in vars(oauth).items()
    }
    try:
        app = create_app(config)
    finally:
        for logger, propagate, level, handlers in saved_logger_states:
            logger.propagate = propagate
            logger.setLevel(level)
            logger.handlers = handlers
        vars(oauth).clear()
        vars(oauth).update(saved_oauth_state)
    assert app is not None
    return app


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
