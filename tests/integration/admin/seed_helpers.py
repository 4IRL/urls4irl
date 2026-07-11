from __future__ import annotations

from backend import db
from backend.metrics.events import EventCategory
from backend.models.event_registry import Event_Registry
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utubs import Utubs

_SEEDED_UTUB_NAME: str = "Browser Test UTub"
_SEEDED_EVENT_REGISTRY_DESCRIPTION: str = "Seeded for the DB-browser string-PK test."


def seed_utub_member(user_id: int) -> Utub_Members:
    """Create a UTub owned by ``user_id`` and add them as a member (composite PK)."""
    new_utub = Utubs(
        name=_SEEDED_UTUB_NAME,
        utub_creator=user_id,
        utub_description="",
    )
    db.session.add(new_utub)
    db.session.commit()
    utub_member = Utub_Members(
        utub_id=new_utub.id,
        user_id=user_id,
        member_role=Member_Role.CREATOR,
    )
    db.session.add(utub_member)
    db.session.commit()
    return utub_member


def seed_event_registry_row(*, name: str) -> Event_Registry:
    """Insert one EventRegistry row (String primary key = ``name``)."""
    event_row = Event_Registry(
        name=name,
        category=EventCategory.DOMAIN,
        description=_SEEDED_EVENT_REGISTRY_DESCRIPTION,
    )
    db.session.add(event_row)
    db.session.commit()
    return event_row
