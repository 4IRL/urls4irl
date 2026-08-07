from flask_login import current_user
from backend import db
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.app_logger import safe_add_log
from backend.extensions.metrics.writer import record_event
from backend.metrics.events import EventName
from backend.models.user_preferences import SortOrder
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.schemas.users import UtubSummaryListSchema
from backend.schemas.utubs import UtubDetailSchema


def get_single_utub_for_user(current_utub: Utubs) -> FlaskResponse:
    # DD-36: order the returned URL list server-side by the viewing user's saved
    # ``default_sort`` preference (defaulting to NEWEST when no UserPreferences
    # row exists). ``utub_urls`` is a fully-materializing list relationship
    # already loaded into memory, so the in-memory list is sorted rather than
    # issuing a second parallel query. Both GET /utubs/<id> and its api_v1 mirror
    # share this service, so ordering here covers both surfaces.
    default_sort = (
        current_user.preferences.default_sort
        if current_user.preferences is not None
        else SortOrder.NEWEST
    )
    if default_sort == SortOrder.TITLE_AZ:
        # ``url_title`` is DB-nullable (Python default ``""`` only), so coalesce
        # to ``""`` before ``.lower()`` — a NULL title can never raise here.
        ordered_utub_urls: list[Utub_Urls] = sorted(
            current_utub.utub_urls,
            key=lambda utub_url: (utub_url.url_title or "").lower(),
        )
    elif default_sort == SortOrder.OLDEST:
        ordered_utub_urls = sorted(
            current_utub.utub_urls, key=lambda utub_url: utub_url.added_at
        )
    else:  # SortOrder.NEWEST (default)
        ordered_utub_urls = sorted(
            current_utub.utub_urls,
            key=lambda utub_url: utub_url.added_at,
            reverse=True,
        )

    utub_schema = UtubDetailSchema.from_utub(
        current_utub, current_user.id, ordered_utub_urls
    )

    current_utub.set_last_updated()
    db.session.commit()

    safe_add_log(f"Retrieving UTub.id={current_utub.id} from direct route")
    record_event(EventName.UTUB_OPENED)
    return APIResponse(data=utub_schema, status_code=200).to_response()


def get_all_utubs_of_user() -> FlaskResponse:
    # TODO: Should serialized summary be utubID and utubName
    # instead of id and name?
    safe_add_log(f"Returning UTubs for User={current_user.id}")

    return APIResponse(
        data=UtubSummaryListSchema.from_user(current_user), status_code=200
    ).to_response()
