from typing import NamedTuple

from backend import db
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.app_logger import safe_add_many_logs, warning_log
from backend.extensions.metrics.writer import record_event
from backend.metrics.events import EventName
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.schemas.errors import build_message_error_response
from backend.schemas.tags import UtubTagSchema
from backend.schemas.trash import UrlRestoredResponseSchema
from backend.schemas.urls import UtubUrlSchema
from backend.tags.services.create_url_tag import get_tag_applied_counts
from backend.urls.constants import URLErrorCodes, UrlRestoreTarget
from backend.urls.services.delete_urls import recompute_tag_counts_after_delete
from backend.urls.services.trashed_url_tags import count_lost_trashed_tags
from backend.utils.strings.trash_strs import TRASH_FAILURE, TRASH_SUCCESS
from backend.utubs.guards import reject_if_utub_locked
from backend.utubs.services.trash_predicates import trashed_url_rows_actionable_by


class LockedTrashedUrl(NamedTuple):
    """A trashed URL row-locked for a Trash action, with its origin UTub and the actor's membership."""

    utub_url: Utub_Urls
    origin_utub: Utubs
    membership: Utub_Members


def _lock_actionable_trashed_url(
    *, utub_id: int, utub_url_id: int, current_user_id: int
) -> LockedTrashedUrl | FlaskResponse:
    """Resolve and row-lock the one trashed URL ``current_user_id`` may act on.

    Narrows and locks the SAME ``Select`` the Trash list uses
    (``trashed_url_rows_actionable_by``), never a second hand-written predicate, so
    "is this URL actionable" has exactly one implementation shared by the list and
    every Trash action. ``of=Utub_Urls`` scopes the row lock to the URL row even though
    the statement also joins ``Utubs`` and ``Utub_Members``; ``populate_existing`` is
    needed for the same reason documented on ``lock_utub_for_update`` (an earlier read
    in this request may have cached a stale instance).

    A row the predicate excludes, a row that does not exist, and a ``utub_id`` /
    ``utub_url_id`` mismatch are all the same 404, so a caller can never probe whether
    an id exists or what state it is in. The lock check runs only AFTER the row is
    proved actionable, so a non-actionable viewer never learns that a UTub is locked.

    Args:
        utub_id (int): The origin UTub id from the path
        utub_url_id (int): The Utub_Urls id from the path
        current_user_id (int): The acting user

    Returns:
        LockedTrashedUrl | FlaskResponse: The locked URL row, its origin UTub and the
        acting user's membership row, or the error response (the session is already
        rolled back in that case). A ``FlaskResponse`` is itself a plain tuple, so
        callers must discriminate with ``isinstance(..., LockedTrashedUrl)``, never
        ``isinstance(..., tuple)``.
    """
    locking_statement = (
        trashed_url_rows_actionable_by(user_id=current_user_id)
        .where(Utub_Urls.id == utub_url_id, Utub_Urls.utub_id == utub_id)
        .with_for_update(of=Utub_Urls)
        .execution_options(populate_existing=True)
    )
    locked_row = db.session.execute(locking_statement).one_or_none()

    if locked_row is None:
        db.session.rollback()
        return build_message_error_response(
            message=TRASH_FAILURE.NOT_IN_TRASH,
            error_code=URLErrorCodes.NOT_IN_TRASH,
            status_code=404,
        )

    utub_url, origin_utub, membership = locked_row

    utub_locked_error: FlaskResponse | None = reject_if_utub_locked(
        origin_utub, error_code=URLErrorCodes.UTUB_IS_LOCKED
    )
    if utub_locked_error is not None:
        db.session.rollback()
        return utub_locked_error

    return LockedTrashedUrl(
        utub_url=utub_url, origin_utub=origin_utub, membership=membership
    )


