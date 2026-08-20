from flask import abort

from backend import db
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.app_logger import safe_add_many_logs, warning_log
from backend.extensions.metrics.writer import record_event
from backend.metrics.events import EventName
from backend.metrics.tag_batch import bucket_bulk_tag_url_count
from backend.models.utub_members import Utub_Members
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.schemas.errors import build_message_error_response
from backend.schemas.urls import (
    CopyUrlsResponseSchema,
    PerDestinationCopyResultSchema,
    UrlCopiedItemSchema,
    UrlCopySkippedSchema,
)
from backend.urls.constants import BulkCopySkipReason, DestCopyStatus, URLErrorCodes
from backend.utils.strings.model_strs import MODELS as M
from backend.utils.strings.url_strs import URL_FAILURE, URL_SUCCESS


def _copy_source_rows_into_dest(
    *,
    source_rows_in_order: list[Utub_Urls],
    dest_utub: Utubs,
    current_user_id: int,
    existing_pairs: set[tuple[int, int]],
) -> tuple[list[UrlCopiedItemSchema], list[dict]]:
    """Copy validated source rows into ONE destination. Adds+flushes rows (NO commit).

    Reads the already-present check from the prefetched `existing_pairs` set
    (`(dest_utub.id, source_row.url_id)`) rather than issuing a per-pair query, so
    the whole multi-destination request costs ONE existing-pairs prefetch instead of
    N destinations × M urls lookups. A duplicate (already in the destination) becomes
    a reported skip, not a write.

    Args:
        source_rows_in_order (list[Utub_Urls]): Validated source `Utub_Urls` rows, in
            request order.
        dest_utub (Utubs): The destination UTub to copy the rows into.
        current_user_id (int): The acting user, attributed as the adder of each copy.
        existing_pairs (set[tuple[int, int]]): Prefetched `(utub_id, url_id)` pairs
            already present across all destinations.

    Returns:
        tuple[list[UrlCopiedItemSchema], list[dict]]:
        - The `copied` item schemas (source→destination id pairs).
        - The `skipped` dicts (`{utubUrlID, reason}`) for already-present URLs.
    """
    copied_results: list[UrlCopiedItemSchema] = []
    skipped_results: list[dict] = []

    for source_row in source_rows_in_order:
        if (dest_utub.id, source_row.url_id) in existing_pairs:
            skipped_results.append(
                {
                    M.UTUB_URL_ID: source_row.id,
                    M.SKIP_REASON: BulkCopySkipReason.DUPLICATE,
                }
            )
            continue

        new_utub_url = Utub_Urls(
            utub_id=dest_utub.id,
            url_id=source_row.url_id,
            user_id=current_user_id,
            url_title=source_row.url_title,
        )
        db.session.add(new_utub_url)
        db.session.flush()  # populate new_utub_url.id before building the schema
        copied_results.append(
            UrlCopiedItemSchema(
                source_utub_url_id=source_row.id,
                utub_url_id=new_utub_url.id,
                url_string=source_row.standalone_url.url_string,
                url_title=new_utub_url.url_title,
            )
        )

    return copied_results, skipped_results


