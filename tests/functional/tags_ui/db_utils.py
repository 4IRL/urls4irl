from flask import Flask

from backend import db
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.utils.constants import TAG_CONSTANTS


def get_tag_in_utub(app: Flask, tag_id: int) -> Utub_Tags:
    with app.app_context():
        return Utub_Tags.query.get(tag_id)


def get_url_ids_in_utub_ordered(*, app: Flask, utub_id: int) -> list[int]:
    """Every URL id in a UTub ordered by primary key (stable across runs)."""
    with app.app_context():
        return [
            utub_url.id
            for utub_url in Utub_Urls.query.filter(Utub_Urls.utub_id == utub_id)
            .order_by(Utub_Urls.id)
            .all()
        ]


def get_url_title(*, app: Flask, utub_url_id: int) -> str:
    with app.app_context():
        utub_url: Utub_Urls = Utub_Urls.query.get(utub_url_id)
        return utub_url.url_title


def create_utub_tag(*, app: Flask, utub_id: int, user_id: int, tag_string: str) -> int:
    """Create a UTub tag applied to no URL. Returns the new tag id."""
    with app.app_context():
        new_tag = Utub_Tags(utub_id=utub_id, tag_string=tag_string, created_by=user_id)
        db.session.add(new_tag)
        db.session.commit()
        return new_tag.id


def apply_tag_to_url_in_db(
    *, app: Flask, utub_id: int, user_id: int, utub_url_id: int, utub_tag_id: int
) -> None:
    """Apply an existing UTub tag to a URL directly in the DB."""
    with app.app_context():
        db.session.add(
            Utub_Url_Tags(
                utub_id=utub_id,
                utub_url_id=utub_url_id,
                utub_tag_id=utub_tag_id,
                user_id=user_id,
            )
        )
        db.session.commit()


def fill_url_to_tag_limit(
    *, app: Flask, utub_id: int, user_id: int, utub_url_id: int
) -> list[int]:
    """Apply MAX_URL_TAGS distinct fresh tags to one URL so it sits exactly at
    the per-URL tag limit. Returns the new tag ids."""
    tag_ids: list[int] = []
    for index in range(TAG_CONSTANTS.MAX_URL_TAGS):
        tag_id = create_utub_tag(
            app=app,
            utub_id=utub_id,
            user_id=user_id,
            tag_string=f"limit-tag-{index}",
        )
        apply_tag_to_url_in_db(
            app=app,
            utub_id=utub_id,
            user_id=user_id,
            utub_url_id=utub_url_id,
            utub_tag_id=tag_id,
        )
        tag_ids.append(tag_id)
    return tag_ids


def count_tags_on_url(*, app: Flask, utub_url_id: int) -> int:
    with app.app_context():
        return Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_url_id == utub_url_id
        ).count()
