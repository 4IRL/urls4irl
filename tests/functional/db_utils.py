from typing import Tuple
from flask import Flask
from flask.testing import FlaskCliRunner

from src import db
from src.models.urls import Urls
from src.models.users import Users
from src.models.utub_members import Member_Role, Utub_Members
from src.models.utub_tags import Utub_Tags
from src.models.utub_urls import Utub_Urls
from src.models.utub_url_tags import Utub_Url_Tags
from src.models.utubs import Utubs
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS


def get_utub_this_user_created(app: Flask, user_id: int) -> Utubs:
    with app.app_context():
        return Utubs.query.filter(Utubs.utub_creator == user_id).first()


def get_utub_this_user_did_not_create(app: Flask, user_id: int) -> Utubs:
    with app.app_context():
        return Utubs.query.filter(Utubs.utub_creator != user_id).first()


def get_url_in_utub(app: Flask, utub_id: int) -> Utub_Urls:
    with app.app_context():
        return Utub_Urls.query.filter(Utub_Urls.utub_id == utub_id).first()


def add_mock_urls(runner: FlaskCliRunner, urls: list[str]):
    args = (
        ["addmock", "url"]
        + urls
        + [
            "--no-dupes",
        ]
    )
    runner.invoke(args=args)


def update_utub_to_empty_desc(app: Flask, utub_id: int):
    with app.app_context():
        utub: Utubs = Utubs.query.get(utub_id)
        utub.utub_description = ""
        db.session.commit()


def create_test_searchable_utubs(app: Flask, test_user_id: int) -> dict[str, int]:
    """
    Assumes users created. Creates sample UTubs, each user owns one.
    """
    utub_names = UI_TEST_STRINGS.UTUB_SEARCH_NAMES
    utub_ids = {key: 0 for key in utub_names}
    with app.app_context():
        user: Users = Users.query.get(test_user_id)
        for utub_name in utub_names:
            new_utub = Utubs(name=utub_name, utub_description="", utub_creator=user.id)
            db.session.add(new_utub)
            db.session.commit()
            utub_ids[utub_name] = new_utub.id

            utub_member = Utub_Members(utub_id=new_utub.id, user_id=test_user_id)
            utub_member.utub_id = new_utub.id
            utub_member.user_id = test_user_id
            utub_member.member_role = Member_Role.CREATOR
            db.session.add(utub_member)
            db.session.commit()

    return utub_ids


def get_other_member_in_utub(app: Flask, utub_id: int, current_user_id: int) -> Users:
    with app.app_context():
        other_member: Utub_Members = Utub_Members.query.filter(
            Utub_Members.user_id != current_user_id, Utub_Members.utub_id == utub_id
        ).first()
        return other_member.to_user


def get_utub_url_id_for_added_url_in_utub_as_member(
    app: Flask, utub_id: int, user_id: int
) -> int:
    with app.app_context():
        url_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id, Utub_Urls.user_id == user_id
        ).first()
        return url_in_utub.id


def get_newly_added_utub_url_id_by_url_string(
    app: Flask, utub_id: int, url_string: str
) -> int:
    with app.app_context():
        url: Urls = Urls.query.filter(Urls.url_string == url_string).first()
        assert url is not None
        utub_url: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.url_id == url.id, Utub_Urls.utub_id == utub_id
        ).first()
        assert utub_url is not None
        return utub_url.id


def get_tag_string_already_on_url_in_utub_and_delete(
    app: Flask, utub_id: int, utub_url_id: int
) -> str:
    with app.app_context():
        utub_url_tag: Utub_Url_Tags = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id, Utub_Url_Tags.utub_url_id == utub_url_id
        ).all()
        tag_string = utub_url_tag[0].utub_tag_item.tag_string
        db.session.delete(utub_url_tag[1])
        db.session.commit()
        return tag_string


def get_tag_on_url_in_utub(app: Flask, utub_id: int, utub_url_id: int) -> Utub_Url_Tags:
    with app.app_context():
        return Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id, Utub_Url_Tags.utub_url_id == utub_url_id
        ).first()


def add_tag_to_utub_user_created(
    app: Flask, utub_id: int, user_id: int, tag_string: str
) -> Utub_Tags:
    with app.app_context():
        new_tag: Utub_Tags = Utub_Tags(
            utub_id=utub_id, tag_string=tag_string, created_by=user_id
        )
        db.session.add(new_tag)
        db.session.commit()

        return Utub_Tags.query.filter(Utub_Tags.tag_string == tag_string).first()


def add_two_tags_across_urls_in_utub(
    app: Flask, utub_id: int, first_tag_id: int, second_tag_id: int
) -> Tuple[int, int, int]:
    with app.app_context():
        utub_urls: list[Utub_Urls] = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id
        ).all()
        num_utub_urls = len(utub_urls)
        urls_for_first_tag = utub_urls[: len(utub_urls) - 1]
        num_urls_for_first_tag = len(urls_for_first_tag)
        urls_for_second_tag = urls_for_first_tag[: len(urls_for_first_tag) // 2]
        num_urls_for_second_tag = len(urls_for_second_tag)

        for first_tag_url in urls_for_first_tag:
            url_id = first_tag_url.id
            new_url_tag = Utub_Url_Tags(
                utub_id=utub_id, utub_url_id=url_id, utub_tag_id=first_tag_id
            )
            db.session.add(new_url_tag)

            if first_tag_url in urls_for_second_tag:
                new_url_tag = Utub_Url_Tags(
                    utub_id=utub_id, utub_url_id=url_id, utub_tag_id=second_tag_id
                )
                db.session.add(new_url_tag)
        db.session.commit()
        return num_utub_urls, num_urls_for_first_tag, num_urls_for_second_tag

def count_urls_with_tag_applied_by_tag_id(
    app: Flask,
    tag_id: int,
) -> int:
    """
    Counts the number of URLs displayed with a specific tag applied by its ID.
    """
    with app.app_context():
        return Utub_Url_Tags.query.filter(Utub_Url_Tags.utub_tag_id == tag_id).count()


def count_urls_with_tag_applied_by_tag_string(
    app: Flask,
    utub_id: int,
    tag_text: str,
) -> int:
    """
    Counts the number of URLs displayed with a specific tag applied by its string and UTub ID.
    """
    with app.app_context():
        utub_tag: Utub_Tags = Utub_Tags.query.filter(
            Utub_Tags.utub_id == utub_id,
            Utub_Tags.tag_string == tag_text,
        ).first()

        return (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id,
                Utub_Url_Tags.utub_tag_id == utub_tag.id,
            ).count()
            if utub_tag
            else 0
        )
