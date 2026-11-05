from datetime import timedelta
from enum import IntEnum, StrEnum
from typing import Final

# secrets.token_urlsafe(16): 128 bits of randomness, 22 base64url characters.
INVITE_LINK_TOKEN_BYTES: int = 16
INVITE_LINK_TOKEN_LENGTH: int = 22
INVITE_LINK_TOKEN_PATTERN: str = rf"^[A-Za-z0-9_-]{{{INVITE_LINK_TOKEN_LENGTH}}}\Z"
INVITE_LINK_DEFAULT_TTL: timedelta = timedelta(days=7)

# DD-5 closed sets; the request schema Literals must mirror these exactly.
INVITE_LINK_EXPIRY_DAYS_VALUES: tuple[int, ...] = (1, 7, 30)
INVITE_LINK_MAX_USES_VALUES: tuple[int, ...] = (1, 5, 10, 25)
INVITE_LINK_MANAGE_RATE_LIMIT: str = "30 per minute"
# One shared bucket for web and mobile create/replace, per manager.
INVITE_LINK_MANAGE_RATE_SCOPE: str = "invite_link_manage"
INVITE_LINK_PAGE_RATE_LIMIT: Final = "60 per minute"
INVITE_LINK_JOIN_RATE_LIMIT: str = "10 per minute"
INVITE_LINK_JOIN_RATE_SCOPE: str = "invite_link_join"
INVITE_LINK_TOKEN_MAX_ATTEMPTS: int = 5

# Metric dimension closed sets (DD-15).
INVITE_LINK_METRIC_HAS_USE_LIMIT_VALUES: tuple[str, ...] = ("true", "false")
INVITE_LINK_METRIC_REVOKE_REASONS: tuple[str, ...] = (
    "manual",
    "replaced",
    "dead_on_create",
    "role_change",
)

UNIQUE_INVITE_LINK_TOKEN: str = "unique_utub_invite_link_token"
ONE_ACTIVE_INVITE_LINK_PER_UTUB: str = "uq_utub_invite_links_one_active_per_utub"
FK_EMAIL_VALIDATIONS_PENDING_INVITE: str = "fk_email_validations_pending_invite"
FK_INVITE_ACCEPTANCES_INVITE: str = "fk_utub_invite_acceptances_invite"
FK_INVITE_ACCEPTANCES_UTUB: str = "fk_utub_invite_acceptances_utub"
FK_INVITE_ACCEPTANCES_USER: str = "fk_utub_invite_acceptances_user"
IX_INVITE_ACCEPTANCES_INVITE: str = "ix_utub_invite_acceptances_invite_id"


class InviteState(StrEnum):
    LIVE = "live"
    REVOKED = "revoked"
    EXPIRED = "expired"
    USED_UP = "used_up"
    # NULL creator, not a member, or demoted
    CREATOR_NOT_MANAGER = "creator_not_manager"
    UTUB_TRASHED = "utub_trashed"
    UTUB_LOCKED = "utub_locked"


class InviteLinkStatus(StrEnum):
    LIVE = "live"
    EXPIRED = "expired"
    USED_UP = "used_up"
    CREATOR_DEMOTED = "creator_demoted"


class InviteLinkErrorCodes(IntEnum):
    INVITE_LINK_NOT_FOUND = 1  # 404, no unrevoked link
    INVALID_FORM_INPUT = 2  # 400
    UTUB_IS_LOCKED = 3  # 403
    LIVE_LINK_EXISTS = 4  # 409 on create
    DEAD_LINK_UPDATE = 5  # 409 on update
    USES_BELOW_JOINED = 6  # 400 on update


class InviteJoinOutcome(StrEnum):
    JOINED = "joined"
    ALREADY_MEMBER = "already_member"
    DEAD = "dead"
    ACTOR_UNVALIDATED = "actor_unvalidated"
    ACTOR_SUSPENDED = "actor_suspended"
