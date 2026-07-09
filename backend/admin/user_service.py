from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import or_

from backend.models.users import Users

DEFAULT_SEARCH_LIMIT: int = 20

_LIKE_ESCAPE_CHAR: str = "\\"


@dataclass(frozen=True)
class UserSearchPage:
    """One page of admin user-search results."""

    users: list[Users]
    total_count: int
    query: str
    limit: int
    offset: int

    @property
    def has_previous(self) -> bool:
        return self.offset > 0

    @property
    def has_next(self) -> bool:
        return self.offset + self.limit < self.total_count

    @property
    def previous_offset(self) -> int:
        return max(self.offset - self.limit, 0)

    @property
    def next_offset(self) -> int:
        return self.offset + self.limit


def _escape_like_wildcards(raw_query: str) -> str:
    r"""Escape SQL LIKE wildcards so user input matches literally.

    Example: ``"50%_off"`` becomes ``"50\%\_off"`` — without this, a query
    of ``"%"`` would match every user.
    """
    return (
        raw_query.replace(_LIKE_ESCAPE_CHAR, _LIKE_ESCAPE_CHAR * 2)
        .replace("%", _LIKE_ESCAPE_CHAR + "%")
        .replace("_", _LIKE_ESCAPE_CHAR + "_")
    )


def search_users(
    *,
    query: str,
    limit: int = DEFAULT_SEARCH_LIMIT,
    offset: int = 0,
) -> UserSearchPage:
    """Case-insensitive substring search over username and email.

    A blank query returns the first page of all users (ordered by id) so
    the admin page is immediately useful on load. Results are always
    ordered by id for stable pagination.

    Example: ``search_users(query="test", limit=2, offset=2)`` returns the
    third and fourth users whose username or email contains "test".
    """
    normalized_query = query.strip()
    users_query = Users.query
    if normalized_query:
        like_pattern = f"%{_escape_like_wildcards(normalized_query)}%"
        users_query = users_query.filter(
            or_(
                Users.username.ilike(like_pattern, escape=_LIKE_ESCAPE_CHAR),
                Users.email.ilike(like_pattern, escape=_LIKE_ESCAPE_CHAR),
            )
        )
    total_count = users_query.count()
    matched_users = users_query.order_by(Users.id).limit(limit).offset(offset).all()
    return UserSearchPage(
        users=matched_users,
        total_count=total_count,
        query=normalized_query,
        limit=limit,
        offset=offset,
    )


def get_user_detail(*, user_id: int) -> Users | None:
    """The user row for the admin detail page, or None when absent.

    Memberships (``utubs_is_member_of`` → ``to_utub``) and OAuth identities
    load lazily on template access — acceptable for a single-user admin
    page.
    """
    return Users.query.get(user_id)
