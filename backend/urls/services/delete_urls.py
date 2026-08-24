from flask_login import current_user
from sqlalchemy import case, func

from backend import db
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.app_logger import safe_add_many_logs, warning_log
from backend.extensions.metrics.writer import record_event
from backend.metrics.events import EventName
from backend.metrics.tag_batch import bucket_bulk_tag_url_count
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.schemas.errors import build_message_error_response
from backend.schemas.urls import (
    DeleteUrlsResponseSchema,
    UrlDeletedResponseSchema,
    UrlDeleteSkippedSchema,
    UtubUrlDeleteSchema,
)
from backend.urls.constants import BulkDeleteSkipReason, URLErrorCodes
from backend.utils.strings.model_strs import MODELS as M
from backend.utils.strings.url_strs import URL_FAILURE, URL_SUCCESS
from backend.utubs.guards import reject_if_utub_locked


def delete_url_in_utub(
    current_utub: Utubs,
    current_utub_url: Utub_Urls,
) -> FlaskResponse:
    """
    Deletes a URL from a UTub. Returns associated tag data for the UTub.

    Args:
        current_utub (Utubs): The UTub object containing the UTub_Urls
        current_utub_url (Utub_Urls): The Utub_Urls to delete

    Returns:
        tuple[Response, int]:
        - Response: JSON response on delete
        - int: HTTP status code 200 (Success)
    """
    utub_locked_error: FlaskResponse | None = reject_if_utub_locked(
        current_utub, error_code=URLErrorCodes.UTUB_IS_LOCKED
    )
    if utub_locked_error is not None:
        return utub_locked_error

    # Store serialized data from URL association with UTub and associated tags
    url_id_to_remove = current_utub_url.standalone_url.id
    utub_url_id = current_utub_url.id

    url_schema = UtubUrlDeleteSchema.from_orm_url(current_utub_url)
    tag_ids_and_updated_count = _update_tag_counts_on_url_delete(
        current_utub_url, current_utub
    )

    db.session.delete(current_utub_url)
    current_utub.set_last_updated()

    db.session.commit()

    record_event(EventName.URL_REMOVED_FROM_UTUB)

    safe_add_many_logs(
        [
            "Deleted UTubURL and associated UTubURLTags",
            f"User.id={current_user.id}",
            f"UTub.id={current_utub.id}",
            f"UTubURL.id={utub_url_id}",
            f"URL.id={url_id_to_remove}",
        ]
    )

    return APIResponse(
        message=URL_SUCCESS.URL_REMOVED,
        data=UrlDeletedResponseSchema(
            utub_id=current_utub.id,
            url=url_schema,
            tag_counts_modified=tag_ids_and_updated_count,
        ),
    ).to_response()


def _update_tag_counts_on_url_delete(
    current_utub_url: Utub_Urls, current_utub: Utubs
) -> dict[int, int]:
    """
    Update tag usage counts when deleting a URL and remove all associated tag relationships.

    Retrieves all tags associated with the URL being deleted, removes the tag associations
    from the database, and calculates updated tag counts for the UTub. This ensures tag
    counts accurately reflect the removal of the URL.

    Args:
        current_utub_url (Utub_Urls): The Utub_Urls object representing the URL being deleted.
        current_utub (Utubs): The UTub object from which the URL is being removed.

    Returns:
        dict[int, int]: A dictionary mapping tag IDs to their updated counts (decremented by 1)
        for all tags that were associated with the deleted URL.
    """
    # Find all rows corresponding to tags on the URL to be deleted in current UTub
    utub_url_tag_ids, utub_tag_ids = _get_utub_url_tag_ids_and_utub_tag_ids_on_utub_url(
        utub_id=current_utub.id, utub_url_id=current_utub_url.id
    )

    # Count instances of tags in UTub that were unique to the URL to be deleted
    tag_ids_and_count = _get_utub_url_tag_ids_and_count_in_utub(
        utub_id=current_utub.id, utub_tag_ids=utub_tag_ids
    )

    # Remove all tags associated with this URL in this UTub
    db.session.query(Utub_Url_Tags).filter(Utub_Url_Tags.id.in_(utub_url_tag_ids)).delete()  # type: ignore

    # Update utub tag count after successful removal of all tags associated with deleted URL
    return {t[0]: t[1] - 1 for t in tag_ids_and_count}


def _get_utub_url_tag_ids_and_utub_tag_ids_on_utub_url(
    utub_id: int, utub_url_id: int
) -> tuple[list[int], list[int]]:
    primary_key_and_tag_ids = (
        db.session.query(Utub_Url_Tags)
        .filter(
            Utub_Url_Tags.utub_id == utub_id,
            Utub_Url_Tags.utub_url_id == utub_url_id,
        )
        .with_entities(Utub_Url_Tags.id, Utub_Url_Tags.utub_tag_id)
        .all()
    )
    return _parse_utub_url_tag_ids_and_utub_tag_ids(primary_key_and_tag_ids)


