from flask_sqlalchemy import SQLAlchemy

from src.mocks.mock_constants import MOCK_URL_STRINGS
from src.models.urls import Possible_Url_Validation, Urls
from src.models.utubs import Utubs
from src.models.utub_members import Utub_Members
from src.models.utub_urls import Utub_Urls


def generate_mock_urls(db: SQLAlchemy):
    """
    Generates mock URLs, adds them to database if not already added,
    and then adds those to each UTub.

    Args:
        db (SQLAlchemy): Database engine and connection for committing mock data
    """
    all_utubs: list[Utubs] = Utubs.query.all()

    for utub in all_utubs:
        utub_members: list[Utub_Members] = utub.members

        for member, url in zip(utub_members, MOCK_URL_STRINGS):
            url_to_add = Urls.query.filter(Urls.url_string == url).first()
            if url_to_add is not None:
                print(f"Already added {url} to database")
            else:
                url_to_add = Urls(
                    normalized_url=url,
                    current_user_id=member.user_id,
                    is_validated=Possible_Url_Validation.VALIDATED.value,
                )
                db.session.add(url_to_add)
                print(f"Adding {url} to database")

            if (
                Utub_Urls.query.filter(
                    Utub_Urls.utub_id == utub.id,
                    Utub_Urls.url_id == url_to_add.id,
                ).first()
                is not None
            ):
                print(f"Already added {url} to {utub.name}, ID={utub.id}")
                continue

            new_utub_url: Utub_Urls = Utub_Urls()
            new_utub_url.utub_id = utub.id
            new_utub_url.user_id = member.user_id
            new_utub_url.url_id = url_to_add.id
            new_utub_url.url_title = f"This is {url_to_add.url_string}."
            db.session.add(new_utub_url)
            print(
                f"Adding {url} to {utub.name}, ID={utub.id}, by {member.to_user.username}"
            )

    db.session.commit()


def generate_custom_mock_url(db: SQLAlchemy, urls_to_add: list[str]):
    all_utubs: list[Utubs] = Utubs.query.all()

    for utub in all_utubs:
        utub_members: list[Utub_Members] = utub.members
        creator = [
            member for member in utub_members if member.user_id == utub.utub_creator
        ][0]

        for url in urls_to_add:
            url_to_add = Urls.query.filter(Urls.url_string == url).first()
            if url_to_add is not None:
                print(f"Already added {url} to database")
            else:
                url_to_add = Urls(
                    normalized_url=url,
                    current_user_id=utub.utub_creator,
                    is_validated=Possible_Url_Validation.VALIDATED.value,
                )
                db.session.add(url_to_add)
                print(f"Adding {url} to database")

            if (
                Utub_Urls.query.filter(
                    Utub_Urls.utub_id == utub.id,
                    Utub_Urls.user_id == utub.utub_creator,
                    Utub_Urls.url_id == url_to_add.id,
                ).first()
                is not None
            ):
                print(
                    f"Already added {url} to {utub.name}, ID={utub.id}, by {creator.to_user.username}"
                )
                continue

            new_utub_url: Utub_Urls = Utub_Urls()
            new_utub_url.utub_id = utub.id
            new_utub_url.user_id = utub.utub_creator
            new_utub_url.url_id = url_to_add.id
            new_utub_url.url_title = f"This is {url_to_add.url_string}."
            db.session.add(new_utub_url)
            print(
                f"Adding {url} to {utub.name}, ID={utub.id}, by {creator.to_user.username}"
            )

    db.session.commit()
