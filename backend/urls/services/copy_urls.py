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
    UrlCopiedItemSchema,
    UrlCopySkippedSchema,
)
from backend.urls.constants import BulkCopySkipReason, URLErrorCodes
from backend.urls.services.create_urls import check_url_already_in_utub
from backend.utils.strings.model_strs import MODELS as M
from backend.utils.strings.url_strs import URL_FAILURE, URL_SUCCESS
from backend.utubs.guards import reject_if_utub_locked


def copy_urls_into_utub(
    source_utub_id: int,
    utub_url_ids: list[int],
    dest_utub: Utubs,
    current_user_id: int,
) -> FlaskResponse:
    """
    Copies selected URLs from a source UTub into a destination UTub in one bulk
    action, carrying the URL string + title only (never tags) and skipping +
    reporting any URL already present in the destination.

    The route path carries only the destination `utub_id`, so
    `@utub_membership_required` guards the DESTINATION only. Source membership AND
    that each `utubUrlId` belongs to the SOURCE UTub are therefore validated here,
    all-or-nothing, before any write — otherwise a destination member could copy
    URLs out of a source UTub they do not belong to (IDOR). Source non-membership
    is masked as a 404 (matching `@utub_membership_required`), and a foreign/unknown
    id is a malformed/spoofed request rejected 400 (never a legitimate skip).

    The whole batch is one transaction with a single final commit: either it
    commits with the accumulated per-URL results, or an unexpected mid-loop
    exception rolls everything back. A duplicate (already in the destination) is a
    reported skip, not a write.

    Args:
        source_utub_id (int): The UTub to copy URLs FROM (validated here, not by the
            route decorator).
        utub_url_ids (list[int]): The source UTub-URL ids to copy (already deduped by
            the request schema; deduped again defensively here).
        dest_utub (Utubs): The destination UTub to copy URLs INTO (injected by the
            `@utub_membership_required` decorator from the path `utub_id`).
        current_user_id (int): The acting user; must be a member of the source UTub.

    Returns:
        tuple[Response, int]:
        - Response: JSON partial-success report (`copied` / `skipped`).
        - int: HTTP status code
            200 (success — including the all-already-present all-skipped case)
            400 (same-UTub copy, or one or more ids are not URLs in the source UTub)
            403 (destination UTub is locked)
        Raises a 404 (via `abort`) when the acting user is not a member of the
        source UTub (masks the source UTub's existence).
    """
    # Same-UTub guard — copying a UTub into itself is a no-op request.
    if source_utub_id == dest_utub.id:
        return build_message_error_response(
            message=URL_FAILURE.CANNOT_COPY_TO_SAME_UTUB,
            error_code=URLErrorCodes.INVALID_FORM_INPUT,
            status_code=400,
        )

    # Source membership (masking 404) — the route decorator only guards the
    # destination, so a destination member could otherwise read out of a source
    # UTub they do not belong to. Mask non-membership as 404, mirroring
    # `@utub_membership_required` (auth_decorators.py).
    source_membership = Utub_Members.query.get((source_utub_id, current_user_id))
    if source_membership is None:
        abort(404)

    # Lock guard on the DESTINATION only — the source is read-only during a copy,
    # so a locked source is not blocked.
    utub_locked_error: FlaskResponse | None = reject_if_utub_locked(
        dest_utub, error_code=URLErrorCodes.UTUB_IS_LOCKED
    )
    if utub_locked_error is not None:
        return utub_locked_error

    # Defensively de-dup ids (order-preserving), mirroring the request schema's own
    # dedup, so a direct/in-code caller cannot copy the same source row twice.
    utub_url_ids = list(dict.fromkeys(utub_url_ids))

    # All-or-nothing source-id validation (closes the IDOR). A single query fetches
    # all requested rows; any id that is unknown OR belongs to a UTub other than the
    # claimed SOURCE (NOT the destination) rejects the whole request before any write.
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

    copied_results: list[UrlCopiedItemSchema] = []
    skipped_results: list[dict] = []

    # The explicit rollback mirrors the bulk tag-apply wrapper: a mid-loop exception
    # discards every flushed destination row across all URLs, rather than relying on
    # the request-teardown rollback (which the test harness's SAVEPOINT does not
    # trigger on a propagated exception).
    try:
        for url_id in utub_url_ids:
            source_row = rows_by_id[url_id]
            if check_url_already_in_utub(dest_utub.id, source_row.url_id):
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

        # Only bump the destination modification time (and commit) when at least one
        # URL was actually copied; an all-already-present request is a pure no-op.
        if copied_results:
            dest_utub.set_last_updated()
            db.session.commit()
    except Exception as exc:
        db.session.rollback()
        warning_log(
            f"Bulk URL copy failed | SourceUTub.id={source_utub_id} "
            f"| DestUTub.id={dest_utub.id} | URLCount={len(utub_url_ids)} "
            f"| error_type={type(exc).__name__}"
        )
        raise

    safe_add_many_logs(
        [
            "Copied bulk URLs into UTub",
            f"SourceUTub.id={source_utub_id}",
            f"DestUTub.id={dest_utub.id}",
            f"URLsCopied={len(copied_results)}",
            f"URLsSkipped={len(skipped_results)}",
        ]
    )

    # Metrics (post-commit, dedicated aggregate event only). Emitted only when at
    # least one URL was actually copied; an all-skipped request records nothing.
    # URL_ADDED_TO_UTUB is deliberately NOT emitted — a copy is not a fresh create.
    if copied_results:
        record_event(
            EventName.URLS_COPIED_TO_UTUB,
            dimensions={
                "url_count_bucket": bucket_bulk_tag_url_count(len(copied_results)),
                "skipped_count_bucket": bucket_bulk_tag_url_count(len(skipped_results)),
                # This single-destination path always copies into exactly one
                # destination. The dim is required on the shared _DimUrlsCopiedToUtub
                # model (added for the multi-destination orchestrator); feed it here
                # so this still-live emit passes validation. This whole function +
                # emit is retired in Step 3.
                "destination_count_bucket": bucket_bulk_tag_url_count(1),
            },
        )

    return APIResponse(
        message=URL_SUCCESS.URLS_COPIED,
        data=CopyUrlsResponseSchema(
            copied=copied_results,
            skipped=[UrlCopySkippedSchema(**entry) for entry in skipped_results],
        ),
    ).to_response()
