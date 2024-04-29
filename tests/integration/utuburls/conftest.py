from flask import Flask
import pytest

from src import db
from src.models.tags import Tags
from src.models.urls import Urls
from src.models.url_tags import Url_Tags
from src.models.users import Users
from src.models.utubs import Utubs
from src.models.utub_members import Utub_Members
from src.models.utub_urls import Utub_Urls


@pytest.fixture
def add_first_user_to_second_utub_and_add_tags_remove_first_utub(
    app: Flask, add_one_url_to_each_utub_no_tags, add_tags_to_database
):
    """
    After each user has made their own UTub, with one URL added by that user to each UTub,
    now add first user to second UTub as UTub member, and add tags to all currently added URLs

    Remove the first UTub so first user is no longer creator of a UTub

    Utub with ID of 2, created by User ID of 2, with URL ID of 2, now has member 1
    All URLs have all tags associated with them

    Args:
        app (Flask): The Flask client providing an app context
        add_one_url_to_each_utub_no_tags (pytest fixture): Has each User make their own UTub, and has
            that user add a URL to their UTub
        add_tags_to_database (pytest.fixture): Adds all tags to the database for easy adding to URLs
    """
    with app.app_context():
        first_utub = Utubs.query.get(1)
        db.session.delete(first_utub)
        second_utub = Utubs.query.get(2)
        all_tags = Tags.query.all()

        # Add a single missing users to this UTub
        new_user = Users.query.get(1)
        new_utub_user_association = Utub_Members()
        new_utub_user_association.to_user = new_user
        new_utub_user_association.utub_id = second_utub.id
        second_utub.members.append(new_utub_user_association)
        db.session.add(new_utub_user_association)

        urls_in_utub: list[Utub_Urls] = [utub_url for utub_url in second_utub.utub_urls]

        for url_in_utub in urls_in_utub:
            url_id = url_in_utub.url_id
            url_in_this_utub = url_in_utub.standalone_url

            for tag in all_tags:
                new_tag_url_utub_association = Url_Tags()
                new_tag_url_utub_association.utub_containing_this_tag = second_utub
                new_tag_url_utub_association.tagged_url = url_in_this_utub
                new_tag_url_utub_association.tag_item = tag
                new_tag_url_utub_association.utub_id = second_utub.id
                new_tag_url_utub_association.url_id = url_id
                new_tag_url_utub_association.tag_id = tag.id
                second_utub.utub_url_tags.append(new_tag_url_utub_association)

        db.session.commit()


@pytest.fixture
def add_two_url_and_all_users_to_each_utub_no_tags(
    app: Flask, add_one_url_and_all_users_to_each_utub_no_tags
):
    """
    After each user has made their own UTub, with one URL added by that user to each UTub,
    now add all other users as members to each UTub.

    Utub with ID of 1, created by User ID of 1, with URL ID of 1, now has members 2 and 3 included,
    now had URL ID of 2 also included in it

    Args:
        app (Flask): The Flask client providing an app context
        add_one_url_to_each_utub_no_tags (pytest fixture): Has each User make their own UTub, and has
            that user add a URL to their UTub
    """
    with app.app_context():
        current_utubs = Utubs.query.all()
        current_users = Users.query.all()

        # Add all missing users to this UTub
        for utub in current_utubs:
            # Get URL in current UTUb
            current_utub_url = Utub_Urls.query.filter_by(utub_id=utub.id).first()
            current_utub_id = current_utub_url.url_id
            new_url = Urls.query.filter_by(id=((current_utub_id % 3) + 1)).first()

            new_utub_url_user_association = Utub_Urls()

            new_utub_url_user_association.standalone_url = new_url
            new_utub_url_user_association.url_id = new_url.id

            new_utub_url_user_association.utub = utub
            new_utub_url_user_association.utub_id = utub.id

            user_added = [user for user in current_users if user.id == new_url.id].pop()
            new_utub_url_user_association.user_that_added_url = user_added
            new_utub_url_user_association.user_id = new_url.id

            new_utub_url_user_association.url_title = f"This is {new_url.url_string}"

            db.session.add(new_utub_url_user_association)

        db.session.commit()


@pytest.fixture
def add_one_url_and_all_users_to_each_utub_with_all_tags(
    app: Flask, add_one_url_and_all_users_to_each_utub_no_tags, add_tags_to_database
):
    """
    After each user has made their own UTub, with one URL added by that user to each UTub,
    now add all other users as members to each UTub.

    Utub with ID of 1, created by User ID of 1, with URL ID of 1, now has members 2 and 3 included

    Args:
        app (Flask): The Flask client providing an app context
        add_one_url_to_each_utub_no_tags (pytest fixture): Has each User make their own UTub, and has
            that user add a URL to their UTub
    """
    with app.app_context():
        current_utubs = Utubs.query.all()
        current_tags = Tags.query.all()

        # Add all missing users to this UTub
        for utub in current_utubs:
            current_utub_url = [
                utub_url.standalone_url for utub_url in utub.utub_urls
            ].pop()

            for tag in current_tags:
                new_tag_url_utub_association = Url_Tags()
                new_tag_url_utub_association.utub_containing_this_tag = utub
                new_tag_url_utub_association.tagged_url = current_utub_url
                new_tag_url_utub_association.tag_item = tag
                new_tag_url_utub_association.utub_id = utub.id
                new_tag_url_utub_association.url_id = current_utub_url.id
                new_tag_url_utub_association.tag_id = tag.id
                utub.utub_url_tags.append(new_tag_url_utub_association)

        db.session.commit()
