import time

from flask import current_app
from flask_login import current_user

from backend import db
from backend.api_common.request_utils import is_current_utub_manager
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.app_logger import (
    critical_log,
    safe_add_log,
    safe_add_many_logs,
    safe_get_request_id,
    warning_log,
)
from backend.extensions.extension_utils import (
    safe_get_notif_sender,
    safe_get_url_validator,
)
from backend.extensions.metrics.writer import record_event
from backend.extensions.url_validation.url_validator import (
    AdaUrlParsingError,
    InvalidURLError,
    URLWithCredentialsError,
)
from backend.metrics.events import EventName
from backend.metrics.tag_batch import bucket_url_tag_count
from backend.models.urls import Urls
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.schemas.errors import (
    build_detail_error_response,
    build_url_conflict_error_response,
)
from backend.schemas.tags import UtubTagSchema
from backend.schemas.urls import UrlCreatedItemSchema, UrlCreatedResponseSchema
from backend.tags.services.create_url_tag import (
    apply_tags_core,
    build_url_at_tag_limit_response,
    get_tag_applied_counts,
)
from backend.urls.constants import URLErrorCodes, URLNormalizationResult, URLState
from backend.urls.data_models import NormalizedUrl, ValidatedUrl
from backend.urls.services.trashed_url_tags import count_lost_trashed_tags
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.url_strs import URL_FAILURE, URL_SUCCESS
from backend.utubs.guards import reject_if_utub_locked


def create_url_in_utub(
    url_string: str,
    url_title: str,
    current_utub: Utubs,
    tag_strings: list[str] | None = None,
) -> FlaskResponse:
    """
    Creates a new URL in a UTub.

    If the UTub already holds a trashed row for the URL, that row is revived
    (see `_revive_trashed_url_in_utub`) instead of a new row being inserted.

    Args:
        url_string (str): The URL string to add
        url_title (str): The title for this URL in the UTub
        current_utub (Utubs): The UTub object containing the UTub_Urls
        tag_strings (list[str]): Optional tags to apply to the URL on creation

    Returns:
        tuple[Response, int]:
        - Response: JSON response on create
        - int: HTTP status code 200 (Success)
    """
    if tag_strings is None:
        tag_strings = []
    utub_locked_error: FlaskResponse | None = reject_if_utub_locked(
        current_utub, error_code=URLErrorCodes.UTUB_IS_LOCKED
    )
    if utub_locked_error is not None:
        return utub_locked_error
    had_tracking: bool = safe_get_url_validator(current_app).contains_tracking_params(
        url_string
    )
    validated_new_url = validate_new_url_for_utub(url_string, current_utub.id)
    if (
        validated_new_url.url_state == URLState.INVALID_URL_STRING
        or validated_new_url.url is None
    ):
        return build_response_for_invalidated_url(validated_new_url.normalized_url)

    if validated_new_url.url_state == URLState.EXISTING_URL_TRASHED_IN_UTUB:
        assert validated_new_url.utub_url is not None
        return _revive_trashed_url_in_utub(
            current_utub=current_utub,
            trashed_utub_url=validated_new_url.utub_url,
            url_title=url_title,
            url_string=validated_new_url.url.url_string,
            tag_strings=tag_strings,
            had_tracking=had_tracking,
        )

    if validated_new_url.url_state == URLState.EXISTING_URL_IN_UTUB:
        return _build_url_already_in_utub_response(
            current_utub=current_utub,
            url_id=validated_new_url.url.id,
            url_string=validated_new_url.url.url_string,
            had_tracking=had_tracking,
        )

    url, url_state = validated_new_url.url, validated_new_url.url_state

    # Associate URL with given UTub
    return _associate_url_with_utub(
        current_utub=current_utub,
        url_id=url.id,
        url_title=url_title,
        url_string=url.url_string,
        url_state=url_state,
        tag_strings=tag_strings,
        had_tracking=had_tracking,
    )


