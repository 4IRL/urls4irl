from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm.util import AliasedClass
from sqlalchemy.sql.expression import ColumnElement, Select

from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs

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


def trashed_url_rows_actionable_by(*, user_id: int) -> Select:
    """Select the trashed URL rows ``user_id`` may list, restore or permanently delete.

    Single source of truth for the Trash list and every Trash action: the list, URL
    restore/purge and Empty trash narrow and lock this exact ``Select`` instead of
    re-deriving the rule in Python.

    A row is actionable when either:
      * its UTub is trashed and ``user_id`` created it (the whole UTub's URLs ride along
        with it, whatever their own ``deleted_at``); or
      * its UTub is live, the URL is trashed, and ``user_id`` added it or is the UTub's
        creator or a co-creator.

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
