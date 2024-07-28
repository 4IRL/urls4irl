from flask import Flask
import pytest

from src import db
from src.models.utub_tags import Utub_Tags
from src.models.utub_url_tags import Utub_Url_Tags
from src.models.utubs import Utubs
from src.utils.strings import model_strs
from tests.models_for_test import all_tags


@pytest.fixture
def add_one_url_to_each_utub_one_tag_to_each_url_all_tags_in_utub(
    app: Flask, add_one_url_to_each_utub_no_tags, add_tags_to_utubs
):
    """
    Add a single valid tag to each URL in each UTub, after adding all tags to each UTub.
    The ID of the UTub, User, and related URL, and tag are all the same.

    Utub with ID of 1, created by User ID of 1, with URL ID of 1, with tag ID of 1

    Args:
        app (Flask): The Flask client providing an app context
        add_one_url_to_each_utub_no_tags (pytest fixture): Adds one url to each UTub with same ID as creator
        add_tags_to_all_utubs (pytest fixture): Adds all test tags to each UTub
    """
    with app.app_context():
        all_utubs: list[Utubs] = Utubs.query.all()
        tag = all_tags[0]

        for utub in all_utubs:
            url_in_utub = utub.utub_urls[0]
            tag_in_utub = Utub_Tags.query.filter(
                Utub_Tags.utub_id == utub.id,
                Utub_Tags.tag_string == tag[model_strs.TAG_STRING],
            ).first()

            new_tag_url_utub_association = Utub_Url_Tags()
            new_tag_url_utub_association.utub_id = utub.id
            new_tag_url_utub_association.utub_url_id = url_in_utub.id
            new_tag_url_utub_association.utub_tag_id = tag_in_utub.id
            db.session.add(new_tag_url_utub_association)

        db.session.commit()


@pytest.fixture
def add_one_tag_to_each_utub_after_one_url_added(
    app: Flask, add_one_url_to_each_utub_no_tags
):
    """
    Add a single valid tag to each UTub

    Args:
        app (Flask): The Flask client providing an app context
        add_one_url_to_each_utub_no_tags (pytest fixture): Adds one url to each UTub with same ID as creator
    """
    with app.app_context():
        all_utubs: list[Utubs] = Utubs.query.all()

        for idx, utub in enumerate(all_utubs):
            tag = all_tags[idx]
            new_tag_in_utub = Utub_Tags(
                utub_id=utub.id,
                tag_string=tag[model_strs.TAG_STRING],
                created_by=utub.utub_creator,
            )
            db.session.add(new_tag_in_utub)

        db.session.commit()
