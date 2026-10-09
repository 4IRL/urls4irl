"""Persisted ORM round-trip tests for the soft-delete columns.

The migration test proves the schema; the unit tests prove the in-memory
``is_trashed`` property. These tests commit real rows and re-read them from
Postgres to prove the columns (``deletedAt``/``deletedBy`` on Utubs and
UtubUrls, plus the ``UtubUrls.trashedTagIds`` JSONB snapshot) persist the
values the models promise, in particular that ``JSONB(none_as_null=True)``
stores Python ``None`` as SQL NULL rather than the JSON ``null`` literal.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from flask import Flask
from sqlalchemy import text

from backend import db
from backend.models.users import Users
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs

pytestmark = pytest.mark.cli


def _trashed_tag_ids_is_sql_null(utub_url_id: int) -> bool:
    """Return whether the row's trashedTagIds is SQL NULL (not JSON ``null``)."""
    return db.session.execute(
        text('SELECT "trashedTagIds" IS NULL FROM "UtubUrls" WHERE id = :id'),
        {"id": utub_url_id},
    ).scalar_one()


def test_utub_soft_delete_columns_round_trip(
    app: Flask, add_one_url_to_each_utub_no_tags
):
    """
    GIVEN an existing Utubs row and a real user
    WHEN deleted_at (timezone-aware) and deleted_by are set, committed and
        re-read from the database, and then both are cleared and committed
    THEN both values round-trip with deleted_at still timezone-aware and
        is_trashed True, and after clearing both are None and is_trashed False
    """
    with app.app_context():
        user: Users = Users.query.order_by(Users.id).first()
        utub: Utubs = Utubs.query.order_by(Utubs.id).first()
        utub_id = utub.id
        deleted_at = datetime.now(timezone.utc)

        utub.deleted_at = deleted_at
        utub.deleted_by = user.id
        db.session.commit()

        db.session.expire_all()
        reread: Utubs = db.session.get(Utubs, utub_id)
        db.session.refresh(reread)
        assert reread.deleted_at == deleted_at
        assert reread.deleted_at.tzinfo is not None
        assert reread.deleted_at.utcoffset() is not None
        assert reread.deleted_by == user.id
        assert reread.is_trashed is True

        reread.deleted_at = None
        reread.deleted_by = None
        db.session.commit()

        db.session.expire_all()
        cleared: Utubs = db.session.get(Utubs, utub_id)
        db.session.refresh(cleared)
        assert cleared.deleted_at is None
        assert cleared.deleted_by is None
        assert cleared.is_trashed is False


def test_utub_urls_soft_delete_columns_round_trip(
    app: Flask, add_one_url_to_each_utub_no_tags
):
    """
    GIVEN an existing Utub_Urls row and a real user
    WHEN deleted_at (timezone-aware) and deleted_by are set, committed and
        re-read from the database, and then both are cleared and committed
    THEN both values round-trip with deleted_at still timezone-aware and
        is_trashed True, and after clearing both are None and is_trashed False
    """
    with app.app_context():
        user: Users = Users.query.order_by(Users.id).first()
        utub_url: Utub_Urls = Utub_Urls.query.order_by(Utub_Urls.id).first()
        utub_url_id = utub_url.id
        deleted_at = datetime.now(timezone.utc)

        utub_url.deleted_at = deleted_at
        utub_url.deleted_by = user.id
        db.session.commit()

        db.session.expire_all()
        reread: Utub_Urls = db.session.get(Utub_Urls, utub_url_id)
        db.session.refresh(reread)
        assert reread.deleted_at == deleted_at
        assert reread.deleted_at.tzinfo is not None
        assert reread.deleted_at.utcoffset() is not None
        assert reread.deleted_by == user.id
        assert reread.is_trashed is True

        reread.deleted_at = None
        reread.deleted_by = None
        db.session.commit()

        db.session.expire_all()
        cleared: Utub_Urls = db.session.get(Utub_Urls, utub_url_id)
        db.session.refresh(cleared)
        assert cleared.deleted_at is None
        assert cleared.deleted_by is None
        assert cleared.is_trashed is False


def test_trashed_tag_ids_none_persists_as_sql_null(
    app: Flask, add_one_url_to_each_utub_no_tags
):
    """
    GIVEN a new Utub_Urls row explicitly committed with trashed_tag_ids=None
    WHEN the column is read back via raw SQL and via the ORM
    THEN it is SQL NULL (not the JSON null literal), a list round-trips as
        [1, 2], and reassigning None after a list clears it to SQL NULL again
    """
    with app.app_context():
        existing: Utub_Urls = Utub_Urls.query.order_by(Utub_Urls.id).first()

        # Reuse the first utub with a URL it does not already contain, so the
        # row is a new INSERT carrying an explicit None for trashed_tag_ids.
        new_utub_url = Utub_Urls()
        new_utub_url.utub_id = existing.utub_id
        new_utub_url.url_id = existing.url_id + 1
        new_utub_url.user_id = existing.user_id
        new_utub_url.url_title = "explicit none trashed tag ids"
        new_utub_url.trashed_tag_ids = None
        db.session.add(new_utub_url)
        db.session.commit()
        utub_url_id = new_utub_url.id

        assert _trashed_tag_ids_is_sql_null(utub_url_id) is True

        row: Utub_Urls = db.session.get(Utub_Urls, utub_url_id)
        row.trashed_tag_ids = [1, 2]
        db.session.commit()

        db.session.expire_all()
        row = db.session.get(Utub_Urls, utub_url_id)
        db.session.refresh(row)
        assert row.trashed_tag_ids == [1, 2]
        assert _trashed_tag_ids_is_sql_null(utub_url_id) is False

        row.trashed_tag_ids = None
        db.session.commit()

        db.session.expire_all()
        row = db.session.get(Utub_Urls, utub_url_id)
        db.session.refresh(row)
        assert row.trashed_tag_ids is None
        assert _trashed_tag_ids_is_sql_null(utub_url_id) is True
