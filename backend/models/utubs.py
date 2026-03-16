from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from backend import db
from backend.models.utub_members import Utub_Members
from backend.models.utub_urls import Utub_Urls
from backend.models.utub_tags import Utub_Tags
from backend.utils.constants import UTUB_CONSTANTS
from backend.utils.datetime_utils import utc_now


class Utubs(db.Model):
    """Class represents a UTub. A UTub is created by a specific user, but has read-update access given to other users depending on who it
    is shared with. The UTub contains a set of URL's and their associated tags."""

    __tablename__ = "Utubs"
    id: int = Column(Integer, primary_key=True)
    name: str = Column(
        String(UTUB_CONSTANTS.MAX_NAME_LENGTH), nullable=False, name="utubName"
    )  # Note that multiple UTubs can have the same name, maybe verify this per user?
    utub_creator: int = Column(
        Integer, ForeignKey("Users.id"), nullable=False, name="utubCreator"
    )
    created_at: datetime = Column(
        DateTime(timezone=True), nullable=False, default=utc_now, name="createdAt"
    )
    last_updated: datetime = Column(
        DateTime(timezone=True), nullable=False, default=utc_now, name="lastUpdated"
    )
    utub_description: str = Column(
        String(UTUB_CONSTANTS.MAX_DESCRIPTION_LENGTH),
        nullable=True,
        name="utubDescription",
    )
    utub_tags: list[Utub_Tags] = db.relationship(
        "Utub_Tags", cascade="all, delete, delete-orphan", passive_deletes=True
    )
    utub_url_tags = db.relationship(
        "Utub_Url_Tags",
        back_populates="utub_containing_this_url_tag",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    utub_urls: list[Utub_Urls] = db.relationship(
        "Utub_Urls", cascade="all, delete, delete-orphan", passive_deletes=True
    )
    members: list[Utub_Members] = db.relationship(
        "Utub_Members", back_populates="to_utub", cascade="all, delete, delete-orphan"
    )

    def __init__(self, name: str, utub_creator: int, utub_description: str):
        self.name = name
        self.utub_creator = utub_creator
        self.utub_description = utub_description

    def set_last_updated(self):
        self.last_updated = utc_now()
