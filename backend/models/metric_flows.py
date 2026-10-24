from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from backend import db
from backend.metrics.flow_limits import FLOW_LIMITS
from backend.utils.datetime_utils import utc_now

DISPLAY_NAME_LOWER_INDEX = "uq_metric_flows_display_name_lower"
DISPLAY_NAME_TRIMMED_CHECK = "ck_metric_flows_display_name_trimmed"
DEFINITION_STEPS_ARRAY_CHECK = "ck_metric_flows_definition_steps_array"

# The migration uses these identical texts. ``coalesce`` is required: the
# ``jsonb_typeof`` of a missing key is NULL, and a CHECK evaluating to NULL passes.
DISPLAY_NAME_TRIMMED_SQL = (
    '"displayName" = btrim("displayName") AND char_length("displayName") > 0'
)
DEFINITION_STEPS_ARRAY_SQL = (
    "coalesce(jsonb_typeof(definition -> 'steps'), '') = 'array'"
)


class Metric_Flows(db.Model):
    """An admin-created metric funnel.

    ``definition`` holds the ``{"steps": [...]}`` envelope. ``displayName`` is
    unique regardless of case (Postgres ``lower()`` only, no Unicode folding) and
    must be trimmed and non-empty. ``createdBy``/``updatedBy`` are nulled if the
    referenced user is deleted.
    """

    __tablename__ = "MetricFlows"
    __table_args__ = (
        Index(DISPLAY_NAME_LOWER_INDEX, text('lower("displayName")'), unique=True),
        CheckConstraint(DISPLAY_NAME_TRIMMED_SQL, name=DISPLAY_NAME_TRIMMED_CHECK),
        CheckConstraint(DEFINITION_STEPS_ARRAY_SQL, name=DEFINITION_STEPS_ARRAY_CHECK),
    )

    id: int = Column(Integer, primary_key=True)
    display_name: str = Column(
        String(FLOW_LIMITS.NAME_MAX_LENGTH), nullable=False, name="displayName"
    )
    definition: dict[str, Any] = Column(JSONB, nullable=False)
    created_by: int | None = Column(
        Integer,
        ForeignKey("Users.id", ondelete="SET NULL"),
        nullable=True,
        name="createdBy",
    )
    updated_by: int | None = Column(
        Integer,
        ForeignKey("Users.id", ondelete="SET NULL"),
        nullable=True,
        name="updatedBy",
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

    def __init__(
        self,
        *,
        display_name: str,
        definition: dict[str, Any],
        created_by: int | None,
        updated_by: int | None,
    ) -> None:
        self.display_name = display_name
        self.definition = definition
        self.created_by = created_by
        self.updated_by = updated_by
