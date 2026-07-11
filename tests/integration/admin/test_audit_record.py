"""Integration tests for the AuditLog model and the audit.record() helper.

Covers:
  - Model round-trip: every column persists and is queryable.
  - audit.record() is flush-only: the row is visible in-session but is
    discarded by a caller rollback — the caller owns the commit.
  - audit.record() + caller commit persists the row.
  - audit.record() with only required args: nullable columns default to None.
  - audit.record() failure path: the failed audit write rolls back only its
    own savepoint — the caller's pending mutation survives and commits — and
    the specific warning is emitted without any exception propagating.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from flask import Flask

from backend import db
from backend.extensions import audit
from backend.models.audit_log import AuditLog
from backend.models.users import Users

pytestmark = pytest.mark.admin

ACTION_TEST = "admin.test.action"
ACTION_TEST_MINIMAL = "admin.test.minimal"
ACTION_OVER_COLUMN_LIMIT = "admin.test." + ("x" * 100)
METADATA_DICT: dict = {"query": "foo", "extra": 42}
TARGET_TYPE_USER = "User"
MUTATED_USERNAME = "MutatedByCaller"


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


def test_audit_record_is_flush_only(app: Flask, register_first_user):
    """
    GIVEN a registered user and an empty AuditLogs table
    WHEN audit.record() is called and the caller then rolls back
    THEN the row was visible in-session after the call (flushed) but is gone
         after the rollback — proving record() never commits and the caller
         owns the transaction.
    """
    _, registered_user = register_first_user
    actor_id: int = registered_user.id

    assert AuditLog.query.count() == 0

    audit.record(actor_id=actor_id, action=ACTION_TEST)

    assert AuditLog.query.count() == 1

    db.session.rollback()

    assert AuditLog.query.count() == 0


def test_audit_record_persists_with_caller_commit(app: Flask, register_first_user):
    """
    GIVEN a registered user and an empty AuditLogs table
    WHEN audit.record() is called with all args and the caller commits
    THEN exactly one AuditLog row exists with those values, visible after
         session.expunge_all() — confirming it was committed by the caller.
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
    db.session.commit()

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
    WHEN audit.record() is called with only the required actor_id and action,
         and the caller commits
    THEN exactly one row is persisted and target_type, target_id, and
         log_metadata are all None.
    """
    _, registered_user = register_first_user
    actor_id: int = registered_user.id

    assert AuditLog.query.count() == 0

    audit.record(actor_id=actor_id, action=ACTION_TEST_MINIMAL)
    db.session.commit()

    audit_rows = AuditLog.query.all()
    assert len(audit_rows) == 1

    audit_row = audit_rows[0]
    assert audit_row.actor_id == actor_id
    assert audit_row.action == ACTION_TEST_MINIMAL
    assert audit_row.target_type is None
    assert audit_row.target_id is None
    assert audit_row.log_metadata is None


def test_audit_record_failure_does_not_roll_back_caller_mutation(
    app: Flask, register_first_user
):
    """
    GIVEN a registered user with a pending (uncommitted) username mutation
    WHEN audit.record() fails at flush time (action exceeds the 100-char
         column limit, rejected by Postgres inside the audit savepoint)
    THEN no exception propagates, the specific warning is emitted, the
         caller's mutation still commits successfully, and no AuditLog row
         persists — the audit failure rolled back only its own savepoint.
    """
    _, registered_user = register_first_user
    actor_id: int = registered_user.id

    assert AuditLog.query.count() == 0
    assert registered_user.username != MUTATED_USERNAME

    registered_user.username = MUTATED_USERNAME

    with patch("backend.extensions.audit.record.warning_log") as mock_warning_log:
        audit.record(actor_id=actor_id, action=ACTION_OVER_COLUMN_LIMIT)

    db.session.commit()
    db.session.expunge_all()

    persisted_user = Users.query.get(actor_id)
    assert persisted_user is not None
    assert persisted_user.username == MUTATED_USERNAME
    assert AuditLog.query.count() == 0

    mock_warning_log.assert_called_once()
    warning_message: str = mock_warning_log.call_args[0][0]
    assert (
        f"audit.record failed for action={ACTION_OVER_COLUMN_LIMIT}" in warning_message
    )


def test_caller_rollback_discards_pending_audit_row(app: Flask, register_first_user):
    """
    GIVEN a registered user and a successfully flushed audit.record() call
    WHEN the caller's own flow fails and it rolls back the session
    THEN the audit row is discarded along with the caller's writes — the
         audit row and the mutation share one transaction atomically.
    """
    _, registered_user = register_first_user
    actor_id: int = registered_user.id

    assert AuditLog.query.count() == 0

    registered_user.username = MUTATED_USERNAME
    audit.record(actor_id=actor_id, action=ACTION_TEST)

    assert AuditLog.query.count() == 1

    db.session.rollback()

    assert AuditLog.query.count() == 0
    refreshed_user = Users.query.get(actor_id)
    assert refreshed_user is not None
    assert refreshed_user.username != MUTATED_USERNAME
