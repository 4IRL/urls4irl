from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import Field

from backend.schemas.base import BaseSchema, StatusMessageResponseSchema
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import MODELS
from backend.utils.strings.user_strs import MEMBER, REDIRECT_URL
from backend.utils.strings.utub_strs import UTUB_ID

if TYPE_CHECKING:
    from backend.models.users import Users


class UserSchema(BaseSchema):
    id: int = Field(alias=MODELS.ID, description="Unique user ID")
    username: str = Field(alias=MODELS.USERNAME, description="Username of the user")


MemberSchema = UserSchema


class UtubMemberSchema(BaseSchema):
    """A member of a UTub, carrying their role, for the open-UTub detail response.

    Distinct from the shared ``UserSchema``/``MemberSchema`` (reused by the
    add/remove-member responses where a role isn't naturally present) so that
    role exposure is scoped to the detail response only.
    """

    id: int = Field(alias=MODELS.ID, description="Unique user ID")
    username: str = Field(alias=MODELS.USERNAME, description="Username of the user")
    member_role: str = Field(
        alias=MODELS.MEMBER_ROLE,
        description="Role of the member in the UTub",
    )


class CoMemberSchema(BaseSchema):
    """A co-member add candidate: a user who shares >=1 other UTub with the
    requester and is not already a member of the target UTub."""

    id: int = Field(alias=MODELS.ID, description="Unique user ID")
    username: str = Field(alias=MODELS.USERNAME, description="Username of the user")
    shared_utub_count: int = Field(
        alias=MODELS.SHARED_UTUB_COUNT,
        description="Number of the requester's UTubs this candidate also belongs to",
    )


class CoMemberListSchema(BaseSchema):
    """Wrapper list of co-member add candidates for the target UTub.

    A wrapper (never a bare list) because ``APIResponse`` spreads the data dict
    at the top level via ``**data_dict``.
    """

    members: list[CoMemberSchema] = Field(
        default_factory=list,
        alias=MODELS.MEMBERS,
        description="Co-member add candidates for the target UTub",
    )


class UtubSummaryItemSchema(BaseSchema):
    id: int = Field(alias=MODELS.ID, description="Unique UTub ID")
    name: str = Field(alias=MODELS.NAME, description="Name of the UTub")
    member_role: str = Field(
        alias=MODELS.MEMBER_ROLE,
        description="Role of the current user in the UTub",
    )
    is_locked: bool = Field(
        alias=MODELS.IS_LOCKED,
        description="Whether the UTub is locked (frozen to all user mutations)",
    )


class UtubSummaryListSchema(BaseSchema):
    """List of UTub summaries"""

    utubs: list[UtubSummaryItemSchema] = Field(
        alias=MODELS.UTUBS,
        description="List of UTubs the user is a member of",
    )

    @classmethod
    def from_user(cls, user: Users) -> UtubSummaryListSchema:
        sorted_utubs = sorted(
            user.utubs_is_member_of,
            key=lambda membership: membership.to_utub.last_updated,
            reverse=True,
        )
        return cls(
            utubs=[
                UtubSummaryItemSchema(
                    id=membership.to_utub.id,
                    name=membership.to_utub.name,
                    member_role=membership.member_role.value,
                    is_locked=membership.to_utub.is_locked,
                )
                for membership in sorted_utubs
            ]
        )


UtubSummaryListSchema.model_rebuild()


class LoginRedirectResponseSchema(BaseSchema):
    """Login successful with redirect URL"""

    redirect_url: str = Field(
        alias=REDIRECT_URL,
        description="URL to redirect to after login",
    )


class MemberModifiedResponseSchema(BaseSchema):
    utub_id: int = Field(
        alias=UTUB_ID,
        description="ID of the UTub the member was added to or removed from",
    )
    member: UserSchema = Field(
        alias=MEMBER,
        description="User object for the member added or removed",
    )


class OwnershipTransferredResponseSchema(BaseSchema):
    """Response for the transfer-ownership endpoint (web + /api/v1 twin).

    Reuses the role-carrying ``UtubMemberSchema`` for both the promoted member
    (now ``CREATOR``) and the demoted outgoing owner (now ``CO_CREATOR``), so
    the client can update both role displays without a reload.
    """

    utub_id: int = Field(
        alias=UTUB_ID,
        description="ID of the UTub whose ownership was transferred",
    )
    new_owner: UtubMemberSchema = Field(
        alias=MODELS.NEW_OWNER,
        description="The promoted member, now CREATOR",
    )
    previous_owner: UtubMemberSchema = Field(
        alias=MODELS.PREVIOUS_OWNER,
        description="The demoted member, now CO_CREATOR",
    )


