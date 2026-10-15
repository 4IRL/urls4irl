from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from backend import db
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.app_logger import safe_add_log
from backend.models.urls import Urls
from backend.models.users import Users
from backend.models.utub_members import Utub_Members
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.schemas.trash import (
    TrashedUrlItemSchema,
    TrashedUtubItemSchema,
    TrashListResponseSchema,
)
from backend.utils.datetime_utils import utc_now
from backend.utubs.services.trash_predicates import (
    trashed_url_rows_actionable_by,
    trashed_utubs_actionable_by,
)
from scripts.trash_retention import TRASH_RETENTION_DAYS


def _expires_at(deleted_at: datetime) -> datetime:
    """Return when a row trashed at ``deleted_at`` leaves the retention window."""
    return deleted_at + timedelta(days=TRASH_RETENTION_DAYS)


def get_trash_for_user(*, current_user_id: int) -> FlaskResponse:
    """List everything in Trash the given user may act on.

    Visibility comes entirely from ``trash_predicates`` so the list, restore and purge
    never disagree. A URL row inherits its UTub's trash clock and deleter when it was
    trashed only because the UTub was (its own ``deleted_at`` is NULL); a URL trashed
    on its own earlier keeps its own, earlier clock.

    Deleter joins are deliberately inner joins: services always set ``deleted_by``
    together with ``deleted_at``, so a trashed row with a NULL ``deleted_by`` is
    intentionally not listed (fail closed).

    Retention: rows past the 30-day window but not yet swept are still listed, with a
    past ``expiresAt``, until the purge sweep removes them. This is by design.

    Known limit: the list is not paginated. The 30-day retention window bounds it, so a
    user's Trash stays small enough to return in one response.

    ``listedAt`` is read before the first query, so a row committed after the list's
    snapshot is never covered by it. Residual window: a row committed between this clock
    read and the first query's snapshot is listed yet has a ``deleted_at`` after
    ``listedAt``, so Empty Trash skips it (fail closed: it stays for the next list).
    """
    listed_at: datetime = utc_now()
    adder = aliased(Users)
    deleter = aliased(Users)
    effective_deleted_at = func.coalesce(Utub_Urls.deleted_at, Utubs.deleted_at)
    effective_deleted_by = func.coalesce(Utub_Urls.deleted_by, Utubs.deleted_by)

    url_rows = db.session.execute(
        trashed_url_rows_actionable_by(user_id=current_user_id)
        .add_columns(Urls.url_string, adder.username, deleter.username)
        .join(Urls, Urls.id == Utub_Urls.url_id)
        .join(adder, adder.id == Utub_Urls.user_id)
        .join(deleter, deleter.id == effective_deleted_by)
        .order_by(effective_deleted_at.desc(), Utub_Urls.id.desc())
    ).all()

    urls: list[TrashedUrlItemSchema] = []
    for (
        utub_url,
        utub,
        _member,
        url_string,
        adder_username,
        deleter_username,
    ) in url_rows:
        deleted_at: datetime = utub_url.deleted_at or utub.deleted_at
        urls.append(
            TrashedUrlItemSchema(
                utub_url_id=utub_url.id,
                url_string=url_string,
                url_title=utub_url.url_title,
                utub_id=utub.id,
                utub_name=utub.name,
                origin_utub_trashed=utub.deleted_at is not None,
                origin_utub_locked=utub.is_locked,
                trashed_with_utub=utub_url.deleted_at is None,
                deleted_at=deleted_at,
                expires_at=_expires_at(deleted_at),
                deleted_by_user_id=utub_url.deleted_by or utub.deleted_by,
                deleted_by_username=deleter_username,
                added_by_user_id=utub_url.user_id,
                added_by_username=adder_username,
                can_restore=not utub.is_locked,
                can_delete=not utub.is_locked,
            )
        )

    viewer_trashed_utub_ids = select(Utubs.id).where(
        Utubs.deleted_at.isnot(None), Utubs.utub_creator == current_user_id
    )
    live_url_counts = (
        select(Utub_Urls.utub_id, func.count(Utub_Urls.id).label("live_url_count"))
        .where(
            Utub_Urls.deleted_at.is_(None),
            Utub_Urls.utub_id.in_(viewer_trashed_utub_ids),
        )
        .group_by(Utub_Urls.utub_id)
        .subquery()
    )
    member_counts = (
        select(Utub_Members.utub_id, func.count(Utub_Members.user_id).label("members"))
        .where(Utub_Members.utub_id.in_(viewer_trashed_utub_ids))
        .group_by(Utub_Members.utub_id)
        .subquery()
    )
    utub_rows = db.session.execute(
        trashed_utubs_actionable_by(user_id=current_user_id)
        .add_columns(
            func.coalesce(live_url_counts.c.live_url_count, 0),
            func.coalesce(member_counts.c.members, 0),
            deleter.username,
        )
        .outerjoin(live_url_counts, live_url_counts.c.utub_id == Utubs.id)
        .outerjoin(member_counts, member_counts.c.utub_id == Utubs.id)
        .join(deleter, deleter.id == Utubs.deleted_by)
        .order_by(Utubs.deleted_at.desc(), Utubs.id.desc())
    ).all()

    utubs: list[TrashedUtubItemSchema] = [
        TrashedUtubItemSchema(
            utub_id=utub.id,
            utub_name=utub.name,
            utub_description=utub.utub_description,
            deleted_at=utub.deleted_at,
            expires_at=_expires_at(utub.deleted_at),
            deleted_by_user_id=utub.deleted_by,
            deleted_by_username=deleter_username,
            url_count=url_count,
            member_count=member_count,
            is_locked=utub.is_locked,
            can_restore=not utub.is_locked,
            can_delete=not utub.is_locked,
        )
        for utub, _member, url_count, member_count, deleter_username in utub_rows
    ]

    safe_add_log(f"Listing Trash for User={current_user_id}")
    return APIResponse(
        data=TrashListResponseSchema(
            urls=urls,
            utubs=utubs,
            current_user=current_user_id,
            retention_days=TRASH_RETENTION_DAYS,
            listed_at=listed_at,
        ),
        status_code=200,
    ).to_response()
