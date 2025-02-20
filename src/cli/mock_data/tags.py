from flask_sqlalchemy import SQLAlchemy

from src.cli.mock_constants import MOCK_TAGS
from src.models.utub_tags import Utub_Tags
from src.models.utubs import Utubs
from src.models.utub_url_tags import Utub_Url_Tags
from src.models.utub_urls import Utub_Urls


def generate_mock_tags(db: SQLAlchemy):
    """
    Generates mock tags, adds them to utub if not already added,
    and then adds those to each URL in each UTub.

    Args:
        db (SQLAlchemy): Database engine and connection for committing mock data
    """
    for idx, tag in enumerate(MOCK_TAGS):
        for utub in Utubs.query.all():
            tag_in_utub: bool = (
                Utub_Tags.query.filter(
                    Utub_Tags.utub_id == utub.id, Utub_Tags.tag_string == tag
                ).count()
                == 1
            )
            if not tag_in_utub:
                print(f"Adding {tag} as a tag to utub")
                new_tag = Utub_Tags(utub_id=utub.id, tag_string=tag, created_by=idx + 1)
                db.session.add(new_tag)

    db.session.commit()

    all_utubs: list[Utubs] = Utubs.query.all()

    for utub in all_utubs:
        urls_in_utub: list[Utub_Urls] = utub.utub_urls

        for url in urls_in_utub:
            if len(url.url_tags) == len(MOCK_TAGS):
                print(
                    f"{url.standalone_url.url_string} in {utub.name}, ID={utub.id} has 5 tags"
                )
                continue

            for tag in MOCK_TAGS:
                current_tag: Utub_Tags = Utub_Tags.query.filter(
                    Utub_Tags.utub_id == utub.id, Utub_Tags.tag_string == tag
                ).first()
                utub_url_tag = Utub_Url_Tags()
                utub_url_tag.utub_tag_id = current_tag.id
                utub_url_tag.utub_id = utub.id
                utub_url_tag.utub_url_id = url.id

                db.session.add(utub_url_tag)
                print(
                    f"Adding {tag} to {url.standalone_url.url_string} in {utub.name}, ID={utub.id}"
                )

    db.session.commit()