class ChangeUsernameResponseSchema(BaseSchema):
    """Response for the authenticated change-username endpoint.

    One shape for every 200 response — the success branch and the no-op branch
    both populate all three fields, differing only in ``status``/``message``
    (DD-12: the banner text is server-sourced off ``message``). Carries the
    echoed ``username`` on top of the ``StatusMessageResponseSchema`` shape so
    the client can refresh the on-page displays without a reload (DD-15).
    """

    username: str = Field(
        alias=MODELS.USERNAME,
        description="The account's username after the change (echoed back)",
    )
    status: Literal["Success", "No change"] = Field(
        alias=STD_JSON.STATUS,
        description="Response status: Success or No change",
    )
    message: str = Field(
        alias=STD_JSON.MESSAGE,
        description="Human-readable, server-sourced banner text",
    )


class UpdatePreferencesResponseSchema(BaseSchema):
    """Response for the authenticated update-preferences endpoint
    (``PUT /users/<id>/preferences``).

    One shape for every 200 response — the success branch and the no-op branch
    both echo all five persisted preference values (each an enum ``.value``
    string), differing only in ``status``/``message`` (the banner text is
    server-sourced off ``message``, mirroring ``ChangeUsernameResponseSchema``).
    Echoing the stored values lets the client refresh its in-memory state
    without a reload.
    """

    theme: str = Field(
        alias=MODELS.THEME,
        description="The account's theme after the change (echoed back)",
    )
    default_view: str = Field(
        alias=MODELS.DEFAULT_VIEW,
        description="The account's default view mode after the change",
    )
    default_sort: str = Field(
        alias=MODELS.DEFAULT_SORT,
        description="The account's default sort order after the change",
    )
    density: str = Field(
        alias=MODELS.DENSITY,
        description="The account's layout density after the change",
    )
    date_format: str = Field(
        alias=MODELS.DATE_FORMAT,
        description="The account's date format after the change",
    )
    status: Literal["Success", "No change"] = Field(
        alias=STD_JSON.STATUS,
        description="Response status: Success or No change",
    )
    message: str = Field(
        alias=STD_JSON.MESSAGE,
        description="Human-readable, server-sourced banner text",
    )


class ChangePasswordResponseSchema(StatusMessageResponseSchema):
    """Response for the authenticated change-password endpoint.

    No data to return beyond status/message, so it reuses the
    ``StatusMessageResponseSchema`` shape (matching the
    ``RegisterResponseSchema``/``ResetPasswordResponseSchema`` convention).
    """

    pass


class ChangeEmailResponseSchema(StatusMessageResponseSchema):
    """Response for the authenticated change-email START endpoint
    (``PUT /users/<id>/email``).

    Carries ``status``/``message`` (DD-12 banner text is server-sourced off
    ``message``) plus the just-staged ``pending_email`` (DD-6) so the client can
    patch the account-info card in place without a reload. ``pending_email`` is
    optional/``None``-defaulted because the no-op guard (guard 5) also builds
    this schema and nothing is staged in that branch.
    """

    pending_email: str | None = Field(
        default=None,
        alias=MODELS.PENDING_EMAIL,
        description="The staged (not-yet-confirmed) new email, echoed back (DD-6)",
    )


class AccountRemovalResponseSchema(StatusMessageResponseSchema):
    """Response for the self-service account-removal / session-revocation
    endpoints (``DELETE /users/<id>`` and
    ``POST /users/<id>/logout-everywhere``).

    Carries ``status``/``message`` (banner text is server-sourced off
    ``message``) plus a ``redirect_url`` (mirroring ``LoginRedirectResponseSchema``)
    so the client navigates to splash after the acting session is logged out.
    Shared by the delete and logout-everywhere flows (and the OAuth-proof
    round-trip initiator, which returns the provider-redirect URL in the same
    field).
    """

    redirect_url: str = Field(
        alias=REDIRECT_URL,
        description="URL to navigate to after the acting session is logged out",
    )


class RegisterResponseSchema(StatusMessageResponseSchema):
    pass


class ForgotPasswordResponseSchema(StatusMessageResponseSchema):
    pass


class ResetPasswordResponseSchema(StatusMessageResponseSchema):
    pass


class EmailValidationResponseSchema(StatusMessageResponseSchema):
    pass
