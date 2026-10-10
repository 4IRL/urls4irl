from datetime import datetime

from flask import abort, current_app
from flask_login import current_user

from backend import db
from backend.api_common.request_utils import is_current_utub_manager
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.app_logger import safe_add_many_logs, warning_log
from backend.extensions.extension_utils import safe_get_url_validator
from backend.extensions.metrics.writer import record_event
from backend.metrics.events import EventName
from backend.models.urls import Urls
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.schemas.errors import (
    build_message_error_response,
    build_url_conflict_error_response,
)
from backend.schemas.tags import UtubTagSchema
from backend.schemas.urls import (
    UrlTitleUpdatedResponseSchema,
    UrlUpdatedResponseSchema,
    UtubUrlDetailSchema,
)
from backend.tags.services.create_url_tag import (
    apply_tags_core,
    build_url_at_tag_limit_response,
    get_tag_applied_counts,
)
from backend.urls.constants import URLErrorCodes, URLState
from backend.urls.services.create_urls import (
    build_response_for_invalidated_url,
    validate_new_url_for_utub,
)
from backend.urls.services.delete_urls import (
    recompute_tag_counts_after_delete,
    trash_live_utub_url,
)
from backend.urls.services.trashed_url_tags import count_lost_trashed_tags
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import MODELS
from backend.utils.strings.url_strs import URL_FAILURE, URL_NO_CHANGE, URL_SUCCESS
from backend.utubs.guards import reject_if_utub_locked


def update_url_in_utub(
    url_string: str, current_utub: Utubs, current_utub_url: Utub_Urls
) -> FlaskResponse:
    """
    Updates the given Utub_Urls in the UTub.

    Args:
        url_string (str): The new URL string to update to
        current_utub (Utubs): The UTub object containing the UTub_Urls
        current_utub_url (Utub_Urls): The UTub_Urls object to update.

    Returns:
        tuple[Response, int]:
        - Response: JSON response on update
        - int: HTTP status code 200 (Success)
    """
    utub_locked_error: FlaskResponse | None = reject_if_utub_locked(
        current_utub, error_code=URLErrorCodes.UTUB_IS_LOCKED
    )
    if utub_locked_error is not None:
        return utub_locked_error

    url_to_change_to: str = url_string.strip()

    had_tracking: bool = safe_get_url_validator(current_app).contains_tracking_params(
        url_to_change_to
    )

    # Check for empty URL string to update to
    is_empty_url = _check_for_empty_url_string_on_update(
        url_to_change_to, current_utub_url.id
    )

    if is_empty_url:
        return build_message_error_response(
            message=URL_FAILURE.EMPTY_URL,
            error_code=URLErrorCodes.EMPTY_URL,
        )

    # Validate (and strip tracking params from) the new URL before any
    # equivalence comparison, so the stored stripped form is compared against
    # the stripped candidate rather than the raw input.
    validated_new_url = validate_new_url_for_utub(url_to_change_to, current_utub.id)
    if (
        validated_new_url.url_state == URLState.INVALID_URL_STRING
        or validated_new_url.url is None
    ):
        return build_response_for_invalidated_url(validated_new_url.normalized_url)

    validated_url_string: str = validated_new_url.normalized_url.validated_url

    # Check for updating the URL to the same (stripped) URL
    is_equivalent_url = _check_for_equivalent_url_on_update(
        validated_url_string, current_utub_url
    )

    if is_equivalent_url:
        return APIResponse(
            status=STD_JSON.NO_CHANGE,
            message=URL_NO_CHANGE.URL_NOT_MODIFIED,
            data=UrlTitleUpdatedResponseSchema(
                url=UtubUrlDetailSchema.from_orm_url(current_utub_url)
            ),
        ).to_response()

    if validated_new_url.url_state == URLState.EXISTING_URL_TRASHED_IN_UTUB:
        assert validated_new_url.utub_url is not None
        return _revive_trashed_url_on_edit(
            current_utub=current_utub,
            edited_utub_url=current_utub_url,
            trashed_utub_url=validated_new_url.utub_url,
            had_tracking=had_tracking,
        )

    if validated_new_url.url_state == URLState.EXISTING_URL_IN_UTUB:
        return _build_live_url_conflict_response(
            current_utub=current_utub,
            url=validated_new_url.url,
            had_tracking=had_tracking,
        )

    return _associate_updated_url_with_utub(
        url=validated_new_url.url,
        current_utub=current_utub,
        current_utub_url=current_utub_url,
        had_tracking=had_tracking,
    )


def _check_for_empty_url_string_on_update(
    url_string: str,
    utub_url_id: int,
) -> bool:
    """
    Checks if the provided URL to update to is an empty string.

    Args:
        url_string (str): The URL string to update to.
        utub_url_id (int): The ID of the UTub URL

    Returns:
        (bool): True if url string is empty
    """
    is_empty_url = not url_string
    if is_empty_url:
        warning_log(
            f"User={current_user.id} tried changing UTubURL.id={utub_url_id} to a URL with only spaces"
        )
    return is_empty_url


