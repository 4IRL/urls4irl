from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import aliased, contains_eager
from sqlalchemy.orm.util import AliasedClass
from sqlalchemy.sql.expression import ColumnElement, Select

from backend import db
from backend.models.urls import Urls
from backend.models.user_preferences import (
    User_Preferences,
    UtubSort,
    resolve_preferences,
)
from backend.models.users import Users
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.schemas.users import UtubListPreferencesSchema
from backend.utils.datetime_utils import truncate_to_milliseconds

# The shared Trash clock and deleter of a URL row: a row trashed only because its UTub
# was (its own ``deleted_at`` is NULL) inherits the UTub's, while a URL trashed on its
# own earlier keeps its own. The Trash list and Empty trash both bound and order by
# these exact expressions, so they cannot disagree on when or by whom a row was trashed.
# Only valid in a statement that selects ``Utub_Urls`` joined to ``Utubs``.
effective_deleted_at: ColumnElement = func.coalesce(
    Utub_Urls.deleted_at, Utubs.deleted_at
)
effective_deleted_by: ColumnElement = func.coalesce(
    Utub_Urls.deleted_by, Utubs.deleted_by
)


def join_url_row_deleter(statement: Select, deleter: AliasedClass) -> Select:
    """Inner-join ``deleter`` (an alias of ``Users``) to a trashed URL row's deleter.

    Deliberately an inner join: services always set ``deleted_by`` together with
    ``deleted_at``, so a trashed row with a NULL ``deleted_by`` matches no user and is
    dropped (fail closed) from the list and from Empty trash alike.
    """
    return statement.join(deleter, deleter.id == effective_deleted_by)


def join_utub_deleter(statement: Select, deleter: AliasedClass) -> Select:
    """Inner-join ``deleter`` (an alias of ``Users``) to a trashed UTub's deleter.

    Inner for the same fail-closed reason as ``join_url_row_deleter``.
    """
    return statement.join(deleter, deleter.id == Utubs.deleted_by)


def adder_not_member_clause() -> ColumnElement[bool]:
    """SQL twin of the orphan rule in ``can_act_as_url_adder`` (#770).

    True when the URL row's adder is no longer a member of its UTub. Correlated to
    ``Utub_Urls`` via a fresh alias of ``Utub_Members``: the alias keeps it independent
    of any viewer ``Utub_Members`` join in the enclosing select (a bare ``Utub_Members``
    would auto-correlate to that join and test the viewer's row instead).
    """
    adder_membership = aliased(Utub_Members)
    return ~(
        select(adder_membership.user_id)
        .where(
            adder_membership.utub_id == Utub_Urls.utub_id,
            adder_membership.user_id == Utub_Urls.user_id,
        )
        .exists()
    )


def trashed_url_rows_actionable_by(*, user_id: int) -> Select:
    """Select the trashed URL rows ``user_id`` may list, restore or permanently delete.

    Single source of truth for the Trash list and every Trash action: the list, URL
    restore/purge and Empty trash narrow and lock this exact ``Select`` instead of
    re-deriving the rule in Python.

    A row is actionable when either:
      * its UTub is trashed and ``user_id`` created it (the whole UTub's URLs ride along
        with it, whatever their own ``deleted_at``); or
      * its UTub is live, the URL is trashed, and ``user_id`` added it, is the UTub's
        creator or a co-creator, or the adder is no longer a member (orphan rule, #770).

    The inner join on ``Utub_Members`` also drops users who have left the UTub.
    """
    return (
        select(Utub_Urls, Utubs, Utub_Members)
        .join(Utubs, Utubs.id == Utub_Urls.utub_id)
        .join(
            Utub_Members,
            and_(
                Utub_Members.utub_id == Utub_Urls.utub_id,
                Utub_Members.user_id == user_id,
            ),
        )
        .where(
            or_(
                and_(
                    Utubs.deleted_at.isnot(None),
                    Utubs.utub_creator == user_id,
                ),
                and_(
                    Utubs.deleted_at.is_(None),
                    Utub_Urls.deleted_at.isnot(None),
                    or_(
                        Utub_Urls.user_id == user_id,
                        adder_not_member_clause(),
                        Utub_Members.member_role.in_(
                            [Member_Role.CREATOR, Member_Role.CO_CREATOR]
                        ),
                    ),
                ),
            )
        )
    )


def trashed_utubs_actionable_by(*, user_id: int) -> Select:
    """Select the trashed UTubs ``user_id`` may list, restore or permanently delete.

    Only the creator of a trashed UTub acts on it, and only while still a member row.
    """
    return (
        select(Utubs, Utub_Members)
        .join(
            Utub_Members,
            and_(
                Utub_Members.utub_id == Utubs.id,
                Utub_Members.user_id == user_id,
            ),
        )
        .where(
            Utubs.deleted_at.isnot(None),
            Utubs.utub_creator == user_id,
        )
    )


