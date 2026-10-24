"""DB-level behavior of the ``Metric_Flows`` model on a ``db.create_all()`` database."""

from __future__ import annotations

from typing import Any

import pytest
from flask import Flask
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError

from backend import db
from backend.models.metric_flows import (
    DEFINITION_STEPS_ARRAY_CHECK,
    DISPLAY_NAME_LOWER_INDEX,
    DISPLAY_NAME_TRIMMED_CHECK,
    Metric_Flows,
)

pytestmark = pytest.mark.cli

_VALID_DEFINITION: dict[str, Any] = {"steps": []}


_DEFAULT_DEFINITION: Any = object()


def _add_flow(display_name: str, definition: Any = _DEFAULT_DEFINITION) -> Metric_Flows:
    flow = Metric_Flows(
        display_name=display_name,
        definition=_VALID_DEFINITION
        if definition is _DEFAULT_DEFINITION
        else definition,
        created_by=None,
        updated_by=None,
    )
    db.session.add(flow)
    return flow


def _assert_commit_rejected(constraint_name: str) -> None:
    with pytest.raises(IntegrityError) as raised:
        db.session.commit()
    db.session.rollback()
    assert constraint_name in str(raised.value)


def test_duplicate_name_differing_in_case_is_rejected_but_own_case_rename_works(
    app: Flask,
):
    """
    GIVEN a stored flow named "Foo"
    WHEN another flow named "foo" is committed, and then the first flow is renamed "foo"
    THEN the duplicate raises IntegrityError naming the unique index, and the
         rename of the row's own name succeeds
    """
    with app.app_context():
        _add_flow("Foo")
        db.session.commit()

        _add_flow("foo")
        _assert_commit_rejected(DISPLAY_NAME_LOWER_INDEX)

        flow = db.session.query(Metric_Flows).one()
        flow.display_name = "foo"
        db.session.commit()
        assert db.session.query(Metric_Flows).one().display_name == "foo"


def test_check_constraints_reject_invalid_rows(app: Flask):
    """
    GIVEN the MetricFlows check constraints
    WHEN rows with a bad definition envelope or an empty/padded name are committed
    THEN each raises IntegrityError naming the violated constraint
    """
    with app.app_context():
        steps_array_cases: list[Any] = [
            {},
            JSONB.NULL,
            {"other": []},
            {"steps": 5},
            {"steps": {}},
        ]
        for definition in steps_array_cases:
            _add_flow("Bad definition", definition)
            _assert_commit_rejected(DEFINITION_STEPS_ARRAY_CHECK)

        for display_name in ("", " ", " padded", "padded "):
            _add_flow(display_name)
            _assert_commit_rejected(DISPLAY_NAME_TRIMMED_CHECK)

        assert db.session.query(Metric_Flows).count() == 0