def validate_new_url_for_utub(url_string: str | None, utub_id: int) -> ValidatedUrl:
    """
    Validates a URL to be ADA compliant, and ensures it is new for a UTub.

    Returns the URL object and its state in a ValidatedUrl object. When the URL already has
    a row in the UTub, the state is EXISTING_URL_IN_UTUB (live) or EXISTING_URL_TRASHED_IN_UTUB
    (soft-deleted), and that row is returned as `utub_url`.

    Args:
        url_string (str | None): The normalized URL string to look up or create.
        utub_id (int): The UTub ID to add the URL to

    Returns:
        tuple[Response, int] | ValidatedUrl: If the URL already exists in the UTub, returns:
        - Response: JSON response indicating the URL is already in the UTub
        - int: HTTP status code 400 on invalid URL
        If the URL is valid, returns the ValidatedUrl with the URL and it's existing or fresh state.

    """
    # Check for a valid and ADA compliant URL
    normalized_url = _normalize_and_validate_url(url_string)
    if normalized_url.status != URLNormalizationResult.VALID_URL:
        return ValidatedUrl(
            url_state=URLState.INVALID_URL_STRING, normalized_url=normalized_url
        )

    url, url_state = get_or_create_url(normalized_url.validated_url)

    # If the URL exists and is already in the UTub, return early
    if url_state == URLState.EXISTING_URL_IN_U4I:
        safe_add_log(f"URL already exists in U4I, URL.id={url.id}")
        existing_utub_url = check_url_already_in_utub(utub_id, url.id)

        if existing_utub_url is not None:
            return ValidatedUrl(
                url=url,
                url_state=(
                    URLState.EXISTING_URL_TRASHED_IN_UTUB
                    if existing_utub_url.is_trashed
                    else URLState.EXISTING_URL_IN_UTUB
                ),
                normalized_url=normalized_url,
                utub_url=existing_utub_url,
            )

    return ValidatedUrl(url=url, url_state=url_state, normalized_url=normalized_url)


def build_response_for_invalidated_url(normalized_url: NormalizedUrl) -> FlaskResponse:
    if normalized_url.status == URLNormalizationResult.INVALID_CREDENTIALS_URL:
        return handle_url_with_credentials_error(normalized_url)

    if normalized_url.status == URLNormalizationResult.INVALID_URL:
        return handle_invalid_url_error(normalized_url)

    return handle_unexpected_url_validation_error(normalized_url)


def get_or_create_url(url_string: str) -> tuple[Urls, URLState]:
    """
    Retrieve an existing URL from the database or create a new one if it doesn't exist.

    Checks if the normalized URL string already exists in the database. If found, returns
    its ID and EXISTING_URL state. Otherwise, creates a new URL entry, commits it to the
    database, and returns its ID with FRESH_URL state.

    Args:
        url_string (str): The normalized URL string to look up or create.

    Returns:
        tuple[Urls, URLState]: A tuple containing:
        - Urls: The URL (existing or newly created) model in the database
        - URLState: Either URLState.EXISTING_URL or URLState.FRESH_URL
    """
    already_created_url: Urls = Urls.query.filter(Urls.url_string == url_string).first()

    if already_created_url:
        return already_created_url, URLState.EXISTING_URL_IN_U4I

    new_url = Urls(
        normalized_url=url_string,
        current_user_id=current_user.id,
    )

    # Commit new URL to the database
    db.session.add(new_url)
    db.session.commit()
    safe_add_log(f"Added new URL, URL.id={new_url.id}")

    return new_url, URLState.FRESH_URL


def check_url_already_in_utub(utub_id: int, url_id: int) -> Utub_Urls | None:
    """
    Look up the URL-UTub association for a specific UTub.

    The lookup is deliberately unfiltered by trash state: the unique constraint
    `unique_url_per_utub` covers trashed rows too, so callers must see a trashed
    row to revive it (add) or reject it (edit) instead of colliding on insert.

    Args:
        utub_id (int): The ID of the UTub to check.
        url_id (int): The ID of the URL to check.

    Returns:
        (Utub_Urls | None): The existing row, live or trashed, or None when the
        URL is not associated with the UTub at all.
    """
    return Utub_Urls.query.filter(
        Utub_Urls.utub_id == utub_id, Utub_Urls.url_id == url_id
    ).first()


