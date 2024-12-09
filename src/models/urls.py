from enum import Enum
from sqlalchemy import Column, DateTime, Enum as SQLEnum, ForeignKey, Integer, String

from src import db
from src.utils.datetime_utils import utc_now


class Possible_Url_Validation(Enum):
    VALIDATED = "valid"
    INVALIDATED = "invalid"
    UNKNOWN = "unknown"


class Urls(db.Model):
    """Class represents a URL. A URL is added by a single user, but can be used generically across multiple UTubs if it's already
    stored in the server."""

    __tablename__ = "Urls"
    id: int = Column(Integer, primary_key=True)
    url_string: str = Column(
        String(8000), nullable=False, unique=True, name="urlString"
    )  # Note that multiple UTubs can have the same URL
    is_validated: str = Column(
        SQLEnum(Possible_Url_Validation),
        nullable=False,
        default=Possible_Url_Validation.UNKNOWN,
        name="isValidated",
    )
    created_by: int = Column(
        Integer, ForeignKey("Users.id"), nullable=False, name="createdBy"
    )
    created_at = Column(
        DateTime(timezone=True), nullable=False, default=utc_now, name="createdAt"
    )

    def __init__(self, normalized_url: str, current_user_id: int):
        self.url_string = normalized_url
        self.created_by = int(current_user_id)
