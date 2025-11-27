from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String

from src import db
from src.utils.constants import EMAIL_CONSTANTS
from src.utils.datetime_utils import utc_now


class Email_Validations(db.Model):
    """Class represents an Email Validation row - users are required to have their emails confirmed before accessing the site"""

    __tablename__ = "EmailValidations"
    id: int = Column(Integer, primary_key=True)
    user_id: int = Column(Integer, ForeignKey("Users.id"), unique=True, name="userID")
    validation_token: str = Column(
        String(2000), nullable=False, default="", name="validationToken"
    )
    is_validated: bool = Column(Boolean, default=False, name="isValidated")
    attempts: int = Column(Integer, nullable=False, default=0)
    created_at: datetime = Column(
        DateTime(timezone=True), nullable=False, default=utc_now, name="createdAt"
    )
    last_attempt: datetime | None = Column(
        DateTime(timezone=True), nullable=True, default=None, name="lastAttempt"
    )

    user = db.relationship("Users", back_populates="email_confirm")

    def __init__(self, validation_token: str):
        self.validation_token = validation_token

    def validate(self):
        self.is_validated = True

    def increment_attempt(self) -> bool:
        if (
            self.last_attempt is not None
            and (utc_now() - self.last_attempt).seconds
            <= EMAIL_CONSTANTS.WAIT_TO_RETRY_BEFORE_MAX_ATTEMPTS
        ):
            return False

        self.last_attempt = utc_now()
        self.attempts += 1
        return True

    def has_too_many_email_attempts(self) -> bool:
        if (
            self.last_attempt is None
            or self.attempts < EMAIL_CONSTANTS.MAX_EMAIL_ATTEMPTS_IN_HOUR
        ):
            return False

        if self.attempts >= EMAIL_CONSTANTS.MAX_EMAIL_ATTEMPTS_IN_HOUR:
            if (
                utc_now() - self.last_attempt
            ).seconds >= EMAIL_CONSTANTS.WAIT_TO_ATTEMPT_AFTER_MAX_ATTEMPTS:
                self.attempts = 0

            else:
                return True

        return False

    def reset_attempts(self):
        self.last_attempt = None
        self.attempts = 0
