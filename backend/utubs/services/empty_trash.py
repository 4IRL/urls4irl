from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import aliased

from backend import db
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.app_logger import safe_add_many_logs, warning_log
from backend.extensions.metrics.writer import record_event
from backend.metrics.events import EventName
from backend.metrics.tag_batch import bucket_bulk_tag_url_count
from backend.models.users import Users
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.schemas.errors import build_message_error_response
from backend.schemas.trash import TrashEmptiedResponseSchema
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.trash_strs import TRASH_FAILURE, TRASH_SUCCESS
from backend.utubs.constants import TrashScope, UTubErrorCodes
from backend.utubs.guards import lock_trashed_utub_for_creator
from backend.utubs.services.trash_predicates import (
    trashed_url_rows_actionable_by,
    trashed_utubs_actionable_by,
)


def _purge_trashed_url_ids(*, ids: list[int], listed_at: datetime) -> list[int]:
    """Delete the given ``Utub_Urls`` rows still in Trash as listed, in one statement.

    The list's own semantics are re-applied inside the ``DELETE`` itself: the row's
    effective trash time (its own ``deleted_at``, else its UTub's) must be set and
    ``<= listed_at`` (a NULL effective time never matches, which is what "in Trash"
    means), and its UTub must not be locked. A row restored, re-trashed after
    ``listed_at``, or whose UTub was restored or locked since the caller selected its id
    is simply not matched. That makes the returned ids, not the caller's candidate list,
    the truth about what was deleted. Fail closed: anything the condition cannot prove
    is left in Trash.

    ``Utub_Url_Tags.utub_url_id`` is ``ON DELETE CASCADE`` to ``Utub_Urls.id``, so the
    database removes the deleted rows' tag associations in the same statement; a row
    the re-applied condition excludes never has its tags touched. The shared ``Urls``
    rows are kept. ``synchronize_session`` must be ``False``: the subquery conditions
    cannot be evaluated in Python, and the stale ORM objects of the preceding select
    are never read again.

    Args:
        ids (list[int]): Candidate ``Utub_Urls`` ids selected as purgeable
        listed_at (datetime): Upper bound (inclusive) on the effective trash time

    Returns:
        list[int]: The ids actually deleted, ascending.
    """
    if not ids:
        return []

    utub_deleted_at = (
        select(Utubs.deleted_at).where(Utubs.id == Utub_Urls.utub_id).scalar_subquery()
    )
    locked_utub_ids = select(Utubs.id).where(Utubs.is_locked.is_(True))
    deleted_ids: list[int] = (
        db.session.execute(
            delete(Utub_Urls)
            .where(
                Utub_Urls.id.in_(ids),
                func.coalesce(Utub_Urls.deleted_at, utub_deleted_at) <= listed_at,
                Utub_Urls.utub_id.not_in(locked_utub_ids),
            )
            .returning(Utub_Urls.id)
            .execution_options(synchronize_session=False)
        )
        .scalars()
        .all()
    )
    return sorted(deleted_ids)


def _empty_urls_tab(
    *, listed_at: datetime, current_user_id: int
) -> tuple[list[int], int]:
    """Delete the caller's actionable trashed URLs that entered Trash by ``listed_at``.

    Candidates come from the same ``trashed_url_rows_actionable_by`` select the Trash
    list uses (and its inner join to the deleter), so exactly the rows the caller can
    see are considered. Rows of a locked UTub are counted, never purged.

    Args:
        listed_at (datetime): Upper bound (inclusive) on the effective trash time
        current_user_id (int): The acting user

    Returns:
        tuple[list[int], int]: The purged ``Utub_Urls`` ids and the number of rows
        skipped because their UTub is locked. Nothing is committed here.
    """
    deleter = aliased(Users)
    effective_deleted_at = func.coalesce(Utub_Urls.deleted_at, Utubs.deleted_at)
    effective_deleted_by = func.coalesce(Utub_Urls.deleted_by, Utubs.deleted_by)

    candidates = db.session.execute(
        trashed_url_rows_actionable_by(user_id=current_user_id)
        .with_only_columns(Utub_Urls.id, Utubs.is_locked)
        .join(deleter, deleter.id == effective_deleted_by)
        .where(effective_deleted_at <= listed_at)
        .order_by(Utub_Urls.id)
        # Lock the candidate Utub_Urls rows in ascending id order (the order_by above),
        # as _lock_actionable_trashed_url does; of= keeps the joined tables unlocked.
        .with_for_update(of=Utub_Urls)
        .execution_options(populate_existing=True)
    ).all()

    purgeable_ids: list[int] = []
    total_skipped_locked: int = 0
    for utub_url_id, utub_is_locked in candidates:
        if utub_is_locked:
            total_skipped_locked += 1
        else:
            purgeable_ids.append(utub_url_id)

    return (
        _purge_trashed_url_ids(ids=purgeable_ids, listed_at=listed_at),
        total_skipped_locked,
    )