def count_trash_rows_for_user(*, user_id: int) -> int:
    """Count the Trash URL rows plus Trash UTub rows ``user_id`` may act on.

    Invariant: the result always equals ``len(urls) + len(utubs)`` of the Trash list for
    the same user. It wraps the same predicates and the same inner joins (deleter, adder,
    URL) that ``read_trash.get_trash_for_user`` uses, so a row the list drops (for
    example one with a NULL ``deleted_by``) is not counted either.
    """
    adder = aliased(Users)
    url_statement = join_url_row_deleter(
        trashed_url_rows_actionable_by(user_id=user_id)
        .join(Urls, Urls.id == Utub_Urls.url_id)
        .join(adder, adder.id == Utub_Urls.user_id),
        aliased(Users),
    )
    utub_statement = join_utub_deleter(
        trashed_utubs_actionable_by(user_id=user_id), aliased(Users)
    )
    url_count = db.session.scalar(
        select(func.count()).select_from(url_statement.subquery())
    )
    utub_count = db.session.scalar(
        select(func.count()).select_from(utub_statement.subquery())
    )
    return (url_count or 0) + (utub_count or 0)


@dataclass(frozen=True)
class SummaryRows:
    """Everything ``UtubSummaryListSchema.from_user`` renders, loaded and sorted."""

    memberships: list[Utub_Members]
    counts: dict[int, tuple[int, int]]
    preferences: UtubListPreferencesSchema


def _sort_summary_memberships(
    memberships: list[Utub_Members], utub_sort: UtubSort
) -> list[Utub_Members]:
    """Sort by the chosen option with ``utub.id`` ascending as the final tie-break.

    Every timestamp is millisecond-truncated first so rows differing only below 1 ms
    tie exactly as they do in the browser. Sorting by id first and then applying a
    stable sort on the key keeps the id tie-break for both directions.
    """
    by_id = sorted(memberships, key=lambda membership: membership.to_utub.id)

    def recency(membership: Utub_Members) -> datetime:
        last_updated = truncate_to_milliseconds(membership.to_utub.last_updated)
        if membership.last_opened_at is None:
            return last_updated
        return max(truncate_to_milliseconds(membership.last_opened_at), last_updated)

    def last_opened(membership: Utub_Members) -> tuple[int, datetime]:
        # Opened rows (flag 1) first by open time; never-opened rows after, by created.
        if membership.last_opened_at is None:
            return (0, truncate_to_milliseconds(membership.to_utub.created_at))
        return (1, truncate_to_milliseconds(membership.last_opened_at))

    if utub_sort == UtubSort.LAST_OPENED:
        return sorted(by_id, key=last_opened, reverse=True)
    if utub_sort == UtubSort.NAME_AZ:
        return sorted(by_id, key=lambda membership: membership.to_utub.name.casefold())
    if utub_sort in (UtubSort.NEWEST_CREATED, UtubSort.OLDEST_CREATED):
        return sorted(
            by_id,
            key=lambda membership: truncate_to_milliseconds(
                membership.to_utub.created_at
            ),
            reverse=utub_sort == UtubSort.NEWEST_CREATED,
        )
    if utub_sort == UtubSort.RECENT_ACTIVITY:
        return sorted(by_id, key=recency, reverse=True)
    raise ValueError(f"Unhandled UTub sort: {utub_sort!r}")


def load_summary_memberships_and_counts(user_id: int) -> SummaryRows:
    """Load a user's live UTub memberships (eager ``to_utub``), sorted by their saved
    sort, with per-UTub (url_count, member_count) and the resolved list preferences.

    The single producer behind ``/home``, ``GET /utubs`` and ``GET /api/v1/utubs``:
    a constant number of statements regardless of how many UTubs the user is in.
    """
    preferences_row = db.session.scalar(
        select(User_Preferences).where(User_Preferences.user_id == user_id)
    )
    resolved = resolve_preferences(preferences_row)

    memberships = list(
        db.session.scalars(
            select(Utub_Members)
            .join(Utubs, Utubs.id == Utub_Members.utub_id)
            .where(Utub_Members.user_id == user_id, Utubs.deleted_at.is_(None))
            .options(contains_eager(Utub_Members.to_utub))
            # Refresh already-loaded Utubs/Utub_Members rows (stale identity map would
            # hide a fresh last_opened_at and skew the statement-count test).
            .execution_options(populate_existing=True)
        ).all()
    )
    utub_ids = [membership.to_utub.id for membership in memberships]

    counts: dict[int, tuple[int, int]] = {utub_id: (0, 0) for utub_id in utub_ids}
    if utub_ids:
        url_counts = dict(
            db.session.execute(
                select(Utub_Urls.utub_id, func.count())
                .where(Utub_Urls.utub_id.in_(utub_ids), Utub_Urls.deleted_at.is_(None))
                .group_by(Utub_Urls.utub_id)
            ).all()
        )
        member_counts = dict(
            db.session.execute(
                select(Utub_Members.utub_id, func.count())
                .where(Utub_Members.utub_id.in_(utub_ids))
                .group_by(Utub_Members.utub_id)
            ).all()
        )
        counts = {
            utub_id: (url_counts.get(utub_id, 0), member_counts.get(utub_id, 0))
            for utub_id in utub_ids
        }

    return SummaryRows(
        memberships=_sort_summary_memberships(memberships, resolved.utub_sort),
        counts=counts,
        preferences=UtubListPreferencesSchema(
            utub_sort=resolved.utub_sort.value,
            show_row_counts=resolved.show_row_counts,
            show_list_totals=resolved.show_list_totals,
        ),
    )
