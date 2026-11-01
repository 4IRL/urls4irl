from datetime import timedelta

# secrets.token_urlsafe(16): 128 bits of randomness, 22 base64url characters.
INVITE_LINK_TOKEN_BYTES: int = 16
INVITE_LINK_TOKEN_LENGTH: int = 22
INVITE_LINK_TOKEN_PATTERN: str = rf"^[A-Za-z0-9_-]{{{INVITE_LINK_TOKEN_LENGTH}}}\Z"
INVITE_LINK_DEFAULT_TTL: timedelta = timedelta(days=7)

UNIQUE_INVITE_LINK_TOKEN: str = "unique_utub_invite_link_token"
ONE_ACTIVE_INVITE_LINK_PER_UTUB: str = "uq_utub_invite_links_one_active_per_utub"
FK_EMAIL_VALIDATIONS_PENDING_INVITE: str = "fk_email_validations_pending_invite"
FK_INVITE_ACCEPTANCES_INVITE: str = "fk_utub_invite_acceptances_invite"
FK_INVITE_ACCEPTANCES_UTUB: str = "fk_utub_invite_acceptances_utub"
FK_INVITE_ACCEPTANCES_USER: str = "fk_utub_invite_acceptances_user"
IX_INVITE_ACCEPTANCES_INVITE: str = "ix_utub_invite_acceptances_invite_id"