def _normalize_and_validate_url(url_string: str | None) -> NormalizedUrl:
    """
    Normalize and validate a URL string using the application's URL validator.

    Performs normalization to standardize the URL format, then validates it for correctness
    and security issues. Logs timing information for performance monitoring and handles
    various types of validation errors appropriately.

    Args:
        url_string (str | None): The URL string to normalize and validate.

    Returns:
        str | tuple[Response, int]: On success, returns the validated URL string.
        On failure, returns a tuple containing:
        - Response: JSON response with error details
        - int: HTTP status code 400
    """
    start = time.perf_counter()
    url_validator = safe_get_url_validator(current_app)
    input_url = "" if not url_string else url_string

    try:
        normalized_url = url_validator.normalize_url(url_string)

        normalized_time = (time.perf_counter() - start) * 1000

        validated_ada_url = url_validator.validate_url(normalized_url)

        validation_time = (time.perf_counter() - start) * 1000

    except URLWithCredentialsError as credentials_error:
        return NormalizedUrl(
            input_url_string=input_url,
            time_to_validate=(time.perf_counter() - start) * 1000,
            status=URLNormalizationResult.INVALID_CREDENTIALS_URL,
            exception=credentials_error,
        )

    except InvalidURLError as invalid_url_error:
        return NormalizedUrl(
            input_url_string=input_url,
            time_to_validate=(time.perf_counter() - start) * 1000,
            status=URLNormalizationResult.INVALID_URL,
            exception=invalid_url_error,
        )

    except (AdaUrlParsingError, Exception) as parse_error:
        return NormalizedUrl(
            input_url_string=input_url,
            time_to_validate=(time.perf_counter() - start) * 1000,
            status=URLNormalizationResult.UNKNOWN_FAILURE_URL,
            exception=parse_error,
        )

    total_time = (time.perf_counter() - start) * 1000
    safe_add_many_logs(
        [
            f"Finished checks for {url_string=}",
            f"Took {normalized_time:.3f} ms for normalization",
            f"Took {(validation_time - normalized_time):.3f} ms total for validation",
            f"Took {total_time:.3f} ms total",
        ]
    )
    return NormalizedUrl(
        input_url_string=input_url,
        time_to_validate=total_time,
        status=URLNormalizationResult.VALID_URL,
        validated_url=validated_ada_url,
    )


def handle_url_with_credentials_error(normalized_url: NormalizedUrl) -> FlaskResponse:
    """
    Handle the case where a URL containing credentials (username/password) is detected.

    Logs the security violation with timing information and returns an error response
    indicating that URLs with credentials are not allowed.

    Args:
        normalized_url (NormalizedUrl): DTO with information from URL normalization/validation.

    Returns:
        tuple[Response, int]: A tuple containing:
        - Response: JSON response with error message and details
        - int: HTTP status code 400
    """
    request_id = safe_get_request_id()
    warning_log(
        f"[{request_id}] URL with crendentials passed by User={current_user.id}\n"
        + f"[{request_id}] Took {normalized_url.time_to_validate:.3f} ms to fail validation\n"
        + f"[{request_id}] Exception={str(normalized_url.exception)}"
    )

    record_event(
        EventName.URL_CREATE_REJECTED,
        dimensions={"reason": "credentials_url"},
    )
    return build_detail_error_response(
        message=URL_FAILURE.URLS_WITH_CREDENTIALS_EXCEPTION,
        details=str(normalized_url.exception),
        error_code=URLErrorCodes.URL_WITH_CREDENTIALS_ERROR,
    )


def handle_invalid_url_error(normalized_url: NormalizedUrl) -> FlaskResponse:
    """
    Handle validation errors for malformed or invalid URLs.

    Logs the validation failure with timing information and returns an error response
    with details about why the URL failed validation.

    Args:
        normalized_url (NormalizedUrl): DTO with information from URL normalization/validation.

    Returns:
        tuple[Response, int]: A tuple containing:
        - Response: JSON response with error message and exception details
        - int: HTTP status code 400
    """
    request_id = safe_get_request_id()

    warning_log(
        f"[{request_id}] Unable to validate the URL given by User={current_user.id}\n"
        + f"[{request_id}] Took {normalized_url.time_to_validate:.3f} ms to fail validation\n"
        + f"[{request_id}] url_string={normalized_url.input_url_string}\n"
        + f"[{request_id}] Exception={str(normalized_url.exception)}"
    )

    record_event(
        EventName.URL_CREATE_REJECTED,
        dimensions={"reason": "invalid_url"},
    )
    return build_detail_error_response(
        message=URL_FAILURE.UNABLE_TO_VALIDATE_THIS_URL,
        details=str(normalized_url.exception),
        error_code=URLErrorCodes.INVALID_URL_ERROR,
    )


