"""Model-level tests for ShortLinks: DB cascade, ORM deletes and unique constraints."""

from __future__ import annotations

from datetime import timedelta

import pytest
from flask import Flask
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from backend import db
from backend.models.short_links import SHORT_LINK_CODE_LENGTH, Short_Links
from backend.models.users import Users
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.short_links.constants import SHORT_LINK_TTL
from backend.utils.datetime_utils import utc_now

pytestmark = pytest.mark.short_links

CODE_A: str = "AbCdEfGh12"
CODE_B: str = "ZyXwVuTs98"


def _first_user_id() -> int:
    user = db.session.query(Users).order_by(Users.id).first()
    assert user is not None
    return user.id


def _two_utub_urls() -> tuple[Utub_Urls, Utub_Urls]:
    """Return two seeded Utub_Urls rows (precondition: the fixture seeded at least two)."""
    rows = db.session.query(Utub_Urls).order_by(Utub_Urls.id).limit(2).all()
    assert len(rows) == 2
    return rows[0], rows[1]


def _mint(utub_url_id: int, code: str = CODE_A) -> int:
    link = Short_Links(
        utub_url_id=utub_url_id,
        code=code,
        created_by=_first_user_id(),
        expires_at=utc_now() + SHORT_LINK_TTL,
    )
    db.session.add(link)
    db.session.commit()
    return link.id


def _link_count() -> int:
    return db.session.query(Short_Links).count()


def test_code_length_constant() -> None:
    """
    GIVEN the model module
    THEN the code length constant is 10
    """
    assert SHORT_LINK_CODE_LENGTH == 10


def test_is_expired(app: Flask, add_one_url_to_each_utub_no_tags) -> None:
    """
    GIVEN a short link
    WHEN expiresAt is in the future, then the past
    THEN is_expired is False, then True
    """
    with app.app_context():
        first, _ = _two_utub_urls()
        link_id = _mint(first.id)
        link = db.session.get(Short_Links, link_id)
        assert link is not None
        assert not link.is_expired()

        link.expires_at = utc_now() - timedelta(seconds=1)
        db.session.commit()
        assert link.is_expired()


def test_raw_sql_delete_of_utub_url_cascades_in_db(
    app: Flask, add_one_url_to_each_utub_no_tags
) -> None:
    """
    GIVEN a short link on a UtubUrls row
    WHEN the UtubUrls row is deleted with raw SQL (as purge_trash.py does)
    THEN the DB-level ON DELETE CASCADE removes the ShortLinks row
    """
    with app.app_context():
        first, second = _two_utub_urls()
        first_id, second_id = first.id, second.id
        _mint(first_id)
        _mint(second_id, code=CODE_B)
        assert _link_count() == 2

        db.session.execute(
            text('DELETE FROM "UtubUrls" WHERE id = :id'), {"id": first_id}
        )
        db.session.commit()

        assert _link_count() == 1
        remaining = db.session.query(Short_Links).one()
        assert remaining.utub_url_id == second_id


def test_raw_sql_delete_of_utub_cascades_to_link(
    app: Flask, add_one_url_to_each_utub_no_tags
) -> None:
    """
    GIVEN a short link on a URL in a UTub
    WHEN the whole UTub is deleted with raw SQL
    THEN the UtubUrls row and its ShortLinks row are both gone
    """
    with app.app_context():
        first, _ = _two_utub_urls()
        utub_id = first.utub_id
        _mint(first.id)
        # UtubMembers has no DB-level cascade to Utubs; clear it as the purge SQL does.
        db.session.execute(
            text('DELETE FROM "UtubMembers" WHERE "utubID" = :id'), {"id": utub_id}
        )
        db.session.execute(text('DELETE FROM "Utubs" WHERE id = :id'), {"id": utub_id})
        db.session.commit()

        assert _link_count() == 0


def test_orm_delete_with_loaded_link(
    app: Flask, add_one_url_to_each_utub_no_tags
) -> None:
    """
    GIVEN a Utub_Urls row whose short_link relationship is already loaded
    WHEN the row is deleted through the ORM
    THEN the link is deleted with it, with no IntegrityError or NULL-FK update
    """
    with app.app_context():
        first, _ = _two_utub_urls()
        _mint(first.id)
        utub_url = db.session.get(Utub_Urls, first.id)
        assert utub_url is not None
        assert utub_url.short_link is not None  # load the relationship

        db.session.delete(utub_url)
        db.session.commit()

        assert _link_count() == 0


