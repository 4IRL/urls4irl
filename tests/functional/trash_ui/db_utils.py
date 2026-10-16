from flask import Flask

from backend import db
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from tests.functional.db_utils import add_url_to_utub_as_other_member


def create_utub_as_creator(app: Flask, user_id: int, utub_name: str) -> int:
    """Create a UTub owned by ``user_id`` (with its CREATOR membership row) and
    return its id. The Trash suite seeds its own UTubs instead of the mock set so
    every test controls exactly which rows exist."""
    with app.app_context():
        utub = Utubs(name=utub_name, utub_description="", utub_creator=user_id)
        db.session.add(utub)
        db.session.commit()

        membership = Utub_Members()
        membership.utub_id = utub.id
        membership.user_id = user_id
        membership.member_role = Member_Role.CREATOR
        db.session.add(membership)
        db.session.commit()
        return utub.id


def add_url_to_utub(
    app: Flask, utub_id: int, user_id: int, url_string: str, url_title: str
) -> int:
    """Add a URL authored by ``user_id`` to the UTub; returns the ``Utub_Urls`` id."""
    return add_url_to_utub_as_other_member(app, utub_id, user_id, url_string, url_title)


def add_tag_to_url(
    app: Flask, utub_id: int, utub_url_id: int, user_id: int, tag_string: str
) -> int:
    """Create a UTub tag and attach it to the URL; returns the ``Utub_Tags`` id."""
    with app.app_context():
        tag = Utub_Tags(utub_id=utub_id, tag_string=tag_string, created_by=user_id)
        db.session.add(tag)
        db.session.flush()

        url_tag = Utub_Url_Tags()
        url_tag.utub_id = utub_id
        url_tag.utub_url_id = utub_url_id
        url_tag.utub_tag_id = tag.id
        url_tag.user_id = user_id
        db.session.add(url_tag)
        db.session.commit()
        return tag.id


def delete_utub_tag(app: Flask, tag_id: int) -> None:
    """Delete a UTub tag and every URL association of it."""
    with app.app_context():
        Utub_Url_Tags.query.filter(Utub_Url_Tags.utub_tag_id == tag_id).delete()
        Utub_Tags.query.filter(Utub_Tags.id == tag_id).delete()
        db.session.commit()


def purge_utub_url_row(app: Flask, utub_url_id: int) -> None:
    """Hard-delete a ``Utub_Urls`` row, as the purge job would, so a Trash list
    that still shows it holds a stale row."""
    with app.app_context():
        Utub_Url_Tags.query.filter(Utub_Url_Tags.utub_url_id == utub_url_id).delete()
        Utub_Urls.query.filter(Utub_Urls.id == utub_url_id).delete()
        db.session.commit()
