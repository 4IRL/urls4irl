from __future__ import annotations
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from src import db
from src.utils.constants import USER_CONSTANTS
from src.utils.datetime_utils import utc_now


class Forgot_Passwords(db.Model):
    __tablename__ = "ForgotPasswords"
    id: int = Column(Integer, primary_key=True)
    user_id: int = Column(Integer, ForeignKey("Users.id"))
    reset_token: String = Column(String(2000), nullable=False, default="")
    attempts: int = Column(Integer, nullable=False, default=0)
    initial_attempt: datetime = Column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    last_attempt: datetime | None = Column(
        DateTime(timezone=True), nullable=True, default=None
    )

    user = db.relationship("Users", back_populates="forgot_password")

    def __init__(self, reset_token: str):
        self.reset_token = reset_token

    def increment_attempts(self):
        self.attempts += 1
        self.last_attempt = utc_now()

    def is_more_than_hour_old(self) -> bool:
        return (
            utc_now() - self.initial_attempt
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
            and (utc_now() - self.last_attempt).seconds
            < USER_CONSTANTS.WAIT_TO_RETRY_FORGOT_PASSWORD_MIN
        ):
            # Cannot perform more than two requests per minute
            return False

        return True
