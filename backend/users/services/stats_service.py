from __future__ import annotations

from datetime import datetime
from typing import Any

from dateutil.relativedelta import relativedelta
from flask_login import current_user

from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.utils.datetime_utils import utc_now


def _humanize_account_age(created_at: datetime) -> str:
    """Render the authenticated user's account age as a single, largest-unit
    relative phrase (e.g. ``"2 years"``, ``"1 month"``, ``"3 days"``).

    Uses ``relativedelta`` so month/year rollovers respect calendar lengths
    rather than a fixed day count. Picks the largest non-zero unit in
    years → months → days order and pluralizes on ``n != 1``. Returns the
    literal ``"Joined today"`` when the account was created earlier the same
    calendar day (all three units zero); this placeholder is replaced with the
    string-bridge constant in Step 3.
    """
    age = relativedelta(utc_now(), created_at)
    if age.years:
        unit_value, unit_label = age.years, "year"
    elif age.months:
        unit_value, unit_label = age.months, "month"
    elif age.days:
        unit_value, unit_label = age.days, "day"
    else:
        return "Joined today"
    plural_suffix = "" if unit_value == 1 else "s"
    return f"{unit_value} {unit_label}{plural_suffix}"


def build_user_stats_context() -> dict[str, Any]:
    """Build the Settings page Stats panel template context for the
    authenticated user.

    Mirrors ``build_connected_accounts_context()`` — no parameters, reads
    ``current_user``, returns a flat dict of read-only personal counts plus the
    member-since values. Every count is a ``COUNT`` query filtered on the acting
    user's id; NULL-attributed legacy ``Utub_Url_Tags`` rows are excluded from
    the "tags applied" count automatically.
    """
    stats_utubs_created = Utubs.query.filter_by(utub_creator=current_user.id).count()
    stats_member_of = (
        Utub_Members.query.filter_by(user_id=current_user.id)
        .filter(Utub_Members.member_role != Member_Role.CREATOR)
        .count()
    )
    stats_urls_added = Utub_Urls.query.filter_by(user_id=current_user.id).count()
    stats_tags_created = Utub_Tags.query.filter_by(created_by=current_user.id).count()
    stats_tags_applied = Utub_Url_Tags.query.filter_by(user_id=current_user.id).count()

    return {
        "stats_utubs_created": stats_utubs_created,
        "stats_member_of": stats_member_of,
        "stats_urls_added": stats_urls_added,
        "stats_tags_created": stats_tags_created,
        "stats_tags_applied": stats_tags_applied,
        "stats_member_since_relative": _humanize_account_age(current_user.created_at),
        "stats_member_since_iso": current_user.created_at.date().isoformat(),
        "stats_member_since_exact": current_user.created_at.strftime(
            "%B %d, %Y"
        ).replace(" 0", " "),
    }