def _check_for_equivalent_url_on_update(
    validated_url_string: str, current_utub_url: Utub_Urls
) -> bool:
    """
    Checks if the provided URL to update to is equivalent to the current URL.

    Args:
        validated_url_string (str): The stripped, validated URL string to compare against the stored URL.
        current_utub_url (Utub_Urls): The UTub URL whose stored URL string is compared against.

    Returns:
        (bool): True if url string is equivalent to given URL
    """

    is_equivalent_url = (
        validated_url_string == current_utub_url.standalone_url.url_string
    )

    if is_equivalent_url:
        warning_log(
            f"User={current_user.id} tried changing UTubURL.id={current_utub_url.id} to the same URL"
        )
    return is_equivalent_url


def _build_live_url_conflict_response(
    *, current_utub: Utubs, url: Urls, had_tracking: bool
) -> FlaskResponse:
    """Log and build the 409 for an edit to a URL that is already live in the UTub."""
    warning_log(
        f"User={current_user.id} tried editing to URL.id={url.id} but already exists in UTub.id={current_utub.id}"
    )
    message = (
        URL_FAILURE.URL_IN_UTUB_TRACKING_PARAMS_STRIPPED
        if had_tracking
        else URL_FAILURE.URL_IN_UTUB
    )
    return build_url_conflict_error_response(
        message=message,
        url_string=url.url_string,
        error_code=URLErrorCodes.URL_ALREADY_IN_UTUB_ERROR,
    )


def _revive_trashed_url_on_edit(
    *,
    current_utub: Utubs,
    edited_utub_url: Utub_Urls,
    trashed_utub_url: Utub_Urls,
    had_tracking: bool,
) -> FlaskResponse:
    """
    Edit a card's link to a URL that is trashed in the same UTub: revive the trashed
    row and trash the edited row, in one transaction.

    The unique constraint `unique_url_per_utub` covers trashed rows, so the trashed
    row (which owns the slot for the new link) is revived in place and the edited row
    is soft-deleted exactly like a normal delete (so it stays recoverable). The
    revived row takes the edited row's identity (title, adder, `added_at`) so the card
    the user edited appears to simply change link. The trashed row's tags are kept
    only when the editor is its original adder or a UTub manager (the same rule as
    add-revive); the edited row's tags are then unioned on top. Tags deleted from the
    UTub while the row was trashed are reported as `lostTagCount`. If the union
    exceeds the per-URL tag limit, nothing changes and the at-tag-limit 400 is
    returned.

    Both rows are locked ordered by id (no deadlock between concurrent edits). If the
    trashed row was concurrently revived the live-conflict 409 is returned; if the
    edited row was concurrently trashed the request aborts with 404.

    Args:
        current_utub (Utubs): The UTub containing both rows.
        edited_utub_url (Utub_Urls): The live row the user is editing.
        trashed_utub_url (Utub_Urls): The trashed row holding the new link.
        had_tracking (bool): Whether the raw input URL carried tracking params.

    Returns:
        FlaskResponse: 200 with `revivedFromTrash` set, 400 on tag limit, 409 when the
        trashed row is no longer trashed.
    """
    edited_utub_url_id: int = edited_utub_url.id
    trashed_utub_url_id: int = trashed_utub_url.id
    revived_url: Urls = trashed_utub_url.standalone_url

    locked_rows_by_id: dict[int, Utub_Urls] = {
        locked_row.id: locked_row
        for locked_row in Utub_Urls.query.filter(
            Utub_Urls.id.in_([edited_utub_url_id, trashed_utub_url_id])
        )
        .order_by(Utub_Urls.id)
        .with_for_update()
        .populate_existing()
        .all()
    }
    locked_edited = locked_rows_by_id.get(edited_utub_url_id)
    locked_trashed = locked_rows_by_id.get(trashed_utub_url_id)

    if locked_edited is None or locked_edited.is_trashed:
        db.session.rollback()
        abort(404)

    if locked_trashed is None or not locked_trashed.is_trashed:
        db.session.rollback()
        return _build_live_url_conflict_response(
            current_utub=current_utub, url=revived_url, had_tracking=had_tracking
        )

    can_keep_tags: bool = (
        locked_trashed.user_id == current_user.id or is_current_utub_manager()
    )

    # Read everything that depends on the pre-write state before any write.
    lost_tag_count: int = (
        count_lost_trashed_tags(locked_trashed) if can_keep_tags else 0
    )
    edited_tag_ids: set[int] = set(locked_edited.associated_tag_ids)
    edited_tag_strings: list[str] = [
        str(tag[MODELS.TAG_STRING]) for tag in locked_edited.associated_tags
    ]
    edited_title: str = locked_edited.url_title
    edited_adder_id: int = locked_edited.user_id
    edited_added_at: datetime = locked_edited.added_at

    # Kept out of the try below so the 404 abort needs no HTTPException passthrough.
    if not trash_live_utub_url(
        utub_id=current_utub.id,
        utub_url_id=edited_utub_url_id,
        snapshot_tag_ids=edited_tag_ids,
    ):
        db.session.rollback()
        abort(404)

    to_apply: list[Utub_Tags] = []
    try:
        if not can_keep_tags:
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_url_id == trashed_utub_url_id
            ).delete(synchronize_session=False)
            db.session.expire(locked_trashed, ["url_tags"])

        locked_trashed.deleted_at = None
        locked_trashed.deleted_by = None
        locked_trashed.trashed_tag_ids = None
        locked_trashed.user_id = edited_adder_id
        locked_trashed.url_title = edited_title
        locked_trashed.added_at = edited_added_at
        locked_trashed.last_accessed = utc_now()
        db.session.flush()
        current_utub.set_last_updated()

        if edited_tag_strings:
            result = apply_tags_core(edited_tag_strings, current_utub, locked_trashed)
            if result.over_limit:
                db.session.rollback()
                return build_url_at_tag_limit_response(trashed_utub_url_id)
            to_apply = result.to_apply

        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        warning_log(
            f"URL revive-on-edit failed | UTub.id={current_utub.id} "
            f"| EditedUTubURL.id={edited_utub_url_id} | RevivedUTubURL.id={trashed_utub_url_id} "
            f"| error_type={type(exc).__name__}"
        )
        raise

    record_event(EventName.URL_STRING_UPDATED)
    record_event(
        EventName.URL_TRACKING_PARAMS_STRIPPED,
        dimensions={"stripped": "true" if had_tracking else "false"},
    )
    for _utub_tag in to_apply:
        record_event(EventName.TAG_APPLIED)

    safe_add_many_logs(
        [
            "Revived trashed URL in UTub on edit",
            f"UTub.id={current_utub.id}",
            f"EditedUTubURL.id={edited_utub_url_id}",
            f"RevivedUTubURL.id={trashed_utub_url_id}",
        ]
    )

    revived_tag_ids: list[int] = locked_trashed.associated_tag_ids
    revived_tags: list[Utub_Tags] = (
        Utub_Tags.query.filter(Utub_Tags.id.in_(revived_tag_ids))
        .order_by(Utub_Tags.id)
        .all()
        if revived_tag_ids
        else []
    )
    revived_tag_counts = get_tag_applied_counts(current_utub.id, revived_tag_ids)
    applied_tags = [
        UtubTagSchema(
            id=utub_tag.id,
            tag_string=utub_tag.tag_string,
            tag_applied=revived_tag_counts.get(utub_tag.id, 0),
        )
        for utub_tag in revived_tags
    ]

    return APIResponse(
        message=URL_SUCCESS.URL_MODIFIED,
        data=UrlUpdatedResponseSchema(
            utub_id=current_utub.id,
            utub_name=current_utub.name,
            url=UtubUrlDetailSchema.from_orm_url(locked_trashed),
            revived_from_trash=True,
            lost_tag_count=lost_tag_count,
            replaced_utub_url_id=edited_utub_url_id,
            applied_tags=applied_tags,
            tag_counts_modified=recompute_tag_counts_after_delete(
                utub_id=current_utub.id, affected_utub_tag_ids=edited_tag_ids
            ),
        ),
    ).to_response()


