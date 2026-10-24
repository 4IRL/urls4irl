"""``rewrite_metric_flow_definitions`` against a real ``MetricFlows`` row.

The seeded definition uses invented event/dim names on purpose: the helper works
on raw JSON and must not depend on the live registries.
"""

from __future__ import annotations

import copy
import json
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Connection

from backend import db
from backend.metrics.flow_rewrites import rewrite_metric_flow_definitions

pytestmark = pytest.mark.cli

_FLOW_NAME = "Rewrite fixture"

_ORIGINAL_DEFINITION: dict[str, Any] = {
    "steps": [
        {
            # Renamed event AND dim/value-renamed in the same spec.
            "stream": "ui",
            "label": "Renamed",
            "event_name": "old_evt",
            "dim_filter": ["old_dim:old_val", "other_dim:old_val"],
            "drop_breakdown": {
                "event_name": "old_bd_evt",
                "dim_filter": ["old_dim:old_val", "other_dim:old_val"],
                "group_by": "old_dim",
            },
        },
        {
            # Unrelated event sharing the dim key and value: must stay unchanged.
            "stream": "ui",
            "label": "Unrelated",
            "event_name": "plain_evt",
            "dim_filter": ["old_dim:old_val"],
            # Only the breakdown's event matches a dim-rename key.
            "drop_breakdown": {
                "event_name": "bd_evt",
                "dim_filter": ["old_dim:old_val:with:colons"],
                "group_by": "old_dim",
            },
        },
        {
            "stream": "api",
            "label": "Api step",
            "api_endpoint": "utubs.home",
            "api_method": "POST",
        },
    ]
}

_UPGRADE_SPEC: dict[str, Any] = {
    "event_renames": {"old_evt": "new_evt", "old_bd_evt": "new_bd_evt"},
    "dim_key_renames": {
        "new_evt": {"old_dim": "new_dim"},
        "new_bd_evt": {"old_dim": "new_dim"},
        "bd_evt": {"old_dim": "new_dim"},
    },
    "dim_value_renames": {
        "new_evt": {"old_dim": {"old_val": "new_val"}},
        "new_bd_evt": {"old_dim": {"old_val": "new_val"}},
        "bd_evt": {"old_dim": {"old_val": "new_val", "old_val:with:colons": "kept"}},
    },
}

# Event keys are the post-rename names, i.e. the old names for the inverse; the
# value maps are keyed by the dim key as it stands before the key rename.
_INVERSE_SPEC: dict[str, Any] = {
    "event_renames": {"new_evt": "old_evt", "new_bd_evt": "old_bd_evt"},
    "dim_key_renames": {
        "old_evt": {"new_dim": "old_dim"},
        "old_bd_evt": {"new_dim": "old_dim"},
        "bd_evt": {"new_dim": "old_dim"},
    },
    "dim_value_renames": {
        "old_evt": {"new_dim": {"new_val": "old_val"}},
        "old_bd_evt": {"new_dim": {"new_val": "old_val"}},
        "bd_evt": {"new_dim": {"new_val": "old_val", "kept": "old_val:with:colons"}},
    },
}

_EXPECTED_UPGRADED_DEFINITION: dict[str, Any] = {
    "steps": [
        {
            "stream": "ui",
            "label": "Renamed",
            "event_name": "new_evt",
            "dim_filter": ["new_dim:new_val", "other_dim:old_val"],
            "drop_breakdown": {
                "event_name": "new_bd_evt",
                "dim_filter": ["new_dim:new_val", "other_dim:old_val"],
                "group_by": "new_dim",
            },
        },
        {
            "stream": "ui",
            "label": "Unrelated",
            "event_name": "plain_evt",
            "dim_filter": ["old_dim:old_val"],
            "drop_breakdown": {
                "event_name": "bd_evt",
                "dim_filter": ["new_dim:kept"],
                "group_by": "new_dim",
            },
        },
        {
            "stream": "api",
            "label": "Api step",
            "api_endpoint": "utubs.home",
            "api_method": "POST",
        },
    ]
}


def _seed_flow(connection: Connection) -> int:
    return connection.execute(
        text(
            'INSERT INTO "MetricFlows" '
            '("displayName", definition, "createdAt", "updatedAt") '
            "VALUES (:name, CAST(:definition AS JSONB), now(), now()) RETURNING id"
        ),
        {"name": _FLOW_NAME, "definition": json.dumps(_ORIGINAL_DEFINITION)},
    ).scalar_one()


def _read_definition(connection: Connection, flow_id: int) -> dict[str, Any]:
    return connection.execute(
        text('SELECT definition FROM "MetricFlows" WHERE id = :id'), {"id": flow_id}
    ).scalar_one()


def test_rewrite_upgrade_inverse_round_trip_and_idempotence(runner):
    """
    GIVEN a stored flow using every rewritable location, an unrelated event that
         shares the dim key, a breakdown-only keying case and an API step
    WHEN the upgrade spec is applied, then the inverse spec, then the upgrade
         spec twice more
    THEN each location is rewritten for the matching event only (count 1), the
         inverse restores the original JSON exactly, and a repeat upgrade call
         is a no-op (count 0)
    """
    app, _ = runner
    with app.app_context():
        with db.engine.begin() as connection:
            flow_id = _seed_flow(connection)

            assert rewrite_metric_flow_definitions(connection, **_UPGRADE_SPEC) == 1
            assert (
                _read_definition(connection, flow_id) == _EXPECTED_UPGRADED_DEFINITION
            )

            assert rewrite_metric_flow_definitions(connection, **_INVERSE_SPEC) == 1
            assert _read_definition(connection, flow_id) == _ORIGINAL_DEFINITION

            assert rewrite_metric_flow_definitions(connection, **_UPGRADE_SPEC) == 1
            assert rewrite_metric_flow_definitions(connection, **_UPGRADE_SPEC) == 0
            assert (
                _read_definition(connection, flow_id) == _EXPECTED_UPGRADED_DEFINITION
            )


def test_rewrite_leaves_non_matching_rows_untouched(runner):
    """
    GIVEN a stored flow that no rename matches
    WHEN the rewrite helper runs
    THEN it returns 0 and the stored JSON is unchanged
    """
    app, _ = runner
    unmatched_spec = copy.deepcopy(_UPGRADE_SPEC)
    unmatched_spec["event_renames"] = {"missing_evt": "other_evt"}
    unmatched_spec["dim_key_renames"] = {}
    unmatched_spec["dim_value_renames"] = {}
    with app.app_context():
        with db.engine.begin() as connection:
            flow_id = _seed_flow(connection)
            assert rewrite_metric_flow_definitions(connection, **unmatched_spec) == 0
            assert _read_definition(connection, flow_id) == _ORIGINAL_DEFINITION
