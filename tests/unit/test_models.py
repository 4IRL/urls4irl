import pytest

from src.extensions.url_validation.url_validator import UrlValidator
from src.models.utub_tags import Utub_Tags
from src.models.urls import Possible_Url_Validation, Urls
from src.models.users import Users
from src.models.utubs import Utubs

pytestmark = pytest.mark.unit

new_user = {
    "username": "FakeUserName1234",
    "email": "FakeUserName123@email.com",
    "confirm_email": "FakeUserName123@email.com",
    "password": "FakePassword1234",
    "confirm_password": "FakePassword1234",
}

new_utub = {"name": "MyNewUTub", "creator": 1, "description": "This is my first UTub!"}

new_url = {"url_string": "google.com", "creator": 1}

new_tag = {"tag_string": "Cool", "creator": 1, "utub_id": 1}


def test_user_model(app):
    """
    GIVEN a new user model
    WHEN a new User model is created
    THEN ensure all fields are filled out correctly
    """
    with app.app_context():
        new_user_object = Users(
            username=new_user["username"],
            email=new_user["email"],
            plaintext_password=new_user["password"],
        )

        assert new_user_object.username == new_user["username"]
        assert new_user_object.password != new_user["password"]
        assert new_user_object.email == new_user["email"].lower()
        assert new_user_object.is_password_correct(new_user["password"]) is True
        assert len(new_user_object.utubs_is_member_of) == 0
        assert new_user_object.email_confirm is None


def test_utub_model(app):
    """
    GIVEN a new UTub model
    WHEN a new UTub model is created
    THEN ensure all fields are filled out correctly
    """
    with app.app_context():
        new_utub_object = Utubs(
            name=new_utub["name"],
            utub_creator=new_utub["creator"],
            utub_description=new_utub["description"],
        )

        assert new_utub_object.name == new_utub["name"]
        assert new_utub_object.utub_creator == new_utub["creator"]
        assert new_utub_object.utub_description == new_utub["description"]
        assert len(new_utub_object.members) == 0
        assert len(new_utub_object.utub_urls) == 0
        assert len(new_utub_object.utub_url_tags) == 0


def test_url_model(app):
    """
    GIVEN a new URL model
    WHEN a new URL model is created
    THEN ensure all fields are filled out correctly
    """
    url_validator = UrlValidator()
    with app.app_context():
        new_url_object = Urls(
            normalized_url=url_validator.validate_url(
                new_url["url_string"],
            )[0],
            current_user_id=new_url["creator"],
            is_validated=Possible_Url_Validation.VALIDATED.value,
        )

        assert (
            new_url_object.url_string
            == url_validator.validate_url(new_url["url_string"])[0]
        )
        assert new_url_object.created_by == new_url["creator"]


def test_tag_model(app):
    """
    GIVEN a new Tag model
    WHEN a new Tag model is created
    THEN ensure all fields are filled out correctly
    """
    with app.app_context():
        new_tag_object = Utub_Tags(
            utub_id=new_tag["utub_id"],
            tag_string=new_tag["tag_string"],
            created_by=new_tag["creator"],
        )

        assert new_tag_object.utub_id == new_tag["utub_id"]
        assert new_tag_object.tag_string == new_tag["tag_string"]
        assert new_tag_object.created_by == new_tag["creator"]
