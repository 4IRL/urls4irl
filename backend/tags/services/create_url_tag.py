from dataclasses import dataclass

from flask_login import current_user
from sqlalchemy import func

from backend import db
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.app_logger import (
    safe_add_log,
    safe_add_many_logs,
    warning_log,
)
from backend.extensions.metrics.writer import record_event
from backend.metrics.events import EventName
from backend.metrics.tag_batch import bucket_tags_batch_size
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.schemas.errors import build_message_error_response
from backend.schemas.tags import (
    UrlTagModifiedResponseSchema,
    UrlTagsModifiedResponseSchema,
    UtubTagOnAddDeleteSchema,
    UtubTagSchema,
)
from backend.tags.constants import URLTagErrorCodes
from backend.utils.constants import TAG_CONSTANTS
from backend.utils.strings.tag_strs import TAGS_FAILURE, TAGS_SUCCESS
from backend.utubs.guards import reject_if_utub_locked


@dataclass
class TagApplyResult:
    """Outcome of a non-committing tag-apply core run.

    Cross-module data model shared between the batch-tag wrapper and the
    create-URL service. `over_limit` signals that applying the requested tags
    would exceed the per-URL tag limit (no rows were staged); `to_apply` holds
    the freshly-staged tags that callers should treat as newly applied.
    """

    over_limit: bool
    to_apply: list[Utub_Tags]


def add_tag_to_url_if_valid(
    tag_string: str, utub: Utubs, utub_url: Utub_Urls
) -> FlaskResponse:
    """
    Adds a tag to a URL, but only if the URL does not already have the maximum number of tags, and if the URL does not have the tag already on it.

    Args:
        tag_string (str): The tag string to add to the URL
        utub (Utubs): The UTub containing the URL and tag to add
        utub_url (Utub_Urls): The URL having a tag being added to

    Returns:
        tuple[Response, int]:
        - Response: JSON response on with success or error details.
        - int: HTTP status code
            200 (success)
            400 (at tag limit)
            400 (tag already on URL)
    """
    utub_locked_error: FlaskResponse | None = reject_if_utub_locked(
        utub, error_code=URLTagErrorCodes.UTUB_IS_LOCKED
    )
    if utub_locked_error is not None:
        return utub_locked_error
    tag_to_add = tag_string.strip()

    if _url_is_at_url_tag_limit(utub, utub_url):
        return build_url_at_tag_limit_response(utub_url.id)

    utub_tag = _get_or_create_utub_tag(tag_to_add, utub)

    if _tag_is_already_on_url(utub_tag, utub_url):
        return _build_tag_already_on_url_response(utub_url, utub_tag)

    utub_url_tag = _add_url_tag(utub_url, utub_tag)

    # Count instances of particular tag in UTub that is to be deleted
    updated_tag_id_count = get_count_of_url_tag_in_utub(utub_tag)

    utub.set_last_updated()
    db.session.commit()

    # Successfully added tag to URL on UTub
    safe_add_many_logs(
        [
            "Added new UTubURLTag",
            f"UTub.id={utub.id}",
            f"UTubURL.id={utub_url.id}",
            f"UTubTag.id={utub_tag.id}",
            f"UTubTag.tag_string={utub_tag.tag_string}",
            f"UTubURLTag.id={utub_url_tag.id}",
        ]
    )

    record_event(EventName.TAG_APPLIED)

    return APIResponse(
        message=TAGS_SUCCESS.TAG_ADDED_TO_URL,
        data=UrlTagModifiedResponseSchema(
            utub_url_tag_ids=utub_url.associated_tag_ids,
            utub_tag=UtubTagOnAddDeleteSchema.from_orm_tag(utub_tag),
            tag_counts_modified=updated_tag_id_count,
        ),
    ).to_response()


