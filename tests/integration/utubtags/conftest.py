from flask import Flask
import pytest

from src import db
from src.models.tags import Tags
from src.models.utub_url_tags import Utub_Url_Tags
from src.models.utubs import Utubs


@pytest.fixture
def add_one_url_to_each_utub_one_tag(
    app: Flask, add_one_url_to_each_utub_no_tags, add_tags_to_database
):
    """
    Add a single valid tag to each URL in each UTub.
    The ID of the UTub, User, and related URL, and tag are all the same.

    Utub with ID of 1, created by User ID of 1, with URL ID of 1, with tag ID of 1

    Args:
        app (Flask): The Flask client providing an app context
        add_one_url_to_each_utub_no_tags (pytest fixture): Adds one url to each UTub with same ID as creator
        add_tags_to_database (pytest fixture): Adds all test tags to the database
    """
    with app.app_context():
        all_utubs: list[Utubs] = Utubs.query.all()
        tag = Tags.query.first()

        for utub in all_utubs:
            url_in_utub = utub.utub_urls[0]

            new_tag_url_utub_association = Utub_Url_Tags()
            new_tag_url_utub_association.utub_containing_this_tag = utub
            new_tag_url_utub_association.tagged_url = url_in_utub
            new_tag_url_utub_association.tag_item = tag
            new_tag_url_utub_association.utub_id = utub.id
            new_tag_url_utub_association.utub_url_id = url_in_utub.id
            new_tag_url_utub_association.tag_id = tag.id
            utub.utub_url_tags.append(new_tag_url_utub_association)

        db.session.commit()


@pytest.fixture
def add_five_tags_to_db_from_same_user(
    app: Flask, add_one_url_and_all_users_to_each_utub_no_tags
):
    """
    Adds five additional tags to the database without associating them with any URLs. Assumes they are
    all added by User ID == 1

    Args:
        app (Flask): The Flask client providing an app context
        add_one_url_and_all_users_to_each_utub_no_tags (pytest fixture): Adds all users to all UTubs, each UTub containing
            a single URL added by the creator
    """
    five_tags_to_add = ("Hello", "Good", "Bad", "yes", "no")
    with app.app_context():
        for tag in five_tags_to_add:
            new_tag = Tags(tag_string=tag, created_by=1)
            db.session.add(new_tag)
        db.session.commit()
