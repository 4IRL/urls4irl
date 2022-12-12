import pytest
from urls4irl.models import User, Utub, URLS, Tags
from urls4irl.url_validation import check_request_head

new_user = {
    "username": "FakeUserName1234",
    "email": "FakeUserName123@email.com",
    "confirm_email": "FakeUserName123@email.com",
    "password": "FakePassword1234",
    "confirm_password": "FakePassword1234"
}

new_utub = {
    "name": "MyNewUTub",
    "creator": 1,
    "description": "This is my first UTub!"
}

new_url = {
    "url_string": "google.com",
    "creator": 1
}

new_tag = {
    "tag_string": "Cool",
    "creator": 1,
}

def test_user_model():
    """
    GIVEN a new user model
    WHEN a new User model is created
    THEN ensure all fields are filled out correctly
    """
    new_user_object = User(username=new_user["username"], 
                            email=new_user["email"], 
                            plaintext_password=new_user["password"],
                            email_confirm=True)

    assert new_user_object.username == new_user["username"]
    assert new_user_object.password != new_user["password"]
    assert new_user_object.email == new_user["email"]
    assert new_user_object.email_confirm is True
    assert new_user_object.is_password_correct(new_user["password"]) is True
    assert len(new_user_object.utubs_created) == 0
    assert len(new_user_object.utub_urls) == 0
    assert len(new_user_object.utubs_is_member_of) == 0

    new_user_object = User(username=new_user["username"], 
                            email=new_user["email"], 
                            plaintext_password=new_user["password"])

    assert new_user_object.email_confirm is False

def test_utub_model():
    """
    GIVEN a new UTub model
    WHEN a new UTub model is created
    THEN ensure all fields are filled out correctly
    """
    new_utub_object = Utub(name=new_utub["name"],
                            utub_creator=new_utub["creator"],
                            utub_description=new_utub["description"])

    assert new_utub_object.name == new_utub["name"]
    assert new_utub_object.utub_creator == new_utub["creator"]
    assert new_utub_object.utub_description == new_utub["description"]
    assert len(new_utub_object.members) == 0
    assert len(new_utub_object.utub_urls) == 0
    assert len(new_utub_object.utub_url_tags) == 0

def test_url_model():
    """
    GIVEN a new URL model
    WHEN a new URL model is created
    THEN ensure all fields are filled out correctly
    """
    new_url_object = URLS(normalized_url=check_request_head(new_url["url_string"]),
                            current_user_id=new_url["creator"])

    assert new_url_object.url_string == check_request_head(new_url["url_string"])
    assert new_url_object.created_by == new_url["creator"]
    assert len(new_url_object.url_tags) == 0

def test_tag_model():
    """
    GIVEN a new Tag model
    WHEN a new Tag model is created
    THEN ensure all fields are filled out correctly
    """
    new_tag_object = Tags(tag_string=new_tag["tag_string"], created_by=new_tag["creator"])

    assert new_tag_object.tag_string == new_tag["tag_string"]
    assert new_tag_object.created_by == new_tag["creator"]