def _parse_utub_url_tag_ids_and_utub_tag_ids(
    primary_key_and_tag_ids: list[Utub_Url_Tags],
) -> tuple[list[int], list[int]]:
    utub_tag_ids = []
    utub_url_tag_ids = []

    for utub_url_tag_id, utub_tag_id in primary_key_and_tag_ids:
        utub_tag_ids.append(utub_tag_id)
        utub_url_tag_ids.append(utub_url_tag_id)

    return utub_url_tag_ids, utub_tag_ids


def _get_utub_url_tag_ids_and_count_in_utub(
    utub_id: int, utub_tag_ids: list[int]
) -> list[tuple[int, int]]:
    tag_ids_and_count_in_utub = (
        db.session.query(
            Utub_Url_Tags.utub_tag_id,
            case([(func.count() > 0, func.count() - 1)], else_=0).label("count"),
        )
        .filter(
            Utub_Url_Tags.utub_id == utub_id,
            Utub_Url_Tags.utub_tag_id.in_(utub_tag_ids),
        )
        .group_by(Utub_Url_Tags.utub_tag_id)
        .all()
    )
    return tag_ids_and_count_in_utub


def _recompute_tag_counts_after_bulk_delete(
    *, utub_id: int, affected_utub_tag_ids: set[int]
) -> dict[int, int]:
    """
    Recompute the UTub-wide applied count for every tag touched by a bulk URL delete,
    in a single grouped query, AFTER the deletable URLs and their tag associations have
    been removed.

    A bare grouped ``COUNT`` cannot report ``0`` for a tag whose last associated URL was
    just deleted — ``GROUP BY`` simply omits rows with no matches (the same trap
    documented on ``get_tag_applied_counts`` in
    ``backend/tags/services/create_url_tag.py``: "Tag ids with zero applications are
    absent from the mapping"). The backfill is therefore explicit: seed every affected
    tag id to ``0`` first, then overwrite from the grouped ``COUNT`` results so tags with
    remaining applications reflect their live count and tags fully emptied by the delete
    keep ``0``.

    This single post-batch recompute replaces per-URL decrement arithmetic, avoiding the
    shared-tag double-decrement that a naive per-URL loop would produce when two deleted
    URLs share a tag.

    Args:
        utub_id (int): The UTub the bulk delete acted on.
        affected_utub_tag_ids (set[int]): Every UTub tag id that was associated with at
            least one deleted URL.

    Returns:
        dict[int, int]: A mapping of every affected tag id to its updated UTub-wide
        applied count, including ``0`` for tags whose last URL was deleted.
    """
    tag_counts: dict[int, int] = {tag_id: 0 for tag_id in affected_utub_tag_ids}
    if not affected_utub_tag_ids:
        return tag_counts

    count_rows = (
        db.session.query(
            Utub_Url_Tags.utub_tag_id, func.count(Utub_Url_Tags.utub_tag_id)
        )
        .filter(
            Utub_Url_Tags.utub_id == utub_id,
            Utub_Url_Tags.utub_tag_id.in_(affected_utub_tag_ids),
        )
        .group_by(Utub_Url_Tags.utub_tag_id)
        .all()
    )
    for utub_tag_id, remaining_count in count_rows:
        tag_counts[utub_tag_id] = remaining_count

    return tag_counts