def restore_trashed_url(
    *,
    utub_id: int,
    utub_url_id: int,
    dest_utub_id: int | None,
    current_user_id: int,
) -> FlaskResponse:
    """Restore a trashed URL.

    A restore keeps the row exactly as it was (adder, added-at and title), unlike a
    revive, which re-adds the URL as a new addition by the reviving user. Its tag
    associations were never removed on trash, so they come back with the row; tags
    deleted from the UTub in the meantime are reported as ``lostTagCount``.

    Membership and UTub state are read when the URL row is locked. A concurrent
    member removal or UTub delete that commits in the narrow window before this
    commit is an accepted race, shared with the sibling delete flows.

    Args:
        utub_id (int): The origin UTub id from the path
        utub_url_id (int): The Utub_Urls id from the path
        dest_utub_id (int | None): The requested destination UTub, if any
        current_user_id (int): The acting user

    Returns:
        FlaskResponse: 200 with the restored URL card on success; 404 when the URL is
        not actionable in Trash, 403 when its UTub is locked, 400 on a bad destination.
    """
    resolved = _lock_actionable_trashed_url(
        utub_id=utub_id, utub_url_id=utub_url_id, current_user_id=current_user_id
    )
    if not isinstance(resolved, LockedTrashedUrl):
        return resolved
    utub_url, origin_utub, membership = resolved

    if origin_utub.deleted_at is not None:
        # Step 3: replace with the move-into-destination branch.
        db.session.rollback()
        return build_message_error_response(
            message=TRASH_FAILURE.DESTINATION_REQUIRED,
            error_code=URLErrorCodes.DESTINATION_REQUIRED,
            status_code=400,
        )

    if dest_utub_id not in (None, utub_id):
        db.session.rollback()
        return build_message_error_response(
            message=TRASH_FAILURE.INVALID_DESTINATION,
            error_code=URLErrorCodes.INVALID_DESTINATION,
            status_code=400,
        )

    lost_tag_count: int

    try:
        # Read BEFORE the snapshot is cleared.
        lost_tag_count = count_lost_trashed_tags(utub_url)

        # Reassign (never mutate) the JSONB snapshot. user_id, added_at, url_title and
        # last_accessed stay untouched: restore is not revive.
        utub_url.deleted_at = None
        utub_url.deleted_by = None
        utub_url.trashed_tag_ids = None
        db.session.flush()

        tag_counts: dict[int, int] = recompute_tag_counts_after_delete(
            utub_id=utub_id, affected_utub_tag_ids=set(utub_url.associated_tag_ids)
        )
        origin_utub.set_last_updated()
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        warning_log(
            f"Restore trashed URL failed | UTub.id={utub_id} "
            f"| UTubURL.id={utub_url_id} "
            f"| error_type={type(exc).__name__}"
        )
        raise

    record_event(
        EventName.URL_RESTORED_FROM_TRASH,
        dimensions={"restore_target": UrlRestoreTarget.ORIGIN.value},
    )
    safe_add_many_logs(
        [
            "Restored trashed UTubURL in place",
            f"User.id={current_user_id}",
            f"UTub.id={utub_id}",
            f"UTubURL.id={utub_url_id}",
        ]
    )

    viewer_is_manager: bool = membership.member_role in (
        Member_Role.CREATOR,
        Member_Role.CO_CREATOR,
    )
    surviving_tag_ids: list[int] = utub_url.associated_tag_ids
    surviving_tags: list[Utub_Tags] = (
        Utub_Tags.query.filter(Utub_Tags.id.in_(surviving_tag_ids))
        .order_by(Utub_Tags.id)
        .all()
        if surviving_tag_ids
        else []
    )
    applied_counts: dict[int, int] = get_tag_applied_counts(
        utub_id, [utub_tag.id for utub_tag in surviving_tags]
    )

    return APIResponse(
        message=TRASH_SUCCESS.URL_RESTORED,
        data=UrlRestoredResponseSchema(
            utub_id=utub_id,
            utub_name=origin_utub.name,
            url=UtubUrlSchema.from_orm_url(
                utub_url, current_user_id, viewer_is_manager
            ),
            restored_to_destination=False,
            applied_tags=[
                UtubTagSchema(
                    id=utub_tag.id,
                    tag_string=utub_tag.tag_string,
                    tag_applied=applied_counts.get(utub_tag.id, 0),
                )
                for utub_tag in surviving_tags
            ],
            tag_counts_modified=tag_counts,
            lost_tag_count=lost_tag_count,
        ),
    ).to_response()