def apply_tags_core(
    tag_strings: list[str], utub: Utubs, utub_url: Utub_Urls
) -> TagApplyResult:
    """
    Non-committing core of the tag-apply flow, shared by the batch-tag wrapper
    and the create-URL service. Performs service-side exact-string de-dup, a
    read-only limit pre-check, and flush-only vocabulary creation + association
    writes — but never commits, rolls back, bumps `set_last_updated()`, emits a
    metric, or builds a FlaskResponse. Each caller owns its own commit,
    rollback, last-updated bump, and response.

    Args:
        tag_strings (list[str]): The tag strings to apply to the URL
        utub (Utubs): The UTub containing the URL and tags
        utub_url (Utub_Urls): The URL having tags applied to it

    Returns:
        TagApplyResult:
        - over_limit (bool): True if applying the net-new tags would exceed the
          per-URL tag limit. When True, no rows were staged.
        - to_apply (list[Utub_Tags]): The freshly-staged tags the caller should
          treat as newly applied (empty when every requested tag was already on
          the URL).
    """
    # Service-side de-dup (exact string / case-sensitive), preserving first-seen
    # order so the service can be called directly in tests without routing
    # through the schema. Exact-string semantics match the DB query below.
    seen: set[str] = set()
    deduped_strings = [
        tag_string
        for tag_string in tag_strings
        if not (tag_string in seen or seen.add(tag_string))
    ]

    # Pass 1 — read-only limit pre-check. No DB writes occur here, so an
    # over-limit signal guarantees zero vocabulary (Utub_Tags) and zero
    # association (Utub_Url_Tags) rows are written.
    already_present_ids = set(utub_url.associated_tag_ids)
    existing_vocab_ids_by_string: dict[str, int] = {
        tag.tag_string: tag.id
        for tag in Utub_Tags.query.filter(Utub_Tags.utub_id == utub.id).all()
    }
    net_new_count = 0
    for tag_string in deduped_strings:
        stripped = tag_string.strip()
        existing_tag_id = existing_vocab_ids_by_string.get(stripped)
        if existing_tag_id is None or existing_tag_id not in already_present_ids:
            net_new_count += 1

    if len(already_present_ids) + net_new_count > TAG_CONSTANTS.MAX_URL_TAGS:
        return TagApplyResult(over_limit=True, to_apply=[])

    # Pass 2 — vocabulary creation (flush-only) + association writes. The core
    # does not commit; the caller flushes these writes into its own single final
    # commit so the batch (and, in the create-URL flow, the URL row too) is
    # all-or-nothing.
    staged_tags: list[Utub_Tags] = []
    for tag_string in deduped_strings:
        tag_to_add = tag_string.strip()
        utub_tag: Utub_Tags = Utub_Tags.query.filter(
            Utub_Tags.utub_id == utub.id, Utub_Tags.tag_string == tag_to_add
        ).first()
        if not utub_tag:
            utub_tag = Utub_Tags(
                utub_id=utub.id, tag_string=tag_to_add, created_by=current_user.id
            )
            db.session.add(utub_tag)
            # flush assigns a DB-generated id without committing, keeping all
            # Pass 2 writes inside the caller's single final commit.
            db.session.flush()
        staged_tags.append(utub_tag)

    to_apply = [tag for tag in staged_tags if tag.id not in already_present_ids]

    for utub_tag in to_apply:
        _add_url_tag(utub_url, utub_tag)

    return TagApplyResult(over_limit=False, to_apply=to_apply)