def test_orm_delete_with_unloaded_link(
    app: Flask, add_one_url_to_each_utub_no_tags
) -> None:
    """
    GIVEN a Utub_Urls row whose short_link relationship is NOT loaded
    WHEN the row is deleted through the ORM
    THEN the DB cascade removes the link, with no IntegrityError
    """
    with app.app_context():
        first, _ = _two_utub_urls()
        first_id = first.id
        _mint(first_id)
        db.session.expire_all()
        utub_url = db.session.get(Utub_Urls, first_id)
        assert utub_url is not None
        assert "short_link" not in utub_url.__dict__

        db.session.delete(utub_url)
        db.session.commit()

        assert _link_count() == 0


def test_orm_delete_of_utub_removes_links(
    app: Flask, add_one_url_to_each_utub_no_tags
) -> None:
    """
    GIVEN a short link on a URL in a UTub
    WHEN the whole UTub is deleted through the ORM
    THEN the link is removed too
    """
    with app.app_context():
        first, _ = _two_utub_urls()
        utub_id = first.utub_id
        _mint(first.id)
        db.session.expire_all()
        utub = db.session.get(Utubs, utub_id)
        assert utub is not None

        db.session.delete(utub)
        db.session.commit()

        assert _link_count() == 0


def test_orm_delete_of_utub_with_loaded_links_removes_links(
    app: Flask, add_one_url_to_each_utub_no_tags
) -> None:
    """
    GIVEN a short link on a URL in a UTub, with utub_urls and each short_link loaded
    WHEN the whole UTub is deleted through the ORM
    THEN the loaded link is deleted with it, with no IntegrityError or NULL-FK update
    """
    with app.app_context():
        first, _ = _two_utub_urls()
        utub_id = first.utub_id
        _mint(first.id)
        db.session.expire_all()
        utub = db.session.get(Utubs, utub_id)
        assert utub is not None
        loaded_links = [
            utub_url.short_link
            for utub_url in utub.utub_urls
            if utub_url.short_link is not None
        ]
        assert len(loaded_links) == 1

        db.session.delete(utub)
        db.session.commit()

        assert _link_count() == 0


def test_deleting_creator_nulls_created_by(
    app: Flask, add_one_url_to_each_utub_no_tags
) -> None:
    """
    GIVEN a short link whose createdBy points at a throwaway user
    WHEN that user is deleted with raw SQL
    THEN the link survives with createdBy NULL (ON DELETE SET NULL)
    """
    with app.app_context():
        first, _ = _two_utub_urls()
        link_id = _mint(first.id)

        throwaway = Users(
            username="shortlinkgone",
            email="shortlinkgone@example.com",
            plaintext_password="shortlinkgone",
        )
        db.session.add(throwaway)
        db.session.commit()
        throwaway_id = throwaway.id

        db.session.execute(
            text('UPDATE "ShortLinks" SET "createdBy" = :uid WHERE id = :id'),
            {"uid": throwaway_id, "id": link_id},
        )
        db.session.commit()

        db.session.execute(
            text('DELETE FROM "Users" WHERE id = :id'), {"id": throwaway_id}
        )
        db.session.commit()
        db.session.expire_all()

        link = db.session.get(Short_Links, link_id)
        assert link is not None
        assert link.created_by is None


def test_second_link_for_same_utub_url_violates_unique(
    app: Flask, add_one_url_to_each_utub_no_tags
) -> None:
    """
    GIVEN a short link for a UtubUrls row
    WHEN a second link is added for the same UtubUrls row
    THEN unique_short_link_per_utub_url raises an IntegrityError
    """
    with app.app_context():
        first, _ = _two_utub_urls()
        first_id = first.id
        _mint(first_id)
        with pytest.raises(IntegrityError, match="unique_short_link_per_utub_url"):
            _mint(first_id, code=CODE_B)
        db.session.rollback()


def test_duplicate_code_violates_unique(
    app: Flask, add_one_url_to_each_utub_no_tags
) -> None:
    """
    GIVEN a short link with a code
    WHEN another UtubUrls row gets a link with the same code
    THEN unique_short_link_code raises an IntegrityError
    """
    with app.app_context():
        first, second = _two_utub_urls()
        first_id, second_id = first.id, second.id
        _mint(first_id)
        with pytest.raises(IntegrityError, match="unique_short_link_code"):
            _mint(second_id)
        db.session.rollback()