def copy_urls_into_utubs(
    source_utub_id: int,
    dest_utub_ids: list[int],
    utub_url_ids: list[int],
    current_user_id: int,
) -> FlaskResponse:
    """
    Copies selected URLs from a source UTub into one or more destination UTubs in a
    single bulk action, carrying the URL string + title only (never tags), skipping +
    reporting any URL already present in a given destination, and skipping +
    reporting any destination locked at write time.

    The endpoint carries no path param, so `@email_validation_required` only proves a
    logged-in, email-validated user; ALL source AND destination membership + lock +
    same-UTub validation is therefore performed here, all-or-nothing, before any
    write — otherwise the acting user could copy out of a source UTub or into a
    destination UTub they do not belong to (IDOR). Source non-membership AND any
    destination the user is not a member of are both masked as a 404. A locked
    destination is NOT a hard failure: it is skipped and reported per-destination
    (`status="locked"`) so the other destinations still copy (DD-3).

    The whole batch is one transaction with a single terminal commit: either it
    commits with the accumulated per-destination results, or an unexpected mid-loop
    exception rolls back every flushed row across every destination.

    Args:
        source_utub_id (int): The UTub to copy URLs FROM (validated here).
        dest_utub_ids (list[int]): Destination UTub ids to copy the selected URLs
            INTO (already deduped by the request schema; deduped again defensively).
        utub_url_ids (list[int]): The source UTub-URL ids to copy (already deduped by
            the request schema; deduped again defensively).
        current_user_id (int): The acting user; must be a member of the source AND of
            every destination UTub.

    Returns:
        FlaskResponse: A JSON partial-success report (`results` per-destination cluster
            + `totalCopied`/`totalSkipped`) at HTTP 200 (including the all-skipped and
            all-locked no-op cases), or 400 (same-UTub copy, or one or more ids are not
            URLs in the source UTub). Raises a 404 (via `abort`) when the acting user is
            not a member of the source UTub or of any destination UTub.
    """
    # Same-UTub guard (DD-4) — copying a UTub into itself is a no-op request.
    if source_utub_id in dest_utub_ids:
        return build_message_error_response(
            message=URL_FAILURE.CANNOT_COPY_TO_SAME_UTUB,
            error_code=URLErrorCodes.INVALID_FORM_INPUT,
            status_code=400,
        )

    # Source membership (masking 404) — mirrors the single-destination service.
    source_membership = Utub_Members.query.get((source_utub_id, current_user_id))
    if source_membership is None:
        abort(404)

    # Defensively de-dup ids (order-preserving), mirroring the request schema's own
    # dedup, so a direct/in-code caller cannot copy the same source row or target the
    # same destination twice.
    dest_utub_ids = list(dict.fromkeys(dest_utub_ids))
    utub_url_ids = list(dict.fromkeys(utub_url_ids))

    # All-destination membership (masking 404), ONE query (DD-4). Any destination the
    # user is not a member of masks the whole request as 404 — spoof/IDOR parity with
    # the source check.
    member_dest_ids = {
        row[0]
        for row in db.session.query(Utub_Members.utub_id)
        .filter(
            Utub_Members.user_id == current_user_id,
            Utub_Members.utub_id.in_(dest_utub_ids),
        )
        .all()
    }
    if set(dest_utub_ids) - member_dest_ids:
        abort(404)

    # All-or-nothing source-id validation (closes the IDOR), shared once across every
    # destination. A single query fetches all requested rows; any id that is unknown
    # OR belongs to a UTub other than the claimed SOURCE rejects the whole request
    # before any write.
    source_rows: list[Utub_Urls] = Utub_Urls.query.filter(
        Utub_Urls.id.in_(utub_url_ids)
    ).all()
    rows_by_id: dict[int, Utub_Urls] = {row.id: row for row in source_rows}
    if any(
        url_id not in rows_by_id or rows_by_id[url_id].utub_id != source_utub_id
        for url_id in utub_url_ids
    ):
        return build_message_error_response(
            message=URL_FAILURE.URL_NOT_IN_UTUB,
            error_code=URLErrorCodes.INVALID_FORM_INPUT,
            status_code=400,
        )
    source_rows_in_order = [rows_by_id[url_id] for url_id in utub_url_ids]

    # Fetch destination rows for lock inspection (membership already proved they
    # exist; this reads `is_locked`).
    dest_utubs_by_id: dict[int, Utubs] = {
        dest_utub.id: dest_utub
        for dest_utub in Utubs.query.filter(Utubs.id.in_(dest_utub_ids)).all()
    }

    # Prefetch existing (dest, url) pairs across ALL destinations in ONE query, so the
    # per-destination duplicate check is a set membership test, not a query per pair.
    source_url_ids = [row.url_id for row in source_rows_in_order]
    existing_pairs: set[tuple[int, int]] = {
        (row.utub_id, row.url_id)
        for row in Utub_Urls.query.filter(
            Utub_Urls.utub_id.in_(dest_utub_ids),
            Utub_Urls.url_id.in_(source_url_ids),
        ).all()
    }

    results: list[PerDestinationCopyResultSchema] = []
    total_copied = 0
    total_skipped = 0
    dests_copied_into = 0

    # The explicit rollback mirrors the single-destination service: a mid-loop
    # exception discards every flushed destination row across all destinations,
    # rather than relying on the request-teardown rollback (which the test harness's
    # SAVEPOINT does not trigger on a propagated exception).
    try:
        for dest_id in dest_utub_ids:
            dest_utub = dest_utubs_by_id[dest_id]
            if dest_utub.is_locked:  # DD-3 skip-and-report; not a write
                results.append(
                    PerDestinationCopyResultSchema(
                        dest_utub_id=dest_id,
                        status=DestCopyStatus.LOCKED,
                        copied=[],
                        skipped=[],
                    )
                )
                continue

            copied_items, skipped_dicts = _copy_source_rows_into_dest(
                source_rows_in_order=source_rows_in_order,
                dest_utub=dest_utub,
                current_user_id=current_user_id,
                existing_pairs=existing_pairs,
            )
            if copied_items:
                dest_utub.set_last_updated()
                dests_copied_into += 1
            total_copied += len(copied_items)
            total_skipped += len(skipped_dicts)
            results.append(
                PerDestinationCopyResultSchema(
                    dest_utub_id=dest_id,
                    status=DestCopyStatus.OK,
                    copied=copied_items,
                    skipped=[UrlCopySkippedSchema(**entry) for entry in skipped_dicts],
                )
            )

        # Only commit when at least one URL was actually copied; an all-already-present
        # or all-locked request is a pure no-op.
        if total_copied:
            db.session.commit()
    except Exception as exc:
        db.session.rollback()
        warning_log(
            f"Bulk multi-UTub URL copy failed | SourceUTub.id={source_utub_id} "
            f"| DestCount={len(dest_utub_ids)} | URLCount={len(utub_url_ids)} "
            f"| error_type={type(exc).__name__}"
        )
        raise

    safe_add_many_logs(
        [
            "Copied bulk URLs into multiple UTubs",
            f"SourceUTub.id={source_utub_id}",
            f"DestUTubIDs={dest_utub_ids}",
            f"URLsCopied={total_copied}",
            f"URLsSkipped={total_skipped}",
        ]
    )

    # Metrics (post-commit, dedicated aggregate event only). One event per request,
    # emitted only when at least one URL was actually copied across all destinations.
    if total_copied:
        record_event(
            EventName.URLS_COPIED_TO_UTUB,
            dimensions={
                "url_count_bucket": bucket_bulk_tag_url_count(total_copied),
                "skipped_count_bucket": bucket_bulk_tag_url_count(total_skipped),
                "destination_count_bucket": bucket_bulk_tag_url_count(
                    dests_copied_into
                ),
            },
        )

    return APIResponse(
        message=URL_SUCCESS.URLS_COPIED,
        data=CopyUrlsResponseSchema(
            results=results,
            total_copied=total_copied,
            total_skipped=total_skipped,
        ),
    ).to_response()