def add_batch_tags_to_existing_url(
    tag_strings: list[str], utub: Utubs, utub_url: Utub_Urls
) -> FlaskResponse:
    """
    Applies a batch of tags to a URL atomically — either every net-new tag is
    applied or none are. Tags already on the URL (or duplicated within the
    payload) are silently de-duplicated and skipped. If applying the net-new
    tags would push the URL past the per-URL tag limit, the whole batch is
    rejected and zero rows are written.

    Thin committing wrapper around `apply_tags_core`: the core stages the
    flush-only writes; this wrapper owns the single final commit, the explicit
    rollback-on-exception guard, and its own `set_last_updated()` bump.

    Args:
        tag_strings (list[str]): The tag strings to apply to the URL
        utub (Utubs): The UTub containing the URL and tags
        utub_url (Utub_Urls): The URL having tags applied to it

    Returns:
        tuple[Response, int]:
        - Response: JSON response with success or error details.
        - int: HTTP status code
            200 (success — including the all-already-applied no-op case)
            400 (applying the batch would exceed the per-URL tag limit)
    """
    utub_locked_error: FlaskResponse | None = reject_if_utub_locked(
        utub, error_code=URLTagErrorCodes.UTUB_IS_LOCKED
    )
    if utub_locked_error is not None:
        return utub_locked_error
    # The explicit rollback guarantees that a mid-batch exception discards both
    # the flushed vocabulary rows and any association writes, rather than relying
    # on the request-teardown rollback (which the test harness's SAVEPOINT does
    # not trigger on a propagated exception).
    try:
        result = apply_tags_core(tag_strings, utub, utub_url)
        if result.over_limit:
            return build_url_at_tag_limit_response(utub_url.id)

        if result.to_apply:
            # Only bump the UTub modification time when at least one new tag is
            # actually applied; an all-already-applied batch is a no-op. Each
            # caller owns its own last-updated bump.
            utub.set_last_updated()
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        warning_log(
            f"Batch tag-apply failed | UTub.id={utub.id} | UTubURL.id={utub_url.id} "
            f"| RequestedCount={len(tag_strings)} | error_type={type(exc).__name__}"
        )
        raise

    to_apply = result.to_apply

    if not to_apply:
        # Every requested tag was already on the URL — no rows written, no
        # batch event emitted, and no "applied" log line.
        return APIResponse(
            message=TAGS_SUCCESS.TAGS_ADDED_TO_URL,
            data=UrlTagsModifiedResponseSchema(
                utub_url_tag_ids=utub_url.associated_tag_ids,
                applied_tags=[],
            ),
        ).to_response()

    safe_add_many_logs(
        [
            "Applied batch of UTubURLTags",
            f"UTub.id={utub.id}",
            f"UTubURL.id={utub_url.id}",
            f"AppliedCount={len(to_apply)}",
        ]
    )

    for _utub_tag in to_apply:
        record_event(EventName.TAG_APPLIED)

    record_event(
        EventName.TAGS_APPLIED_BATCH,
        dimensions={"batch_size_bucket": bucket_tags_batch_size(len(to_apply))},
    )

    tag_counts = get_tag_applied_counts(utub.id, [tag.id for tag in to_apply])

    applied_tags = [
        UtubTagSchema(
            id=tag.id,
            tag_string=tag.tag_string,
            tag_applied=tag_counts.get(tag.id, 0),
        )
        for tag in to_apply
    ]

    return APIResponse(
        message=TAGS_SUCCESS.TAGS_ADDED_TO_URL,
        data=UrlTagsModifiedResponseSchema(
            utub_url_tag_ids=utub_url.associated_tag_ids,
            applied_tags=applied_tags,
        ),
    ).to_response()


def _url_is_at_url_tag_limit(utub: Utubs, utub_url: Utub_Urls) -> bool:
    """
    Checks if the given UTub URL is already at the limit of available tags.

    Args:
        utub (Utubs): The UTub of the URL with tags on it to check
        utub_url (Utub_Urls): The URL with the tag being added

    Returns:
        (bool): True if the URL is at/above the tag limit
    """
    tags_already_on_this_url: list[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
        Utub_Url_Tags.utub_id == utub.id, Utub_Url_Tags.utub_url_id == utub_url.id
    ).all()

    return len(tags_already_on_this_url) >= TAG_CONSTANTS.MAX_URL_TAGS


def build_url_at_tag_limit_response(utub_url_id: int) -> FlaskResponse:
    """
        Builds JSON response for when a URL is at the tag limit

        Args:
            utub_url_id (int): The id of the URL at the tag limit. Accepts a plain
                int (not the ORM object) so callers can pass an id captured before
                a rollback, avoiding detached-instance attribute access.

    Returns:
            tuple[Response, int]:
            - Response: JSON response on error.
            - int: HTTP status code 400
    """
    warning_log(
        f"User={current_user.id} tried adding tag to UTubURL.id={utub_url_id} but tag limited"
    )
    return build_message_error_response(
        message=TAGS_FAILURE.MAX_URL_TAGS_REACHED.format(
            max_tags=TAG_CONSTANTS.MAX_URL_TAGS
        )
    )


