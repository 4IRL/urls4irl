from flask_login import current_user
from sqlalchemy.orm import selectinload

from backend import db
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.app_logger import safe_add_log
from backend.extensions.metrics.writer import record_event
from backend.metrics.events import EventName
from backend.models.user_preferences import SortOrder, resolve_preferences
from backend.models.utub_members import Utub_Members
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.schemas.users import UtubSummaryListSchema
from backend.schemas.utub_member_settings import resolve_member_settings
from backend.schemas.utubs import UtubDetailSchema
from backend.utils.datetime_utils import utc_now
from backend.utubs.services.trash_predicates import (
    count_trash_rows_for_user,
    load_summary_memberships_and_counts,
)


def _record_utub_opened_by(*, utub_id: int, user_id: int) -> None:
    # Bulk UPDATE of only the caller's own membership row: no ``Utubs`` lock or
    # write, and no ORM attribute set, so a membership deleted concurrently
    # updates 0 rows instead of raising ``StaleDataError``.
    Utub_Members.query.filter(
        Utub_Members.utub_id == utub_id,
        Utub_Members.user_id == user_id,
    ).update({Utub_Members.last_opened_at: utc_now()}, synchronize_session=False)


def _build_utub_detail_for_user(current_utub: Utubs) -> UtubDetailSchema:
    # DD-36: order the returned URL list server-side by the viewing user's saved
    # ``default_sort`` preference (defaulting to NEWEST when no UserPreferences
    # row exists). The live rows are fetched in one explicit query with the
    # per-URL relationships the serializer reads (standalone URL, tag links and
    # share link) eager-loaded via ``selectinload``, so the statement count does not
    # grow with the number of URLs; the in-memory list is then sorted. Both
    # GET /utubs/<id> and its api_v1 mirror share this service, so ordering here
    # covers both surfaces.
    # The caller's per-UTub ``urls.sort`` override (their own membership row)
    # beats that preference; an unset override falls back to it.
    default_sort = resolve_preferences(current_user.preferences).default_sort
    caller_settings = next(
        (
            member.settings
            for member in current_utub.members
            if member.user_id == current_user.id
        ),
        None,
    )
    sort_override = resolve_member_settings(caller_settings).urls.sort
    if sort_override is not None:
        default_sort = SortOrder(sort_override)
    # ``populate_existing`` refreshes rows the route guard already identity-mapped, so
    # the eager loads apply to them too. Trashed URLs are filtered out in SQL.
    live_utub_urls: list[Utub_Urls] = (
        Utub_Urls.query.populate_existing()
        .options(
            selectinload(Utub_Urls.standalone_url),
            selectinload(Utub_Urls.url_tags),
            selectinload(Utub_Urls.short_link),
        )
        .filter(
            Utub_Urls.utub_id == current_utub.id,
            Utub_Urls.deleted_at.is_(None),
        )
        .all()
    )
    if default_sort == SortOrder.TITLE_AZ:
        # ``url_title`` is DB-nullable (Python default ``""`` only), so coalesce
        # to ``""`` before ``.lower()`` — a NULL title can never raise here.
        ordered_utub_urls: list[Utub_Urls] = sorted(
            live_utub_urls,
            key=lambda utub_url: (utub_url.url_title or "").lower(),
        )
    elif default_sort == SortOrder.OLDEST:
        ordered_utub_urls = sorted(
            live_utub_urls, key=lambda utub_url: utub_url.added_at
        )
    else:  # SortOrder.NEWEST (default)
        ordered_utub_urls = sorted(
            live_utub_urls,
            key=lambda utub_url: utub_url.added_at,
            reverse=True,
        )

    return UtubDetailSchema.from_utub(current_utub, current_user.id, ordered_utub_urls)


def get_single_utub_for_user(current_utub: Utubs) -> FlaskResponse:
    utub_schema = _build_utub_detail_for_user(current_utub)

    _record_utub_opened_by(utub_id=current_utub.id, user_id=current_user.id)
    db.session.commit()

    safe_add_log(f"Retrieving UTub.id={current_utub.id} from direct route")
    record_event(EventName.UTUB_OPENED)
    return APIResponse(data=utub_schema, status_code=200).to_response()


def refresh_single_utub_for_user(current_utub: Utubs) -> FlaskResponse:
    # Read-only twin of ``get_single_utub_for_user``: no ``last_opened_at``
    # write, no commit and no ``UTUB_OPENED`` event (a refresh is not an open).
    utub_schema = _build_utub_detail_for_user(current_utub)

    safe_add_log(f"Refreshed UTub={current_utub.id}")
    return APIResponse(data=utub_schema, status_code=200).to_response()


def get_all_utubs_of_user() -> FlaskResponse:
    # TODO: Should serialized summary be utubID and utubName
    # instead of id and name?
    safe_add_log(f"Returning UTubs for User={current_user.id}")

    rows = load_summary_memberships_and_counts(current_user.id)
    return APIResponse(
        data=UtubSummaryListSchema.from_user(
            memberships=rows.memberships,
            counts=rows.counts,
            preferences=rows.preferences,
            trash_count=count_trash_rows_for_user(user_id=current_user.id),
        ),
        status_code=200,
    ).to_response()
