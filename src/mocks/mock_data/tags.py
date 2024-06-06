from flask_sqlalchemy import SQLAlchemy

from src.mocks.mock_constants import MOCK_TAGS
from src.models.tags import Tags
from src.models.utubs import Utubs
from src.models.utub_url_tags import Utub_Url_Tags
from src.models.utub_urls import Utub_Urls


def generate_mock_tags(db: SQLAlchemy):
    for idx, tag in enumerate(MOCK_TAGS):
        all_tags: list[Tags] = Tags.query.all()
        all_tag_strings = [tag.tag_string for tag in all_tags]
        if tag not in all_tag_strings:
            print(f"Adding {tag} as a tag to database")
            new_tag = Tags(tag_string=tag, created_by=idx + 1)
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
                current_tag: Tags = Tags.query.filter(Tags.tag_string == tag).first()
                utub_url_tag = Utub_Url_Tags()
                utub_url_tag.tag_id = current_tag.id
                utub_url_tag.utub_id = utub.id
                utub_url_tag.utub_url_id = url.id

                db.session.add(utub_url_tag)
                print(
                    f"Adding {tag} to {url.standalone_url.url_string} in {utub.name}, ID={utub.id}"
                )

    db.session.commit()