def _get_or_create_utub_tag(tag: str, utub: Utubs) -> Utub_Tags:
    """
    Gets the UTub Tag with the given string, or builds it if it doesn't exist.

    Args:
        tag (str): The tag string to add or get
        utub (Utubs): The UTub containing the tag

    Returns:
        (Utub_Tags): The tag object in the UTub
    """
    utub_tag: Utub_Tags = Utub_Tags.query.filter(
        Utub_Tags.utub_id == utub.id, Utub_Tags.tag_string == tag
    ).first()

    if not utub_tag:
        # Create tag, then associate with this UTub and URL
        utub_tag = Utub_Tags(
            utub_id=utub.id, tag_string=tag, created_by=current_user.id
        )
        db.session.add(utub_tag)
        db.session.commit()

        safe_add_log(f"Added new UTubTag with UTubTag.id={utub_tag.id}")

    return utub_tag


def _tag_is_already_on_url(utub_tag: Utub_Tags, utub_url: Utub_Urls) -> bool:
    """
    Checks if the given UTub Tag is already on the given UTub URL.

    Args:
        utub_tag (Utub_Tags): The UTub tag that may or may not be on the UTub URL
        utub_url (Utub_Urls): The UTub URL that may or may not contain the UTub tag

    Returns:
        (bool): True if the UTub Tag is already associated with the UTub URL
    """
    return utub_tag.id in utub_url.associated_tag_ids


def _build_tag_already_on_url_response(
    utub_url: Utub_Urls, utub_tag: Utub_Tags
) -> FlaskResponse:
    """
    Builds JSON response for when a UTub URL already contains a given tag.

    Args:
        utub_url (Utub_Urls): The URL already containing the given UTub Tag
        utub_tag (Utub_Tags): The tag already on the URL

    Returns:
        tuple[Response, int]:
        - Response: JSON response on error.
        - int: HTTP status code 400
    """
    warning_log(
        f"User={current_user.id} tried adding UTubTag.tag_string={utub_tag.tag_string} to UTubURL.id={utub_url.id} but already on UTubURL"
    )
    return build_message_error_response(message=TAGS_FAILURE.TAG_ALREADY_ON_URL)


def _add_url_tag(utub_url: Utub_Urls, utub_tag: Utub_Tags) -> Utub_Url_Tags:
    """
    Adds a UTub tag to a given UTub URL.

    Args:
        utub_url (Utub_Urls): The UTub URL that has a tag being added to it
        utub_tag (Utub_Tags): The UTub Tag to add to the URL

    Returns:
        (Utub_Url_Tags): The newly created URL Tag
    """
    utub_url_tag = Utub_Url_Tags(
        utub_id=utub_url.utub_id, utub_url_id=utub_url.id, utub_tag_id=utub_tag.id
    )

    db.session.add(utub_url_tag)

    return utub_url_tag


def get_count_of_url_tag_in_utub(utub_tag: Utub_Tags) -> int:
    """
    Counts the number of URL Tags for a given UTub tag in a UTub.

    Args:
        utub_tag (Utub_Tags): The tag to check for in the UTub

    Returns:
        (int): The number of URL tags for this UTub Tag
    """
    return Utub_Url_Tags.query.filter(
        Utub_Url_Tags.utub_id == utub_tag.utub_id,
        Utub_Url_Tags.utub_tag_id == utub_tag.id,
    ).count()


def get_tag_applied_counts(utub_id: int, tag_ids: list[int]) -> dict[int, int]:
    """
    Counts, per tag, how many URLs in a UTub the tag is applied to, in a single
    bulk query (avoids an N+1 of per-tag count queries).

    Args:
        utub_id (int): The UTub whose tag applications are being counted
        tag_ids (list[int]): The tag ids to count applications for

    Returns:
        dict[int, int]: A mapping of tag id to its UTub-wide applied count. Tag
        ids with zero applications are absent from the mapping.

    Examples:
        >>> get_tag_applied_counts(utub_id=1, tag_ids=[])
        {}
        >>> get_tag_applied_counts(utub_id=1, tag_ids=[7])
        {7: 3}
        >>> get_tag_applied_counts(utub_id=1, tag_ids=[7, 9])
        {7: 3, 9: 1}
    """
    if not tag_ids:
        return {}

    count_rows = (
        db.session.query(
            Utub_Url_Tags.utub_tag_id, func.count(Utub_Url_Tags.utub_tag_id)
        )
        .filter(
            Utub_Url_Tags.utub_id == utub_id,
            Utub_Url_Tags.utub_tag_id.in_(tag_ids),
        )
        .group_by(Utub_Url_Tags.utub_tag_id)
        .all()
    )
    return {tag_id: count for tag_id, count in count_rows}
