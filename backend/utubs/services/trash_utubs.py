from backend import db
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.app_logger import safe_add_many_logs, warning_log
from backend.extensions.metrics.writer import record_event
from backend.metrics.events import EventName
from backend.models.utub_members import Member_Role
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.schemas.trash import UtubPurgedResponseSchema, UtubRestoredResponseSchema
from backend.utils.strings.trash_strs import TRASH_SUCCESS
from backend.utubs.guards import lock_trashed_utub_for_creator


def purge_trashed_utub(*, utub_id: int, current_user_id: int) -> FlaskResponse:
    """Permanently delete a trashed UTub ("Delete forever") for its creator.

    Shares restore's creator-only guard, so a UTub the caller may not restore is a
    404 here too, and a locked UTub is a 403. The ORM removes the ``members`` rows
    (no DB ``ondelete``) and the database cascades the UTub's tags, URL rows and
    URL-tag rows, as in the admin hard delete.

    Args:
        utub_id (int): The trashed UTub id from the path
        current_user_id (int): The acting user

    Returns:
        FlaskResponse: 200 with the purged UTub summary on success; 404 when the UTub
        is not an actionable trashed UTub of the caller; 403 when the UTub is locked.
    """
    guarded: Utubs | FlaskResponse = lock_trashed_utub_for_creator(utub_id=utub_id)
    if not isinstance(guarded, Utubs):
        db.session.rollback()
        return guarded
    utub: Utubs = guarded

    utub_name: str = utub.name
    try:
        purged_url_count: int = Utub_Urls.query.filter_by(utub_id=utub_id).count()
        db.session.delete(utub)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        warning_log(
            f"Purge trashed UTub failed | UTub.id={utub_id} "
            f"| error_type={type(exc).__name__}"
        )
        raise

    record_event(EventName.UTUB_PURGED_FROM_TRASH)
    safe_add_many_logs(
        [
            "Permanently deleted trashed UTub",
            f"User.id={current_user_id}",
            f"UTub.id={utub_id}",
            f"UTub.name={utub_name}",
            f"Purged URL count={purged_url_count}",
        ]
    )

    return APIResponse(
        message=TRASH_SUCCESS.UTUB_PURGED,
        data=UtubPurgedResponseSchema(
            utub_id=utub_id,
            utub_name=utub_name,
            purged_url_count=purged_url_count,
        ),
    ).to_response()


def restore_trashed_utub(*, utub_id: int, current_user_id: int) -> FlaskResponse:
    """Restore a trashed UTub for its creator.

    Clears ``deleted_at`` / ``deleted_by`` and bumps ``last_updated`` so the UTub
    sorts to the top of the creator's deck. URLs that were trashed on their own
    before the UTub was trashed keep their own ``deleted_at`` and stay in Trash;
    only the live rows become visible again, reported as ``restoredUrlCount``.

    Args:
        utub_id (int): The trashed UTub id from the path
        current_user_id (int): The acting user

    Returns:
        FlaskResponse: 200 with the restored UTub summary on success; 404 when the
        UTub is not an actionable trashed UTub of the caller (live, missing, already
        restored, or the caller is not its creator); 403 when the UTub is locked.
    """
    guarded: Utubs | FlaskResponse = lock_trashed_utub_for_creator(utub_id=utub_id)
    if not isinstance(guarded, Utubs):
        db.session.rollback()
        return guarded
    utub: Utubs = guarded

    try:
        utub.deleted_at = None
        utub.deleted_by = None
        utub.set_last_updated()
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        warning_log(
            f"Restore trashed UTub failed | UTub.id={utub_id} "
            f"| error_type={type(exc).__name__}"
        )
        raise

    restored_url_count: int = Utub_Urls.query.filter(
        Utub_Urls.utub_id == utub_id, Utub_Urls.deleted_at.is_(None)
    ).count()

    record_event(EventName.UTUB_RESTORED_FROM_TRASH)
    safe_add_many_logs(
        [
            "Restored trashed UTub",
            f"User.id={current_user_id}",
            f"UTub.id={utub.id}",
            f"UTub.name={utub.name}",
        ]
    )

    return APIResponse(
        message=TRASH_SUCCESS.UTUB_RESTORED,
        data=UtubRestoredResponseSchema(
            utub_id=utub.id,
            utub_name=utub.name,
            utub_description=utub.utub_description,
            member_role=Member_Role.CREATOR.value,
            is_locked=utub.is_locked,
            restored_url_count=restored_url_count,
        ),
    ).to_response()
