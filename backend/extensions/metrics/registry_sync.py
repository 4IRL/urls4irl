from __future__ import annotations

from flask import Flask, current_app

from backend import db
from backend.metrics.events import EVENT_CATEGORY, EVENT_DESCRIPTIONS, EventName
from backend.models.event_registry import Event_Registry


def sync_event_registry(app: Flask) -> None:
    """Reconcile the `EventRegistry` table with the `EventName` Python enum.

    Inserts rows for enum members not yet present. Updates `category` and
    `description` for rows whose values drift from the Python source.
    Never deletes rows: historical `AnonymousMetrics` rows may still
    reference retired enum values via the FK.

    Idempotent. Safe to call on every container start (invoked by the
    `flask metrics sync-registry` CLI command from `docker/startup-flask.sh`).
    """
    with app.app_context():
        existing = {row.name: row for row in Event_Registry.query.all()}
        for member in EventName:
            expected_category = EVENT_CATEGORY[member]
            expected_description = EVENT_DESCRIPTIONS[member]
            row = existing.get(member.value)
            if row is None:
                db.session.add(
                    Event_Registry(
                        name=member.value,
                        category=expected_category,
                        description=expected_description,
                    )
                )
            else:
                if row.category != expected_category:
                    row.category = expected_category
                if row.description != expected_description:
                    row.description = expected_description
        db.session.commit()
        current_app.cli_logger.info(
            "metrics: synced event_registry — %d enum members",
            len(EventName),
        )
