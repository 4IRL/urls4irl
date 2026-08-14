from flask import Flask
import pytest

from backend import db
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.utils.constants import TAG_CONSTANTS
from backend.utils.strings import model_strs
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
        all_utubs: list[Utubs] = Utubs.query.order_by(Utubs.id).all()
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
    _add_one_tag_to_each_utub(app)


@pytest.fixture
def add_one_tag_to_each_utub_after_all_users_added(
    app: Flask, every_user_in_every_utub
):
    """
    Adds one tag to each UTub, generating a single UtubTag entry for each UTub.

    Args:
        app (Flask): The Flask client providing the app context
        every_user_in_every_utub (pytest fixture): Adds every user to every UTub
    """
    _add_one_tag_to_each_utub(app)


def _add_one_tag_to_each_utub(app: Flask):
    with app.app_context():
        all_utubs: list[Utubs] = Utubs.query.order_by(Utubs.id).all()

        for idx, utub in enumerate(all_utubs):
            tag = all_tags[idx]
            new_tag_in_utub = Utub_Tags(
                utub_id=utub.id,
                tag_string=tag[model_strs.TAG_STRING],
                created_by=utub.utub_creator,
            )
            db.session.add(new_tag_in_utub)

        db.session.commit()


@pytest.fixture
def add_mixed_tag_state_urls_in_first_utub(
    app: Flask, add_all_urls_and_users_to_each_utub_no_tags
):
    """
    Seed a mixed per-URL tag state on the first UTub (created by the first user),
    so the multi-URL tag-apply endpoint can be exercised for per-URL partial
    success in one request:

    - URL A (first by id):  no tags
    - URL B (second by id): exactly one tag applied
    - URL C (third by id):  at the per-URL MAX_URL_TAGS limit (skipped on apply)

    Builds on ``add_all_urls_and_users_to_each_utub_no_tags`` (three URLs and all
    members in each UTub) and layers tag associations via direct ``db.session``
    inserts, reusing ``tests.models_for_test.all_tags`` for the single-tag URL.
    The first UTub is created by the first user, so a test that logs in as the
    first user (``login_first_user_without_register``) is its creator.

    Args:
        app (Flask): The Flask client providing an app context
        add_all_urls_and_users_to_each_utub_no_tags (pytest fixture): Adds all
            URLs and all members to each UTub, with no tags on any URL
    """
    with app.app_context():
        first_utub: Utubs = Utubs.query.order_by(Utubs.id).first()
        url_ids = [
            utub_url.id
            for utub_url in Utub_Urls.query.filter(Utub_Urls.utub_id == first_utub.id)
            .order_by(Utub_Urls.id)
            .all()
        ]
        url_b_id, url_c_id = url_ids[1], url_ids[2]

        # URL B: exactly one applied tag (reuse a canonical test tag string).
        single_tag = Utub_Tags(
            utub_id=first_utub.id,
            tag_string=all_tags[0][model_strs.TAG_STRING],
            created_by=first_utub.utub_creator,
        )
        db.session.add(single_tag)
        db.session.flush()
        db.session.add(
            Utub_Url_Tags(
                utub_id=first_utub.id,
                utub_url_id=url_b_id,
                utub_tag_id=single_tag.id,
            )
        )

        # URL C: filled to the per-URL tag limit so it is skipped over-limit.
        for index in range(TAG_CONSTANTS.MAX_URL_TAGS):
            limit_tag = Utub_Tags(
                utub_id=first_utub.id,
                tag_string=f"limit_seed_{url_c_id}_{index}",
                created_by=first_utub.utub_creator,
            )
            db.session.add(limit_tag)
            db.session.flush()
            db.session.add(
                Utub_Url_Tags(
                    utub_id=first_utub.id,
                    utub_url_id=url_c_id,
                    utub_tag_id=limit_tag.id,
                )
            )

        db.session.commit()
