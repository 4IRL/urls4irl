from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_serializer

from backend.schemas.base import BaseSchema, StatusMessageResponseSchema


class ExportAccountSchema(BaseSchema):
    """The acting user's own account fields — identity only, no secrets and no
    internal database IDs (data-minimization: the export is human-readable, not
    a re-import anchor)."""

    username: str = Field(description="The user's username")
    email: str = Field(description="The user's email address")
    member_since: datetime = Field(
        alias="memberSince",
        description="Account creation timestamp (ISO 8601)",
    )

    @field_serializer("member_since")
    def serialize_member_since(self, value: datetime) -> str:
        return value.isoformat()


class ExportPreferencesSchema(BaseSchema):
    """The acting user's stored display/view preferences. Every value is already
    an enum ``.value`` string, so all fields are plain ``str`` (mirroring
    ``ExportAccountSchema``'s field-per-attribute style). When the user has no
    ``UserPreferences`` row (pre-existing user), each field carries its enum
    default."""

    theme: str = Field(description="The app-wide color theme (light/dark/system)")
    default_view: str = Field(
        alias="defaultView",
        description="The default UTub URL view mode (list/compact/cards)",
    )
    default_sort: str = Field(
        alias="defaultSort",
        description="The default URL sort order (newest/oldest/title_az)",
    )
    density: str = Field(description="The layout density (comfortable/compact)")
    date_format: str = Field(
        alias="dateFormat",
        description="The date display format (iso/us/eu)",
    )


class ExportMemberSchema(BaseSchema):
    """A member of a UTub the acting user belongs to. Identified by username
    only — no internal user ID (third-party data-minimization)."""

    username: str = Field(description="The member's username")
    role: str = Field(description="The member's role within the UTub")


class ExportTagSchema(BaseSchema):
    """A tag in a UTub's tag vocabulary. No internal IDs; the creator is
    attributed by username."""

    tag_string: str = Field(alias="tagString", description="The tag text")
    created_by: str = Field(
        alias="createdBy",
        description="Username of the tag's creator",
    )
    created_at: datetime = Field(
        alias="createdAt",
        description="Tag creation timestamp (ISO 8601)",
    )

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        return value.isoformat()


class ExportUrlSchema(BaseSchema):
    """A URL within a UTub, with its applied tag strings. No internal IDs; the
    adder is attributed by username."""

    url: str = Field(description="The URL string")
    title: str | None = Field(description="Display title for the URL, or null")
    added_at: datetime = Field(
        alias="addedAt",
        description="Timestamp the URL was added to the UTub (ISO 8601)",
    )
    added_by: str = Field(
        alias="addedBy",
        description="Username of the member who added the URL",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Tag strings applied to this URL within the UTub",
    )

    @field_serializer("added_at")
    def serialize_added_at(self, value: datetime) -> str:
        return value.isoformat()


class ExportUtubSchema(BaseSchema):
    """A UTub the acting user belongs to (created or joined), fully expanded.
    No internal database ID (data-minimization)."""

    name: str = Field(description="The UTub's name")
    description: str | None = Field(description="The UTub's description, or null")
    role: str = Field(description="The acting user's role within this UTub")
    is_locked: bool = Field(
        alias="isLocked",
        description="Whether the UTub is locked (frozen to all user mutations)",
    )
    created_at: datetime = Field(
        alias="createdAt",
        description="UTub creation timestamp (ISO 8601)",
    )
    urls: list[ExportUrlSchema] = Field(
        default_factory=list,
        description="URLs in the UTub, each with applied tags",
    )
    tags: list[ExportTagSchema] = Field(
        default_factory=list,
        description="The UTub's tag vocabulary",
    )
    members: list[ExportMemberSchema] = Field(
        default_factory=list,
        description="Members of the UTub",
    )

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        return value.isoformat()


class UserDataExportSchema(BaseSchema):
    """Full user-data export: the account block plus every UTub the user is a
    member of (created + joined), each expanded with its URLs, tags, and
    members. Purpose-built so the export shape is decoupled from the live-API
    response schemas and never carries viewer-relative or secret fields."""

    exported_at: datetime = Field(
        alias="exportedAt",
        description="Timestamp the export was generated (ISO 8601)",
    )
    account: ExportAccountSchema = Field(
        description="The acting user's own account fields"
    )
    preferences: ExportPreferencesSchema = Field(
        description="The user's stored display/view preferences"
    )
    utubs: list[ExportUtubSchema] = Field(
        default_factory=list,
        description="Every UTub the user belongs to, created or joined",
    )

    @field_serializer("exported_at")
    def serialize_exported_at(self, value: datetime) -> str:
        return value.isoformat()


class UserDataExportResponseSchema(StatusMessageResponseSchema):
    """Response envelope for ``GET /users/<id>/data-export``.

    Nests the full export under a single ``export`` key (on top of the standard
    ``status``/``message`` envelope fields) so the client can blob ``response.export``
    cleanly for the downloaded file without the envelope metadata leaking into it.
    """

    export: UserDataExportSchema = Field(
        description="The full user-data export payload"
    )


ExportUtubSchema.model_rebuild()
UserDataExportSchema.model_rebuild()
UserDataExportResponseSchema.model_rebuild()
