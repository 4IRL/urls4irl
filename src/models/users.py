from datetime import datetime
from enum import Enum

import jwt
from flask_login import UserMixin
from flask import current_app
from sqlalchemy import Column, DateTime, Enum as SQLEnum, Integer, String
from werkzeug.security import check_password_hash, generate_password_hash

from src import db
from src.models.email_validations import Email_Validations
from src.models.forgot_passwords import Forgot_Passwords
from src.models.utub_members import Utub_Members
from src.utils.constants import EMAIL_CONSTANTS, USER_CONSTANTS
from src.utils.datetime_utils import utc_now
from src.utils.strings.config_strs import CONFIG_ENVS
from src.utils.strings.email_validation_strs import EMAILS
from src.utils.strings.model_strs import MODELS as MODEL_STRS
from src.utils.strings.reset_password_strs import RESET_PASSWORD


class User_Role(Enum):
    ADMIN = "admin"
    USER = "user"
    MOD = "mod"


class Users(db.Model, UserMixin):
    """Class represents a User, with their username, email, and hashed password."""

    # TODO - Ensure if user signs in with Oauth, their username is local part of their email
    # TODO - Verify that username is less than length of max username, else add numbers to end up to 99999
    # TODO - Verify email cannot be used as password

    __tablename__ = "Users"
    id: int = Column(Integer, primary_key=True)
    username: str = Column(
        String(USER_CONSTANTS.MAX_USERNAME_LENGTH), unique=True, nullable=False
    )
    email: str = Column(String(120), unique=True, nullable=False)
    password: str = Column(String(166), nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, default=utc_now, name="createdAt"
    )
    role: str = Column(SQLEnum(User_Role), nullable=False, default=User_Role.USER)
    utubs_is_member_of: list[Utub_Members] = db.relationship(
        "Utub_Members", back_populates="to_user"
    )
    email_confirm: Email_Validations = db.relationship(
        "Email_Validations", uselist=False, back_populates="user"
    )
    forgot_password: Forgot_Passwords = db.relationship(
        "Forgot_Passwords", uselist=False, back_populates="user"
    )

    def __init__(
        self,
        username: str,
        email: str,
        plaintext_password: str,
    ):
        """
        Create new user object per the following parameters

        Args:
            username (str): Username from user input
            email (str): Email from user input
            plaintext_password (str): Plaintext password to be hashed
        """
        self.username = username
        self.email: str = email.lower()
        self.password = generate_password_hash(plaintext_password)
        self._email_confirmed = False

    def is_password_correct(self, plaintext_password: str) -> bool:
        return check_password_hash(self.password, plaintext_password)

    def is_email_authenticated(self) -> bool:
        email_confirm: Email_Validations = self.email_confirm
        return email_confirm.is_validated

    def change_password(self, new_plaintext_password: str):
        self.password = generate_password_hash(new_plaintext_password)

    @property
    def serialized(self) -> dict[str, int | str]:
        """Return object in serialized form."""
        return {
            MODEL_STRS.ID: self.id,
            MODEL_STRS.USERNAME: self.username,
        }

    @property
    def serialized_on_initial_load(self) -> list[dict]:
        """Returns object in serialized for, with only the utub id and Utub name the user is a member of."""
        utubs_for_user = []
        for utub_member_relationship in self.utubs_is_member_of:
            utubs_for_user.append(utub_member_relationship.serialized_on_initial_load)

        return utubs_for_user

    def __repr__(self):
        return f"User: {self.username}, Email: {self.email}, Password: {self.password}"

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
