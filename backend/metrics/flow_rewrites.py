"""Migration-safe rewrite of stored custom metric flows.

Used by Alembic migrations that rename an event, a dim key or a dim value, so
saved ``MetricFlows`` definitions follow the rename (and undo it on downgrade).

This module works on raw JSON with plain strings and SQLAlchemy Core only. It
must never import the event/dim registries, enums or the Pydantic flow models:
old migrations call it, and those registries change over time.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

_SELECT_FLOWS_SQL = text('SELECT id, definition FROM "MetricFlows" ORDER BY id')
_UPDATE_FLOW_SQL = text(
    'UPDATE "MetricFlows" SET definition = CAST(:definition AS JSONB) WHERE id = :id'
)


def _rename_filter_entry(
    entry: Any,
    *,
    key_renames: Mapping[str, str],
    value_renames: Mapping[str, Mapping[str, str]],
) -> Any:
    """Rename one ``'dim:value'`` entry (split on the first colon).

    The value map is keyed by the dim key as it stands before the key rename.
    """
    if not isinstance(entry, str) or ":" not in entry:
        return entry
    dim_key, dim_value = entry.split(":", 1)
    dim_value = value_renames.get(dim_key, {}).get(dim_value, dim_value)
    dim_key = key_renames.get(dim_key, dim_key)
    return f"{dim_key}:{dim_value}"


def _rewrite_dim_scope(
    owner: dict[str, Any],
    *,
    event_name: str,
    dim_key_renames: Mapping[str, Mapping[str, str]],
    dim_value_renames: Mapping[str, Mapping[str, Mapping[str, str]]],
    rename_group_by: bool,
) -> None:
    """Rewrite ``dim_filter`` (and ``group_by``) of a step or breakdown in place,
    using the maps registered for its own (post-event-rename) event."""
    key_renames = dim_key_renames.get(event_name, {})
    value_renames = dim_value_renames.get(event_name, {})
    dim_filter = owner.get("dim_filter")
    if isinstance(dim_filter, list):
        owner["dim_filter"] = [
            _rename_filter_entry(
                entry, key_renames=key_renames, value_renames=value_renames
            )
            for entry in dim_filter
        ]
    group_by = owner.get("group_by")
    if rename_group_by and isinstance(group_by, str):
        owner["group_by"] = key_renames.get(group_by, group_by)


def _rewrite_event_name(
    owner: dict[str, Any], *, event_renames: Mapping[str, str]
) -> str | None:
    """Rename ``owner['event_name']`` in place; return the post-rename name."""
    event_name = owner.get("event_name")
    if not isinstance(event_name, str):
        return None
    renamed_event = event_renames.get(event_name, event_name)
    owner["event_name"] = renamed_event
    return renamed_event


def _rewrite_definition(
    definition: dict[str, Any],
    *,
    event_renames: Mapping[str, str],
    dim_key_renames: Mapping[str, Mapping[str, str]],
    dim_value_renames: Mapping[str, Mapping[str, Mapping[str, str]]],
) -> dict[str, Any]:
    """Return a rewritten deep copy of a stored ``{"steps": [...]}`` definition."""
    rewritten = copy.deepcopy(definition)
    steps = rewritten.get("steps")
    if not isinstance(steps, list):
        return rewritten
    for step in steps:
        if not isinstance(step, dict):
            continue
        step_event = _rewrite_event_name(step, event_renames=event_renames)
        if step_event is not None:
            _rewrite_dim_scope(
                step,
                event_name=step_event,
                dim_key_renames=dim_key_renames,
                dim_value_renames=dim_value_renames,
                rename_group_by=False,
            )
        breakdown = step.get("drop_breakdown")
        if isinstance(breakdown, dict):
            breakdown_event = _rewrite_event_name(
                breakdown, event_renames=event_renames
            )
            if breakdown_event is not None:
                _rewrite_dim_scope(
                    breakdown,
                    event_name=breakdown_event,
                    dim_key_renames=dim_key_renames,
                    dim_value_renames=dim_value_renames,
                    rename_group_by=True,
                )
    return rewritten


def rewrite_metric_flow_definitions(
    connection: Connection,
    *,
    event_renames: Mapping[str, str],
    dim_key_renames: Mapping[str, Mapping[str, str]],
    dim_value_renames: Mapping[str, Mapping[str, Mapping[str, str]]],
) -> int:
    """Apply event, dim-key and dim-value renames to every stored custom flow.

    ``dim_key_renames`` is ``{event: {old_key: new_key}}`` and
    ``dim_value_renames`` is ``{event: {dim_key: {old_value: new_value}}}``. The
    event key is the event name as it stands after this call's
    ``event_renames`` (so a downgrade spec is keyed by the old event names), and
    a value map is keyed by the dim key as it stands before this call's
    ``dim_key_renames``. Steps without ``event_name`` (API steps) are not touched
    by dim renames.

    Returns the number of rows changed; unchanged rows are not updated.
    """
    changed_rows = 0
    for flow_id, definition in connection.execute(_SELECT_FLOWS_SQL).all():
        if not isinstance(definition, dict):
            continue
        rewritten = _rewrite_definition(
            definition,
            event_renames=event_renames,
            dim_key_renames=dim_key_renames,
            dim_value_renames=dim_value_renames,
        )
        if rewritten == definition:
            continue
        connection.execute(
            _UPDATE_FLOW_SQL,
            {"id": flow_id, "definition": json.dumps(rewritten)},
        )
        changed_rows += 1
    return changed_rows