def handle_unexpected_url_validation_error(
    normalized_url: NormalizedUrl,
) -> FlaskResponse:
    """
    Handle unexpected exceptions that occur during URL validation.

    Logs critical error information, sends a notification about the unexpected failure,
    and returns an error response. This is for catching unanticipated validation errors
    that don't fall into known error categories.

    Args:
        normalized_url (NormalizedUrl): DTO with information from URL normalization/validation.

    Returns:
        tuple[Response, int]: A tuple containing:
        - Response: JSON response with error message and exception details
        - int: HTTP status code 400
    """
    request_id = safe_get_request_id()

    critical_log(
        f"[{request_id}] Unexpected exception validating the URL given by User={current_user.id}\n"
        + f"[{request_id}] Took {normalized_url.time_to_validate:.3f} ms to fail validation\n"
        + f"[{request_id}] url_string={normalized_url.input_url_string}\n"
        + f"[{request_id}] Exception={str(normalized_url.exception)}"
    )
    notification_sender = safe_get_notif_sender(current_app)
    notification_sender.send_notification(
        f"Unexpected exception validating {normalized_url.input_url_string} | Exception={str(normalized_url.exception)}"
    )

    record_event(
        EventName.URL_CREATE_REJECTED,
        dimensions={"reason": "unexpected_error"},
    )
    return build_detail_error_response(
        message=URL_FAILURE.UNEXPECTED_VALIDATION_EXCEPTION,
        details=str(normalized_url.exception),
        error_code=URLErrorCodes.UNEXPECTED_VALIDATION_ERROR,
    )


def _associate_url_with_utub(
    current_utub: Utubs,
    url_id: int,
    url_title: str,
    url_string: str,
    url_state: URLState,
    tag_strings: list[str] | None = None,
    had_tracking: bool = False,
) -> FlaskResponse:
    """
    Create an association between a URL and a UTub, adding the URL to the UTub,
    and atomically apply any requested tags.

    Creates a new Utub_Urls entry linking the URL to the UTub with the specified title,
    updates the UTub's last modified timestamp, applies the requested tags, and commits
    the URL row and its tags together so the addition is all-or-nothing.

    Args:
        current_utub (Utubs): The UTub object to associate the URL with.
        url_id (int): The database ID of the URL to add.
        url_title (str): The title to display for this URL in the UTub.
        url_string (str): The URL string for the success response.
        url_state (URLState): Whether this is a newly created or existing URL.
        tag_strings (list[str]): Optional tags to apply to the URL on creation.
        had_tracking (bool): Whether the raw input URL carried tracking query
            params that were stripped before storage. Recorded as the
            `stripped` dimension on the URL_TRACKING_PARAMS_STRIPPED event.

    Returns:
        tuple[Response, int]: A tuple containing:
        - Response: JSON response with success message and URL details
        - int: HTTP status code 200 (success) or 400 (applying the tags would
          exceed the per-URL tag limit)
    """
    if tag_strings is None:
        tag_strings = []
    url_utub_user_add = Utub_Urls(
        utub_id=current_utub.id,
        url_id=url_id,
        user_id=current_user.id,
        url_title=url_title,
    )

    # The flush assigns url_utub_user_add.id before tags are associated; the
    # explicit rollback guarantees that an invalid tag discards the URL row too,
    # so the URL and its tags commit together or not at all.
    try:
        db.session.add(url_utub_user_add)
        db.session.flush()
        current_utub.set_last_updated()

        applied: list[Utub_Tags] = []
        if tag_strings:
            result = apply_tags_core(tag_strings, current_utub, url_utub_user_add)
            if result.over_limit:
                # Capture the id before the rollback detaches the instance; the
                # response builder must not access ORM attributes post-rollback.
                url_utub_user_add_id = url_utub_user_add.id
                db.session.rollback()
                return build_url_at_tag_limit_response(url_utub_user_add_id)
            applied = result.to_apply

        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        warning_log(
            f"URL-with-tags create failed | UTub.id={current_utub.id} "
            f"| URL.id={url_id} | RequestedTagCount={len(tag_strings)} "
            f"| error_type={type(exc).__name__}"
        )
        raise

    record_event(
        EventName.URL_ADDED_TO_UTUB,
        dimensions={"tag_count_bucket": bucket_url_tag_count(len(applied))},
    )
    record_event(
        EventName.URL_TRACKING_PARAMS_STRIPPED,
        dimensions={"stripped": "true" if had_tracking else "false"},
    )
    for _utub_tag in applied:
        record_event(EventName.TAG_APPLIED)

    # Successfully added a URL, and associated it to a UTub
    safe_add_many_logs(
        ["Added URL to UTub", f"UTub.id={current_utub.id}", f"URL.id={url_id}"]
    )

    message = URL_SUCCESS.URL_ADDED
    if url_state == URLState.FRESH_URL:
        message = URL_SUCCESS.URL_CREATED_ADDED

    tag_counts = get_tag_applied_counts(
        current_utub.id, [utub_tag.id for utub_tag in applied]
    )
    applied_tags = [
        UtubTagSchema(
            id=utub_tag.id,
            tag_string=utub_tag.tag_string,
            tag_applied=tag_counts.get(utub_tag.id, 0),
        )
        for utub_tag in applied
    ]

    return APIResponse(
        message=message,
        data=UrlCreatedResponseSchema(
            utub_id=current_utub.id,
            added_by=current_user.id,
            url=UrlCreatedItemSchema(
                utub_url_id=url_utub_user_add.id,
                url_string=url_string,
                url_title=url_title,
                utub_url_tag_ids=url_utub_user_add.associated_tag_ids,
                added_at=url_utub_user_add.added_at,
            ),
            applied_tags=applied_tags,
        ),
    ).to_response()


