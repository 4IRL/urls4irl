from __future__ import annotations

from backend.api_common.responses import FlaskResponse
from backend.models.utubs import Utubs
from backend.schemas.errors import build_message_error_response
from backend.utils.strings.utub_strs import UTUB_FAILURE


def reject_if_utub_locked(utub: Utubs, *, error_code: int) -> FlaskResponse | None:
    """Return a 403 'UTub is locked' response when the UTub is locked, else None.

    Shared write-guard for the content-add services (add URL / member / UTub tag /
    URL tag). Callers pass their own domain error_code so the API contract per
    domain is unchanged. Mirrors the reject_* guard helpers in backend/admin/guards.py.
    """
    if utub.is_locked:
        return build_message_error_response(
            message=UTUB_FAILURE.UTUB_IS_LOCKED,
            error_code=error_code,
            status_code=403,
        )
    return None
