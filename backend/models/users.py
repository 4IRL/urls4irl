from __future__ import annotations

from datetime import datetime
from enum import Enum

import jwt
from flask_login import UserMixin
from flask import current_app
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    Integer,
    String,
    text,
)
from werkzeug.security import check_password_hash, generate_password_hash

from backend import db
from backend.models.email_validations import Email_Validations
from backend.models.forgot_passwords import Forgot_Passwords
from backend.models.user_oauth_identities import UserOAuthIdentity
from backend.models.user_preferences import User_Preferences
from backend.models.utub_members import Utub_Members
from backend.utils.constants import EMAIL_CONSTANTS, USER_CONSTANTS
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.config_strs import CONFIG_ENVS
from backend.utils.strings.email_validation_strs import EMAILS
from backend.utils.strings.reset_password_strs import RESET_PASSWORD


class User_Role(Enum):
    ADMIN = "admin"
    USER = "user"
    MOD = "mod"


class Users(db.Model, UserMixin):
    """Class represents a User, with their username, email, and hashed password."""

    # TODO - Verify email cannot be used as password

    __tablename__ = "Users"
    id: int = Column(Integer, primary_key=True)
    username: str = Column(
        String(USER_CONSTANTS.MAX_USERNAME_LENGTH_ACTUAL), unique=True, nullable=False
    )
    email: str = Column(
        String(USER_CONSTANTS.MAX_EMAIL_LENGTH), unique=True, nullable=False
    )
    # Not-yet-confirmed new email for the Settings "change email" flow. The user
    # stays logged in on their existing (still-verified) ``email`` until they
    # click the confirmation link, at which point ``finalize_email_change``
    # swaps this into ``email``. None means no email change is in flight.
    pending_email: str | None = Column(
        String(USER_CONSTANTS.MAX_EMAIL_LENGTH),
        nullable=True,
        default=None,
        name="pendingEmail",
    )
    password: str | None = Column(
        String(USER_CONSTANTS.MAX_PASSWORD_LENGTH), nullable=True
    )
    created_at = Column(
        DateTime(timezone=True), nullable=False, default=utc_now, name="createdAt"
    )
    role: str = Column(SQLEnum(User_Role), nullable=False, default=User_Role.USER)
    email_validated: bool = Column(
        Boolean, default=False, name="emailValidated", nullable=False
    )
    is_suspended: bool = Column(
        Boolean,
        default=False,
        server_default=text("false"),
        name="isSuspended",
        nullable=False,
    )
    # Sessions issued (web) before this timestamp are rejected by the
    # user_loader; None means no invalidation has ever been requested.
    sessions_invalidated_at: datetime | None = Column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        name="sessionsInvalidatedAt",
    )
    utubs_is_member_of: list[Utub_Members] = db.relationship(
        "Utub_Members", back_populates="to_user"
    )
    email_confirm: Email_Validations = db.relationship(
        "Email_Validations", uselist=False, back_populates="user"
    )
    forgot_password: Forgot_Passwords = db.relationship(
        "Forgot_Passwords", uselist=False, back_populates="user"
    )
    # Default lazy="select" (not "selectin"): selectin would fire a companion
    # SELECT against UserOAuthIdentities on *every* Users query, which breaks
    # any code path running against a migration revision before that table
    # exists (e.g. the pre-strip-revision seed in the migration roundtrip
    # tests). Identities are loaded on access, which is all Phase 1 needs;
    # a future hot path can opt in per-query via selectinload(...).
    oauth_identities: list[UserOAuthIdentity] = db.relationship(
        "UserOAuthIdentity",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select",
    )
    # Default lazy="select" (not eager): the migration-roundtrip tests run
    # Users queries against a schema revision *before* the UserPreferences table
    # exists; an eager join would break them. Preferences are loaded on access,
    # which is all any preference read path needs.
    preferences: User_Preferences = db.relationship(
        "User_Preferences",
        uselist=False,
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __init__(
        self,
        username: str,
        email: str,
        *,
        plaintext_password: str | None = None,
    ) -> None:
        """
        Create new user object per the following parameters

        Args:
            username (str): Username from user input
            email (str): Email from user input
            plaintext_password (str | None): Plaintext password to be hashed;
                None for OAuth-only accounts that never set a local password
        """
        self.username = username
        self.email: str = email.lower()
        self.password = (
            generate_password_hash(plaintext_password)
            if plaintext_password is not None
            else None
        )
        self._email_confirmed = False

    def is_password_correct(self, plaintext_password: str) -> bool:
        if self.password is None:
            return False
        return check_password_hash(self.password, plaintext_password)

    def is_admin(self) -> bool:
        return self.role == User_Role.ADMIN

    def change_password(self, new_plaintext_password: str):
        self.password = generate_password_hash(new_plaintext_password)

    def validate_email(self):
        self.email_validated = True

    def stage_email_change(self, new_email: str) -> None:
        """Stash a not-yet-confirmed new email (lowercased on store).

        Assumes the caller has already format-validated and uniqueness-checked
        ``new_email``. The live ``email`` is untouched until confirmation.
        """
        self.pending_email = new_email.lower()

    def finalize_email_change(self) -> None:
        """Swap the confirmed pending email into the live ``email`` column.

        Only called inside the confirm route's ``IntegrityError`` guard, after
        a final uniqueness re-check. Clears ``pending_email`` so a replayed
        token finds nothing pending and no-ops.
        """
        self.email = self.pending_email
        self.pending_email = None

    def __repr__(self):
        return f"User: {self.username}"

    def get_email_validation_token(
        self, expires_in=EMAIL_CONSTANTS.WAIT_TO_ATTEMPT_AFTER_MAX_ATTEMPTS
    ) -> str:
        return jwt.encode(
            payload={
                EMAILS.VALIDATE_EMAIL: self.username,
                EMAILS.EXPIRATION: datetime.timestamp(utc_now()) + expires_in,
            },
            key=current_app.config[CONFIG_ENVS.SECRET_KEY],
            algorithm=EMAILS.ALGORITHM,
        )

    def get_email_change_token(
        self, expires_in=EMAIL_CONSTANTS.WAIT_TO_ATTEMPT_AFTER_MAX_ATTEMPTS
    ) -> str:
        return jwt.encode(
            payload={
                EMAILS.CHANGE_EMAIL: self.username,
                EMAILS.CHANGE_EMAIL_TARGET: self.pending_email,
                EMAILS.EXPIRATION: datetime.timestamp(utc_now()) + expires_in,
            },
            key=current_app.config[CONFIG_ENVS.SECRET_KEY],
            algorithm=EMAILS.ALGORITHM,
        )

    def get_password_reset_token(
        self, expires_in=USER_CONSTANTS.WAIT_TO_RETRY_FORGOT_PASSWORD_MAX
    ) -> str:
        return jwt.encode(
            payload={
                RESET_PASSWORD.RESET_PASSWORD_KEY: self.username,
                RESET_PASSWORD.EXPIRATION: datetime.timestamp(utc_now()) + expires_in,
            },
            key=current_app.config[CONFIG_ENVS.SECRET_KEY],
        )