def _associate_updated_url_with_utub(
    url: Urls,
    current_utub: Utubs,
    current_utub_url: Utub_Urls,
    had_tracking: bool = False,
) -> FlaskResponse:
    """
    Associates the updated UTub_Url with the UTub.

    Args:
        url (Urls): The URL being updated
        current_utub (Utubs): The UTub object containing the UTub_Urls
        current_utub_url (Utub_Urls): The UTub_Urls object to update the title for.
        had_tracking (bool): Whether the raw input URL carried tracking query
            params that were stripped before storage. Recorded as the
            `stripped` dimension on the URL_TRACKING_PARAMS_STRIPPED event.

    Returns:
        tuple[Response, int]:
        - Response: JSON response on update
        - int: HTTP status code 200 (Success)
    """
    # Now set the URL ID for the old URL to the new URL
    current_utub_url.url_id = url.id
    current_utub_url.standalone_url = url

    current_utub.set_last_updated()
    db.session.commit()

    record_event(EventName.URL_STRING_UPDATED)
    record_event(
        EventName.URL_TRACKING_PARAMS_STRIPPED,
        dimensions={"stripped": "true" if had_tracking else "false"},
    )

    safe_add_many_logs(
        ["Added URL to UTub", f"UTub.id={current_utub.id}", f"URL.id={url.id}"]
    )

    return APIResponse(
        message=URL_SUCCESS.URL_MODIFIED,
        data=UrlUpdatedResponseSchema(
            utub_id=current_utub.id,
            utub_name=current_utub.name,
            url=UtubUrlDetailSchema.from_orm_url(current_utub_url),
        ),
    ).to_response()
