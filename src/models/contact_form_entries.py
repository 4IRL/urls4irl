from datetime import datetime
import hashlib

from flask_login import current_user
from ua_parser import parse
from ua_parser.core import OS, Device, UserAgent
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String

from src import db
from src.contact.constants import CONTACT_FORM_CONSTANTS
from src.utils.datetime_utils import utc_now


class ContactFormEntries(db.Model):
    """Class represents a Contact Us form entry, with associated data to understand the User's device when they made the entry..

    Fields
    user id if not anonymous else null
    Subject field
    Content field
    Created_at
    Last_attempt
    delivered
    case_id (default null, auto increment, set to pk to lock it in)
    user-agent hashed to check repeats
    Device
    Browser
    Browser version
    OS

    """

    __tablename__ = "ContactFormEntries"
    id: int = Column(Integer, primary_key=True)
    user_id: int | None = Column(
        Integer, ForeignKey("Users.id"), nullable=True, name="userID"
    )
    subject: str = Column(
        String(CONTACT_FORM_CONSTANTS.MAX_SUBJECT_LENGTH),
        nullable=False,
        name="subject",
    )
    content: str = Column(
        String(CONTACT_FORM_CONSTANTS.MAX_CONTENT_LENGTH),
        nullable=False,
        name="content",
    )
    created_at: datetime = Column(
        DateTime(timezone=True), nullable=False, default=utc_now, name="createdAt"
    )
    last_delivery_attempt: datetime = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        name="lastDeliveryAttempt",
    )
    delivered: bool = Column(Boolean, default=False, name="delivered", nullable=False)
    user_agent_hash = Column(String(64), nullable=False, name="userAgentHash")
    browser = Column(String(100), nullable=True, name="browser")
    browser_version = Column(String(50), nullable=True, name="browserVersion")
    os = Column(String(100), nullable=True, name="os")
    device = Column(String(100), nullable=True, name="device")

    def __init__(self, subject: str, content: str, user_agent: str) -> None:
        self.subject = subject
        self.content = content

        parsed_user_agent = parse(user_agent)

        self.device = self._get_device(parsed_user_agent.device)

        self.browser = self._get_browser(parsed_user_agent.user_agent)
        self.browser_version = self._get_browser_version(parsed_user_agent.user_agent)

        self.os = self._get_os(parsed_user_agent.os)
        self.user_agent_hash = hashlib.sha256(user_agent.encode("utf-8")).hexdigest()
        self.user_id = self._get_current_user_id()

    def _get_device(self, device: Device | None) -> str | None:
        if device is None or not isinstance(device.family, str):
            return None

        return device.family.lower()

    def _get_version_part(self, val: str | None) -> str:
        return val if val is not None else "0"

    def _get_browser(self, browser: UserAgent | None) -> str | None:
        if browser is None or not isinstance(browser.family, str):
            return None

        return browser.family.lower()

    def _get_browser_version(self, browser: UserAgent | None) -> str | None:
        if browser is None or not isinstance(browser.major, str):
            return None

        major = self._get_version_part(browser.major)
        minor = self._get_version_part(browser.minor)

        # User Agents have been updated for privacy - so only take major and minor for browser
        # https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/User-Agent#user-agent_reduction
        return f"{major}.{minor}"

    def _get_os(self, os: OS | None) -> str | None:
        if os is None or not isinstance(os.family, str):
            return None

        if not isinstance(os.major, str):
            return os.family

        major = self._get_version_part(os.major)
        minor = self._get_version_part(os.minor)

        return f"{os.family} {major}.{minor}"

    @staticmethod
    def _get_current_user_id() -> int | None:
        if (
            current_user is None
            or not hasattr(current_user, "get_id")
            or current_user.get_id() is None
        ):
            return None

        current_user_id = current_user.get_id()
        if not isinstance(current_user_id, str):
            return None

        user_id = None
        try:
            user_id = int(current_user_id) if current_user_id.isnumeric() else None

        except ValueError:
            return None

        return user_id
