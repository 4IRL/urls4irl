from __future__ import annotations

from datetime import datetime

from backend.models.user_preferences import (
    DateFormat,
    Density,
    SortOrder,
    Theme,
    ViewMode,
)
from backend.models.users import Users
from backend.models.utub_members import Utub_Members
from backend.models.utub_urls import Utub_Urls
from backend.schemas.exports import (
    ExportAccountSchema,
    ExportMemberSchema,
    ExportPreferencesSchema,
    ExportTagSchema,
    ExportUrlSchema,
    ExportUtubSchema,
    UserDataExportSchema,
)
from backend.utils.strings.model_strs import MODELS as MODEL_STRS

# Fallback attribution when a contributor's Users row can't be resolved (should
# not occur under FK integrity, but keeps the export schema's `str` contract
# without fabricating an identity or leaking an internal ID).
_UNKNOWN_CONTRIBUTOR = "(unknown user)"


def _build_export_url(
    *, utub_url: Utub_Urls, username_by_id: dict[int, str]
) -> ExportUrlSchema:
    """Serialize one UTub URL, reading applied tag strings from the
    ``associated_tags`` property (a ``list[dict]`` keyed by ``MODEL_STRS`` —
    subscript access, not attribute access). The adder is attributed by
    username (resolved from ``username_by_id``), never an internal user ID."""
    return ExportUrlSchema(
        url=utub_url.standalone_url.url_string,
        title=utub_url.url_title,
        added_at=utub_url.added_at,
        added_by=username_by_id.get(utub_url.user_id, _UNKNOWN_CONTRIBUTOR),
        tags=[
            applied_tag[MODEL_STRS.TAG_STRING]
            for applied_tag in utub_url.associated_tags
        ],
    )


def _build_export_utub(
    *, membership: Utub_Members, username_by_id: dict[int, str]
) -> ExportUtubSchema:
    """Serialize the UTub behind a membership row, tagging it with the acting
    user's role (lowercase ``Member_Role.value`` form). Contributors (URL
    adders, tag creators, members) are identified by username only — no
    internal IDs."""
    utub = membership.to_utub
    return ExportUtubSchema(
        name=utub.name,
        description=utub.utub_description,
        role=membership.member_role.value,
        is_locked=utub.is_locked,
        created_at=utub.created_at,
        urls=[
            _build_export_url(utub_url=utub_url, username_by_id=username_by_id)
            for utub_url in utub.utub_urls
        ],
        tags=[
            ExportTagSchema(
                tag_string=utub_tag.tag_string,
                created_by=username_by_id.get(
                    utub_tag.created_by, _UNKNOWN_CONTRIBUTOR
                ),
                created_at=utub_tag.created_at,
            )
            for utub_tag in utub.utub_tags
        ],
        members=[
            ExportMemberSchema(
                username=member.to_user.username,
                role=member.member_role.value,
            )
            for member in utub.members
        ],
    )


def _resolve_contributor_usernames(
    memberships: list[Utub_Members],
) -> dict[int, str]:
    """Collect every user ID that contributed a URL or tag across the given
    UTubs and resolve their usernames in a single query. Resolving from the
    ``Users`` table (rather than each UTub's current member list) keeps
    attribution intact even when a contributor later left the UTub."""
    contributor_ids: set[int] = set()
    for membership in memberships:
        utub = membership.to_utub
        for utub_url in utub.utub_urls:
            contributor_ids.add(utub_url.user_id)
        for utub_tag in utub.utub_tags:
            contributor_ids.add(utub_tag.created_by)

    if not contributor_ids:
        return {}

    return {
        contributor.id: contributor.username
        for contributor in Users.query.filter(Users.id.in_(contributor_ids)).all()
    }


def build_user_data_export_core(
    *, user: Users, generated_at: datetime
) -> UserDataExportSchema:
    """Guard-free core that serializes every UTub the ``user`` belongs to
    (created + joined) with its URLs, tags, and members, plus the user's own
    account identity fields — no secrets, no session fields, no viewer-relative
    coupling, and no internal database IDs (data-minimization: other users
    appear by username only, never by internal ID).

    ``generated_at`` is injected (never read from ``utc_now()`` here) so callers
    and tests control the export timestamp deterministically; a thin HTTP
    wrapper defaults it to ``utc_now()``.
    """
    account = ExportAccountSchema(
        username=user.username,
        email=user.email,
        member_since=user.created_at,
    )
    # Build the preferences section the same way ``account`` is built, defaulting
    # each field to its enum default when the user has no ``UserPreferences`` row
    # (pre-existing user), mirroring ``build_display_preferences_context``'s
    # None-row defaulting.
    preferences_row = user.preferences
    preferences = ExportPreferencesSchema(
        theme=(
            preferences_row.theme if preferences_row is not None else Theme.SYSTEM
        ).value,
        default_view=(
            preferences_row.default_view
            if preferences_row is not None
            else ViewMode.LIST
        ).value,
        default_sort=(
            preferences_row.default_sort
            if preferences_row is not None
            else SortOrder.NEWEST
        ).value,
        density=(
            preferences_row.density
            if preferences_row is not None
            else Density.COMFORTABLE
        ).value,
        date_format=(
            preferences_row.date_format
            if preferences_row is not None
            else DateFormat.ISO
        ).value,
    )
    memberships = user.utubs_is_member_of
    username_by_id = _resolve_contributor_usernames(memberships)
    utubs = [
        _build_export_utub(membership=membership, username_by_id=username_by_id)
        for membership in memberships
    ]
    return UserDataExportSchema(
        exported_at=generated_at,
        account=account,
        preferences=preferences,
        utubs=utubs,
    )
