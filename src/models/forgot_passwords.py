from __future__ import annotations
from datetime import datetime

from src import db
from src.utils.constants import USER_CONSTANTS


class Forgot_Passwords(db.Model):
    __tablename__ = "ForgotPasswords"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("Users.id"))
    reset_token = db.Column(db.String(2000), nullable=False, default="")
    attempts = db.Column(db.Integer, nullable=False, default=0)
    initial_attempt = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_attempt = db.Column(db.DateTime, nullable=True, default=None)

    user = db.relationship("Users", back_populates="forgot_password")

    def __init__(self, reset_token: str):
        self.reset_token = reset_token

    def increment_attempts(self):
        self.attempts += 1
        self.last_attempt = datetime.utcnow()

    def is_more_than_hour_old(self) -> bool:
        return (
            datetime.utcnow() - self.initial_attempt
        ).seconds >= USER_CONSTANTS.WAIT_TO_RETRY_FORGOT_PASSWORD_MAX

    def is_not_rate_limited(self) -> bool:
        is_more_than_five_attempts_in_one_hour = (
            self.attempts >= USER_CONSTANTS.PASSWORD_RESET_ATTEMPTS
        )
        if is_more_than_five_attempts_in_one_hour:
            # User won't be able to send more than 5 requests in one hour
            return False

        if (
            self.last_attempt is not None
            and (datetime.utcnow() - self.last_attempt).seconds
            < USER_CONSTANTS.WAIT_TO_RETRY_FORGOT_PASSWORD_MIN
        ):
            # Cannot perform more than two requests per minute
            return False

        return True
