from datetime import datetime

from src import db
from src.utils.constants import EMAIL_CONSTANTS


class Email_Validations(db.Model):
    """Class represents an Email Validation row - users are required to have their emails confirmed before accessing the site"""

    __tablename__ = "EmailValidations"
    id: int = db.Column(db.Integer, primary_key=True)
    user_id: int = db.Column(db.Integer, db.ForeignKey("Users.id"), unique=True)
    confirm_url: int = db.Column(db.String(2000), nullable=False, default="")
    is_validated: bool = db.Column(db.Boolean, default=False)
    attempts: int = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_attempt = db.Column(db.DateTime, nullable=True, default=None)
    validated_at = db.Column(db.DateTime, nullable=True, default=None)

    user = db.relationship("Users", back_populates="email_confirm")

    def __init__(self, confirm_url: str):
        self.confirm_url = confirm_url

    def validate(self):
        self.is_validated = True
        self.validated_at = datetime.utcnow()

    def increment_attempt(self) -> bool:
        if (
            self.last_attempt is not None
            and (datetime.utcnow() - self.last_attempt).seconds
            <= EMAIL_CONSTANTS.WAIT_TO_RETRY_BEFORE_MAX_ATTEMPTS
        ):
            return False

        self.last_attempt = datetime.utcnow()
        self.attempts += 1
        return True

    def check_if_too_many_attempts(self) -> bool:
        if (
            self.last_attempt is None
            or self.attempts < EMAIL_CONSTANTS.MAX_EMAIL_ATTEMPTS_IN_HOUR
        ):
            return False

        if self.attempts >= EMAIL_CONSTANTS.MAX_EMAIL_ATTEMPTS_IN_HOUR:
            if (
                datetime.utcnow() - self.last_attempt
            ).seconds >= EMAIL_CONSTANTS.WAIT_TO_ATTEMPT_AFTER_MAX_ATTEMPTS:
                self.attempts = 0

            else:
                return True

        return False

    def reset_attempts(self):
        self.last_attempt = None
        self.attempts = 0