def delete_urls_in_utub(
    *, utub_url_ids: list[int], utub: Utubs, current_user_id: int
) -> FlaskResponse:
    """
    Bulk-delete selected URLs from a single UTub in one transaction, skipping and
    reporting any URL the acting user may not delete (partial-with-report).

    Per-URL permission is the *literal*-creator predicate
    ``current_user_id == utub_url.user_id or current_user_id == utub.utub_creator`` —
    the exact predicate ``UtubUrlSchema.from_orm_url`` computes as ``can_delete`` — and
    deliberately NOT the broader, co-creator-inclusive ``g.is_creator``. This keeps
    server enforcement aligned with the client's ``canDelete``-derived deletable
    snapshot, so a co-creator's request never contains an id the server would reject.

    The whole batch is one transaction with a single terminal commit: unknown or
    cross-UTub ids reject the entire request as a 400 before any write (a foreign id is
    a spoof, not a skip); a locked UTub rejects the whole request as a 403; an
    unexpected mid-loop exception rolls back every removed row via an explicit rollback.
    Affected tag counts are recomputed ONCE post-batch to avoid the shared-tag
    double-decrement.

    Args:
        utub_url_ids (list[int]): The UTub-URL ids to delete (already deduped by the
            request schema; deduped again defensively).
        utub (Utubs): The UTub the URLs belong to (membership already proved by
            ``@utub_membership_required``). Its ``utub_creator`` drives the per-URL
            permission check directly.
        current_user_id (int): The acting user.

    Returns:
        FlaskResponse: A JSON partial-success report (``deleted``/``skipped`` +
            ``tagCountsInUtub`` + ``totalDeleted``/``totalSkipped``) at HTTP 200
            (including the all-skipped no-op case), or 400 (one or more ids are not URLs
            in this UTub), or 403 (the UTub is locked).
    """
    utub_locked_error: FlaskResponse | None = reject_if_utub_locked(
        utub, error_code=URLErrorCodes.UTUB_IS_LOCKED
    )
    if utub_locked_error is not None:
        return utub_locked_error

    # Defensively de-dup ids (order-preserving), mirroring the request schema's own
    # dedup, so a direct/in-code caller cannot request the same row twice.
    utub_url_ids = list(dict.fromkeys(utub_url_ids))

    # One-query all-or-nothing id validation: any unknown id OR any id belonging to a
    # UTub other than this one rejects the whole request BEFORE any write.
    requested_rows: list[Utub_Urls] = Utub_Urls.query.filter(
        Utub_Urls.id.in_(utub_url_ids)
    ).all()
    rows_by_id: dict[int, Utub_Urls] = {row.id: row for row in requested_rows}
    if any(
        utub_url_id not in rows_by_id or rows_by_id[utub_url_id].utub_id != utub.id
        for utub_url_id in utub_url_ids
    ):
        return build_message_error_response(
            message=URL_FAILURE.URLS_NOT_IN_UTUB,
            error_code=URLErrorCodes.INVALID_FORM_INPUT,
            status_code=400,
        )

    # Partition by the literal-creator permission predicate (matches can_delete on
    # UtubUrlSchema; deliberately narrower than g.is_creator).
    deletable_rows: list[Utub_Urls] = []
    skipped: list[dict] = []
    for utub_url_id in utub_url_ids:
        row = rows_by_id[utub_url_id]
        can_delete = (
            row.user_id == current_user_id or current_user_id == utub.utub_creator
        )
        if can_delete:
            deletable_rows.append(row)
        else:
            skipped.append(
                {
                    M.UTUB_URL_ID: row.id,
                    M.SKIP_REASON: BulkDeleteSkipReason.FORBIDDEN,
                }
            )

    # Capture serialized delete data + every affected tag id BEFORE deletion.
    deleted_url_schemas: list[UtubUrlDeleteSchema] = []
    affected_utub_tag_ids: set[int] = set()
    for row in deletable_rows:
        deleted_url_schemas.append(UtubUrlDeleteSchema.from_orm_url(row))
        affected_utub_tag_ids.update(row.associated_tag_ids)

    total_deleted = len(deletable_rows)
    total_skipped = len(skipped)

    # The explicit rollback mirrors the single-delete + copy services: a mid-loop
    # exception discards every removed row rather than relying on the request-teardown
    # rollback (which the test harness's SAVEPOINT does not trigger on a propagated
    # exception).
    tag_counts: dict[int, int] = {}
    try:
        for row in deletable_rows:
            db.session.query(Utub_Url_Tags).filter(
                Utub_Url_Tags.utub_id == utub.id,
                Utub_Url_Tags.utub_url_id == row.id,
            ).delete()
            db.session.delete(row)

        if total_deleted >= 1:
            # Flush the pending removals so the grouped recompute counts post-delete
            # state, then recompute affected tag counts ONCE.
            db.session.flush()
            tag_counts = _recompute_tag_counts_after_bulk_delete(
                utub_id=utub.id, affected_utub_tag_ids=affected_utub_tag_ids
            )
            utub.set_last_updated()
            db.session.commit()
    except Exception as exc:
        db.session.rollback()
        warning_log(
            f"Bulk URL delete failed | UTub.id={utub.id} "
            f"| URLCount={len(utub_url_ids)} "
            f"| error_type={type(exc).__name__}"
        )
        raise

    # Post-commit logs + metric, only when at least one URL was actually deleted.
    if total_deleted >= 1:
        safe_add_many_logs(
            [
                "Bulk-deleted UTubURLs and associated UTubURLTags",
                f"User.id={current_user_id}",
                f"UTub.id={utub.id}",
                f"URLsDeleted={total_deleted}",
                f"URLsSkipped={total_skipped}",
            ]
        )
        record_event(
            EventName.URLS_DELETED_FROM_UTUB,
            dimensions={
                "url_count_bucket": bucket_bulk_tag_url_count(total_deleted),
                "skipped_count_bucket": bucket_bulk_tag_url_count(total_skipped),
            },
        )

    return APIResponse(
        message=URL_SUCCESS.URLS_DELETED,
        data=DeleteUrlsResponseSchema(
            deleted=deleted_url_schemas,
            skipped=[UrlDeleteSkippedSchema(**entry) for entry in skipped],
            tag_counts_modified=tag_counts,
            total_deleted=total_deleted,
            total_skipped=total_skipped,
        ),
    ).to_response()