def _empty_utubs_tab(
    *, listed_at: datetime, current_user_id: int
) -> tuple[list[int], int]:
    """Delete the caller's trashed UTubs that entered Trash by ``listed_at``.

    Candidates are walked in ascending id order, the deadlock-avoidance order used by
    the account-erasure flow, and each is row-locked and re-authorized on fresh state
    by ``lock_trashed_utub_for_creator``. A UTub that was restored, or is no longer the
    caller's, since the candidate select is skipped silently; a locked one is counted.
    Deleting the UTub removes its members through the ORM and the rest through the
    database cascade, as in the single purge.

    Args:
        listed_at (datetime): Upper bound (inclusive) on the UTub's trash time
        current_user_id (int): The acting user

    Returns:
        tuple[list[int], int]: The purged UTub ids and the number of UTubs skipped
        because they are locked. Nothing is committed here.
    """
    deleter = aliased(Users)
    candidate_ids: list[int] = list(
        db.session.execute(
            trashed_utubs_actionable_by(user_id=current_user_id)
            .with_only_columns(Utubs.id)
            .join(deleter, deleter.id == Utubs.deleted_by)
            .where(Utubs.deleted_at <= listed_at)
            .order_by(Utubs.id)
        )
        .scalars()
        .all()
    )

    purged_utub_ids: list[int] = []
    total_skipped_locked: int = 0
    for candidate_id in candidate_ids:
        guarded = lock_trashed_utub_for_creator(
            utub_id=candidate_id,
            error_code=UTubErrorCodes.UTUB_IS_LOCKED,
            not_in_trash_code=UTubErrorCodes.NOT_IN_TRASH,
            reject_locked=False,
        )
        if not isinstance(guarded, Utubs):
            continue
        utub: Utubs = guarded

        # Fresh state under the row lock: a UTub restored and trashed again after the
        # caller's list was read belongs to a later Trash view, not this one.
        if utub.deleted_at > listed_at:
            continue
        if utub.is_locked:
            total_skipped_locked += 1
            continue

        purged_utub_ids.append(candidate_id)
        db.session.delete(utub)

    return purged_utub_ids, total_skipped_locked


def empty_trash_for_user(
    *, scope: TrashScope, listed_at: datetime, current_user_id: int
) -> FlaskResponse:
    """Permanently delete everything in one Trash tab that the user listed.

    Only items that entered Trash at or before ``listed_at`` are deleted, so an item
    trashed after the user read the list is never swept. The bound is clamped to the
    server clock, so a future timestamp cannot widen it. Items in a locked UTub are
    skipped and reported. ``total_purged`` and ``total_skipped_locked`` are the
    post-operation counts, never the pre-delete candidate counts. Emptying the URLs
    tab never deletes a UTub.

    Args:
        scope (TrashScope): Which tab to empty
        listed_at (datetime): The ``listedAt`` of the Trash list the user was viewing
        current_user_id (int): The acting user

    Returns:
        FlaskResponse: 200 with the purged ids and counts (also when nothing was
        purged); 400 for a scope this service does not handle.
    """
    effective_listed_at: datetime = min(listed_at, utc_now())

    purged_utub_url_ids: list[int] = []
    purged_utub_ids: list[int] = []
    total_skipped_locked: int = 0
    emptied_event: EventName

    try:
        if scope is TrashScope.URLS:
            emptied_event = EventName.URLS_EMPTIED_FROM_TRASH
            purged_utub_url_ids, total_skipped_locked = _empty_urls_tab(
                listed_at=effective_listed_at, current_user_id=current_user_id
            )
        elif scope is TrashScope.UTUBS:
            emptied_event = EventName.UTUBS_EMPTIED_FROM_TRASH
            purged_utub_ids, total_skipped_locked = _empty_utubs_tab(
                listed_at=effective_listed_at, current_user_id=current_user_id
            )
        else:
            db.session.rollback()
            return build_message_error_response(
                message=TRASH_FAILURE.UNABLE_TO_EMPTY_TRASH,
                error_code=UTubErrorCodes.UNABLE_TO_EMPTY_TRASH_ERROR,
                status_code=400,
            )
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        warning_log(
            f"Empty Trash failed | User.id={current_user_id} "
            f"| scope={scope.value} | error_type={type(exc).__name__}"
        )
        raise

    total_purged: int = len(purged_utub_url_ids) + len(purged_utub_ids)

    if total_purged >= 1:
        record_event(
            emptied_event,
            dimensions={
                "purged_count_bucket": bucket_bulk_tag_url_count(total_purged),
                "skipped_count_bucket": bucket_bulk_tag_url_count(total_skipped_locked),
            },
        )
    safe_add_many_logs(
        [
            "Emptied Trash tab",
            f"User.id={current_user_id}",
            f"Scope={scope}",
            f"Purged count={total_purged}",
            f"Skipped locked count={total_skipped_locked}",
        ]
    )

    return APIResponse(
        message=TRASH_SUCCESS.TRASH_EMPTIED,
        data=TrashEmptiedResponseSchema(
            scope=scope.value,
            purged_utub_url_ids=purged_utub_url_ids,
            purged_utub_ids=purged_utub_ids,
            total_purged=total_purged,
            total_skipped_locked=total_skipped_locked,
        ),
    ).to_response()
