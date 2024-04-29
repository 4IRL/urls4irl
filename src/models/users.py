from datetime import datetime

import jwt
from flask_login import UserMixin
from flask import current_app
from werkzeug.security import check_password_hash, generate_password_hash

from src import db
from src.models.email_validations import Email_Validations
from src.utils.constants import EMAIL_CONSTANTS, USER_CONSTANTS
from src.utils.strings.config_strs import CONFIG_ENVS
from src.utils.strings.email_validation_strs import EMAILS
from src.utils.strings.model_strs import MODELS as MODEL_STRS
from src.utils.strings.reset_password_strs import RESET_PASSWORD


class Users(db.Model, UserMixin):
    """Class represents a User, with their username, email, and hashed password."""

    # TODO - Ensure if user signs in with Oauth, their username is local part of their email
    # TODO - Verify that username is less than length of max username, else add numbers to end up to 99999
    # TODO - Verify email cannot be used as password

    __tablename__ = "Users"
    id: int = db.Column(db.Integer, primary_key=True)
    username: str = db.Column(
        db.String(USER_CONSTANTS.MAX_USERNAME_LENGTH), unique=True, nullable=False
    )
    email: str = db.Column(db.String(120), unique=True, nullable=False)
    password: str = db.Column(db.String(166), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    utubs_created = db.relationship("Utubs", backref="created_by", lazy=True)
    utub_urls = db.relationship("Utub_Urls", back_populates="user_that_added_url")
    utubs_is_member_of = db.relationship("Utub_Members", back_populates="to_user")
    email_confirm: Email_Validations = db.relationship(
        "Email_Validations", uselist=False, back_populates="user"
    )
    forgot_password = db.relationship(
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
        return self.email_confirm.is_validated

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
        for utub in self.utubs_is_member_of:
            utubs_for_user.append(utub.serialized_on_initial_load)

        return utubs_for_user

    def __repr__(self):
        return f"User: {self.username}, Email: {self.email}, Password: {self.password}"

    def get_email_validation_token(
        self, expires_in=EMAIL_CONSTANTS.WAIT_TO_ATTEMPT_AFTER_MAX_ATTEMPTS
    ) -> str:
        return jwt.encode(
            payload={
                EMAILS.VALIDATE_EMAIL: self.username,
                EMAILS.EXPIRATION: datetime.timestamp(datetime.now()) + expires_in,
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
                RESET_PASSWORD.EXPIRATION: datetime.timestamp(datetime.now())
                + expires_in,
            },
            key=current_app.config[CONFIG_ENVS.SECRET_KEY],
        )
