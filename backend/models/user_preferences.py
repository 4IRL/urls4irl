from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Column,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    UniqueConstraint,
)

from backend import db
from backend.utils.datetime_utils import utc_now

if TYPE_CHECKING:
    from backend.models.users import Users


class Theme(Enum):
    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"


class ViewMode(Enum):
    LIST = "list"
    COMPACT = "compact"
    CARDS = "cards"


class SortOrder(Enum):
    NEWEST = "newest"
    OLDEST = "oldest"
    TITLE_AZ = "title_az"


class Density(Enum):
    COMFORTABLE = "comfortable"
    COMPACT = "compact"


class DateFormat(Enum):
    ISO = "iso"
    US = "us"
    EU = "eu"


class User_Preferences(db.Model):
    """A user's display and view preferences, one-to-one with a Users account.

    Child of Users: each Users row owns at most one preferences row (enforced by
    the ``unique=True`` foreign key on ``userID``), created lazily the first time
    the user saves a display/view preference through the Settings Display tab.
    Pre-existing users have no row until they first save; every consumer defaults
    each field to its enum default (theme ``SYSTEM``, view ``LIST``, sort
    ``NEWEST``, density ``COMFORTABLE``, date format ``ISO``) when the row is
    absent, so the missing-row state is always well-defined.

    Each enum column stores the lowercase ``.value`` string of its Python enum
    (via ``values_callable``), and every column carries an explicit ``name=``
    physical (camelCase) column name matched by the Alembic migration and by the
    named Postgres enum TYPEs it creates.
    """

    __tablename__ = "UserPreferences"
    __table_args__ = (UniqueConstraint("userID", name="unique_user_preferences"),)

    id: int = Column(Integer, primary_key=True)
    # 1:1-ness is enforced by the named ``unique_user_preferences`` constraint in
    # ``__table_args__`` (mirroring the UserOAuthIdentity template's named
    # constraints) rather than a column-level ``unique=True``, so the model and
    # the Alembic migration produce exactly one identically-named constraint.
    user_id: int = Column(
        Integer,
        ForeignKey("Users.id", ondelete="CASCADE"),
        nullable=False,
        name="userID",
    )
    theme: Theme = Column(
        SQLEnum(
            Theme,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
            name="theme_enum",
        ),
        nullable=False,
        default=Theme.SYSTEM,
        name="theme",
    )
    default_view: ViewMode = Column(
        SQLEnum(
            ViewMode,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
            name="view_mode_enum",
        ),
        nullable=False,
        default=ViewMode.LIST,
        name="defaultView",
    )
    default_sort: SortOrder = Column(
        SQLEnum(
            SortOrder,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
            name="sort_order_enum",
        ),
        nullable=False,
        default=SortOrder.NEWEST,
        name="defaultSort",
    )
    density: Density = Column(
        SQLEnum(
            Density,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
            name="density_enum",
        ),
        nullable=False,
        default=Density.COMFORTABLE,
        name="density",
    )
    date_format: DateFormat = Column(
        SQLEnum(
            DateFormat,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
            name="date_format_enum",
        ),
        nullable=False,
        default=DateFormat.ISO,
        name="dateFormat",
    )
    created_at: datetime = Column(
        DateTime(timezone=True), nullable=False, default=utc_now, name="createdAt"
    )
    updated_at: datetime = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        name="updatedAt",
    )

    user: Users = db.relationship("Users", back_populates="preferences")


@dataclass(frozen=True)
class ResolvedPreferences:
    """The five display/view preference values resolved to concrete enum
    members, with the missing-row (pre-existing user) defaults already applied.

    Every consumer of a user's preferences reads through
    ``resolve_preferences()`` so the per-field enum defaults (theme ``SYSTEM``,
    view ``LIST``, sort ``NEWEST``, density ``COMFORTABLE``, date format ``ISO``)
    live in exactly one place. Fields hold enum members (not their ``.value``
    strings) so callers can compare enums directly or read ``.value`` as needed.
    """

    theme: Theme
    default_view: ViewMode
    default_sort: SortOrder
    density: Density
    date_format: DateFormat


def resolve_preferences(row: User_Preferences | None) -> ResolvedPreferences:
    """Resolve a (possibly missing) ``UserPreferences`` row to its five concrete
    preference values, applying each field's enum default when ``row`` is
    ``None`` (a pre-existing user who has never saved a preference).

    This is the single source of truth for the missing-row defaults; the model's
    per-column ``default=`` values above define the same defaults for freshly
    persisted rows, and this resolver mirrors them for the not-yet-persisted
    case.
    """
    if row is None:
        return ResolvedPreferences(
            theme=Theme.SYSTEM,
            default_view=ViewMode.LIST,
            default_sort=SortOrder.NEWEST,
            density=Density.COMFORTABLE,
            date_format=DateFormat.ISO,
        )
    return ResolvedPreferences(
        theme=row.theme,
        default_view=row.default_view,
        default_sort=row.default_sort,
        density=row.density,
        date_format=row.date_format,
    )