def _build_url_already_in_utub_response(
    *, current_utub: Utubs, url_id: int, url_string: str, had_tracking: bool
) -> FlaskResponse:
    """Log, record and build the 409 for a URL that is already live in the UTub."""
    warning_log(
        f"User={current_user.id} tried adding URL.id={url_id} but already exists in UTub.id={current_utub.id}"
    )
    record_event(
        EventName.URL_CREATE_REJECTED,
        dimensions={"reason": "url_already_in_utub"},
    )
    message = (
        URL_FAILURE.URL_IN_UTUB_TRACKING_PARAMS_STRIPPED
        if had_tracking
        else URL_FAILURE.URL_IN_UTUB
    )
    return build_url_conflict_error_response(
        message=message,
        url_string=url_string,
        error_code=URLErrorCodes.URL_ALREADY_IN_UTUB_ERROR,
    )


def make_locked_trashed_url_live(
    *,
    locked_utub_url: Utub_Urls,
    adder_id: int,
    url_title: str,
    keep_tags: bool,
) -> None:
    """
    Make a trashed, row-locked Utub_Urls row live again under a new adder.

    Clears the trash flags and the tag snapshot, sets the adder, title and fresh
    `added_at`/`last_accessed`, and flushes. When `keep_tags` is False the row's
    `Utub_Url_Tags` rows are deleted so it comes back clean. Does not commit or roll
    back; the caller owns the transaction and must hold the row lock.

    Args:
        locked_utub_url (Utub_Urls): The trashed row, locked `FOR UPDATE`.
        adder_id (int): The user to attribute the revived row to.
        url_title (str): The title for the revived row.
        keep_tags (bool): Whether the tags it had when trashed stay attached.
    """
    if not keep_tags:
        Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_url_id == locked_utub_url.id
        ).delete(synchronize_session=False)
        db.session.expire(locked_utub_url, ["url_tags"])

    now = utc_now()
    locked_utub_url.deleted_at = None
    locked_utub_url.deleted_by = None
    locked_utub_url.trashed_tag_ids = None
    locked_utub_url.user_id = adder_id
    locked_utub_url.url_title = url_title
    locked_utub_url.added_at = now
    locked_utub_url.last_accessed = now
    db.session.flush()


