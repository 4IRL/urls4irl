"""Integration tests for the AuditLog model and the audit.record() helper.

Covers:
  - Model round-trip: every column persists and is queryable.
  - audit.record() happy path: row is committed, not just pending.
  - audit.record() with only required args: nullable columns default to None.
  - audit.record() failure path: commit error is swallowed, nothing persists,
    and the specific warning is emitted.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from flask import Flask

from backend import db
from backend.extensions import audit
from backend.models.audit_log import AuditLog

pytestmark = pytest.mark.admin

ACTION_TEST = "admin.test.action"
ACTION_TEST_MINIMAL = "admin.test.minimal"
METADATA_DICT: dict = {"query": "foo", "extra": 42}
TARGET_TYPE_USER = "User"


def test_audit_log_model_round_trip(app: Flask, register_first_user):
    """
    GIVEN a registered user and an empty AuditLogs table
    WHEN an AuditLog row is inserted directly with all fields, including a
         metadata dict, and then queried back
    THEN every field matches the inserted values, created_at is timezone-aware,
         and log_metadata round-trips the dict exactly.
    """
    _, registered_user = register_first_user
    actor_id: int = registered_user.id
    target_id_str: str = str(actor_id)

    assert AuditLog.query.count() == 0

    audit_entry = AuditLog(
        actor_id=actor_id,
        action=ACTION_TEST,
        target_type=TARGET_TYPE_USER,
        target_id=target_id_str,
        log_metadata=METADATA_DICT,
    )
    db.session.add(audit_entry)
    db.session.commit()

    queried_entry = AuditLog.query.get(audit_entry.id)

    assert queried_entry is not None
    assert queried_entry.actor_id == actor_id
    assert queried_entry.action == ACTION_TEST
    assert queried_entry.target_type == TARGET_TYPE_USER
    assert queried_entry.target_id == target_id_str
    assert queried_entry.log_metadata == METADATA_DICT
    assert queried_entry.created_at is not None
    assert queried_entry.created_at.tzinfo is not None


def test_audit_record_happy_path(app: Flask, register_first_user):
    """
    GIVEN a registered user and an empty AuditLogs table
    WHEN audit.record() is called with actor_id, action, target_type,
         target_id, and metadata
    THEN exactly one AuditLog row exists with those values, and the row is
         visible after session.expunge_all() — confirming it was committed,
         not merely pending.
    """
    _, registered_user = register_first_user
    actor_id: int = registered_user.id

    assert AuditLog.query.count() == 0

    audit.record(
        actor_id=actor_id,
        action=ACTION_TEST,
        target_type=TARGET_TYPE_USER,
        target_id=str(actor_id),
        metadata=METADATA_DICT,
    )

    db.session.expunge_all()

    audit_rows = AuditLog.query.all()
    assert len(audit_rows) == 1

    audit_row = audit_rows[0]
    assert audit_row.actor_id == actor_id
    assert audit_row.action == ACTION_TEST
    assert audit_row.target_type == TARGET_TYPE_USER
    assert audit_row.target_id == str(actor_id)
    assert audit_row.log_metadata == METADATA_DICT


def test_audit_record_optional_args_default_to_none(app: Flask, register_first_user):
    """
    GIVEN a registered user and an empty AuditLogs table
    WHEN audit.record() is called with only the required actor_id and action
    THEN exactly one row is persisted and target_type, target_id, and
         log_metadata are all None.
    """
    _, registered_user = register_first_user
    actor_id: int = registered_user.id

    assert AuditLog.query.count() == 0

    audit.record(actor_id=actor_id, action=ACTION_TEST_MINIMAL)

    audit_rows = AuditLog.query.all()
    assert len(audit_rows) == 1

    audit_row = audit_rows[0]
    assert audit_row.actor_id == actor_id
    assert audit_row.action == ACTION_TEST_MINIMAL
    assert audit_row.target_type is None
    assert audit_row.target_id is None
    assert audit_row.log_metadata is None


def test_audit_record_failure_does_not_propagate(app: Flask, register_first_user):
    """
    GIVEN a registered user and a db.session.commit patched to raise
    WHEN audit.record() is called
    THEN no exception propagates to the caller, no AuditLog row persists after
         rollback, and the warning "audit.record failed for action=<action>"
         is emitted — confirming the failure path is silenced and logged.
    """
    _, registered_user = register_first_user
    actor_id: int = registered_user.id

    assert AuditLog.query.count() == 0

    with patch("backend.extensions.audit.record.warning_log") as mock_warning_log:
        with patch.object(
            db.session, "commit", side_effect=RuntimeError("forced commit failure")
        ):
            audit.record(actor_id=actor_id, action=ACTION_TEST)

    assert AuditLog.query.count() == 0

    mock_warning_log.assert_called_once()
    warning_message: str = mock_warning_log.call_args[0][0]
    assert f"audit.record failed for action={ACTION_TEST}" in warning_message
