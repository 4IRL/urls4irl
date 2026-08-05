from __future__ import annotations

from datetime import datetime

from backend.models.users import Users
from backend.models.utub_members import Utub_Members
from backend.models.utub_urls import Utub_Urls
from backend.schemas.exports import (
    ExportAccountSchema,
    ExportMemberSchema,
    ExportTagSchema,
    ExportUrlSchema,
    ExportUtubSchema,
    UserDataExportSchema,
)
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.model_strs import MODELS as MODEL_STRS


def _build_export_url(utub_url: Utub_Urls) -> ExportUrlSchema:
    """Serialize one UTub URL, reading applied tag strings from the
    ``associated_tags`` property (a ``list[dict]`` keyed by ``MODEL_STRS`` —
    subscript access, not attribute access)."""
    return ExportUrlSchema(
        id=utub_url.id,
        url=utub_url.standalone_url.url_string,
        title=utub_url.url_title,
        added_at=utub_url.added_at,
        added_by_user_id=utub_url.user_id,
        tags=[
            applied_tag[MODEL_STRS.TAG_STRING]
            for applied_tag in utub_url.associated_tags
        ],
    )


def _build_export_utub(membership: Utub_Members) -> ExportUtubSchema:
    """Serialize the UTub behind a membership row, tagging it with the acting
    user's role (lowercase ``Member_Role.value`` form)."""
    utub = membership.to_utub
    return ExportUtubSchema(
        id=utub.id,
        name=utub.name,
        description=utub.utub_description,
        role=membership.member_role.value,
        is_locked=utub.is_locked,
        created_at=utub.created_at,
        urls=[_build_export_url(utub_url) for utub_url in utub.utub_urls],
        tags=[
            ExportTagSchema(
                id=utub_tag.id,
                tag_string=utub_tag.tag_string,
                created_by_user_id=utub_tag.created_by,
                created_at=utub_tag.created_at,
            )
            for utub_tag in utub.utub_tags
        ],
        members=[
            ExportMemberSchema(
                user_id=member.to_user.id,
                username=member.to_user.username,
                role=member.member_role.value,
            )
            for member in utub.members
        ],
    )


def build_user_data_export_core(
    *, user: Users, generated_at: datetime
) -> UserDataExportSchema:
    """Guard-free core that serializes every UTub the ``user`` belongs to
    (created + joined) with its URLs, tags, and members, plus the user's own
    account identity fields — no secrets, no session fields, no viewer-relative
    coupling.

    ``generated_at`` is injected (never read from ``utc_now()`` here) so callers
    and tests control the export timestamp deterministically; a thin HTTP
    wrapper defaults it to ``utc_now()``.
    """
    account = ExportAccountSchema(
        id=user.id,
        username=user.username,
        email=user.email,
        member_since=user.created_at,
    )
    utubs = [_build_export_utub(membership) for membership in user.utubs_is_member_of]
    return UserDataExportSchema(
        exported_at=generated_at,
        account=account,
        utubs=utubs,
    )


def build_user_data_export(*, user: Users) -> UserDataExportSchema:
    """Thin wrapper over :func:`build_user_data_export_core` that stamps the
    export with the current time. HTTP callers use this; deterministic tests
    call the core directly."""
    return build_user_data_export_core(user=user, generated_at=utc_now())