def _revive_trashed_url_in_utub(
    *,
    current_utub: Utubs,
    trashed_utub_url: Utub_Urls,
    url_title: str,
    url_string: str,
    tag_strings: list[str],
    had_tracking: bool,
) -> FlaskResponse:
    """
    Revive this UTub's trashed row for a URL instead of inserting a duplicate.

    The unique constraint `unique_url_per_utub` covers trashed rows, so re-adding a
    trashed URL must reuse its row. The row is made live again under the re-adding
    user with a fresh title and timestamps. The tags the URL had when it was
    trashed are kept only when the re-adder is the original adder or a UTub
    manager; any other member gets a clean row. Tags deleted from the UTub while
    the row was trashed are reported as `lostTagCount`. Requested `tag_strings`
    are applied on top of the surviving tags, all in one transaction.

    Args:
        current_utub (Utubs): The UTub containing the trashed row.
        trashed_utub_url (Utub_Urls): The trashed row to revive.
        url_title (str): The title for the revived URL.
        url_string (str): The URL string for the success response.
        tag_strings (list[str]): Optional tags to apply on top of the surviving ones.
        had_tracking (bool): Whether the raw input URL carried tracking params.

    Returns:
        FlaskResponse: 200 with `revivedFromTrash` set, or 400 when applying the
        requested tags would exceed the per-URL tag limit (the row stays trashed).
    """
    utub_url_id: int = trashed_utub_url.id
    url_id: int = trashed_utub_url.url_id

    # Lock the row and re-check it is still trashed, so a concurrent revive or
    # restore cannot be silently overwritten by this one.
    locked_utub_url: Utub_Urls | None = (
        Utub_Urls.query.filter(Utub_Urls.id == utub_url_id)
        .with_for_update()
        .populate_existing()
        .first()
    )
    if locked_utub_url is None or not locked_utub_url.is_trashed:
        db.session.rollback()
        return _build_url_already_in_utub_response(
            current_utub=current_utub,
            url_id=url_id,
            url_string=url_string,
            had_tracking=had_tracking,
        )

    can_keep_tags: bool = (
        locked_utub_url.user_id == current_user.id or is_current_utub_manager()
    )

    # Read everything that depends on the trashed state before any write.
    lost_tag_count: int = (
        count_lost_trashed_tags(locked_utub_url) if can_keep_tags else 0
    )

    to_apply: list[Utub_Tags] = []
    try:
        make_locked_trashed_url_live(
            locked_utub_url=locked_utub_url,
            adder_id=current_user.id,
            url_title=url_title,
            keep_tags=can_keep_tags,
        )
        current_utub.set_last_updated()

        if tag_strings:
            result = apply_tags_core(tag_strings, current_utub, locked_utub_url)
            if result.over_limit:
                db.session.rollback()
                return build_url_at_tag_limit_response(utub_url_id)
            to_apply = result.to_apply

        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        warning_log(
            f"URL revive failed | UTub.id={current_utub.id} "
            f"| UTubURL.id={utub_url_id} | RequestedTagCount={len(tag_strings)} "
            f"| error_type={type(exc).__name__}"
        )
        raise

    record_event(
        EventName.URL_ADDED_TO_UTUB,
        dimensions={"tag_count_bucket": bucket_url_tag_count(len(to_apply))},
    )
    record_event(
        EventName.URL_TRACKING_PARAMS_STRIPPED,
        dimensions={"stripped": "true" if had_tracking else "false"},
    )
    for _utub_tag in to_apply:
        record_event(EventName.TAG_APPLIED)

    safe_add_many_logs(
        [
            "Revived trashed URL in UTub",
            f"UTub.id={current_utub.id}",
            f"UTubURL.id={utub_url_id}",
        ]
    )

    revived_tag_ids: list[int] = locked_utub_url.associated_tag_ids
    response_tags: list[Utub_Tags] = (
        Utub_Tags.query.filter(Utub_Tags.id.in_(revived_tag_ids))
        .order_by(Utub_Tags.id)
        .all()
        if revived_tag_ids
        else []
    )

    tag_counts = get_tag_applied_counts(
        current_utub.id, [utub_tag.id for utub_tag in response_tags]
    )
    applied_tags = [
        UtubTagSchema(
            id=utub_tag.id,
            tag_string=utub_tag.tag_string,
            tag_applied=tag_counts.get(utub_tag.id, 0),
        )
        for utub_tag in response_tags
    ]

    return APIResponse(
        message=URL_SUCCESS.URL_ADDED,
        data=UrlCreatedResponseSchema(
            utub_id=current_utub.id,
            added_by=current_user.id,
            url=UrlCreatedItemSchema(
                utub_url_id=utub_url_id,
                url_string=url_string,
                url_title=url_title,
                utub_url_tag_ids=locked_utub_url.associated_tag_ids,
                added_at=locked_utub_url.added_at,
            ),
            applied_tags=applied_tags,
            revived_from_trash=True,
            lost_tag_count=lost_tag_count,
        ),
    ).to_response()
