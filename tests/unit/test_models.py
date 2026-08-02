import jwt
import pytest
from flask import current_app

from backend import db
from backend.extensions.url_validation.url_validator import UrlValidator
from backend.models.utils import VerifyTokenResponse
from backend.models.utub_tags import Utub_Tags
from backend.models.urls import Urls
from backend.models.users import User_Role, Users
from backend.models.utubs import Utubs
from backend.splash.utils import verify_token
from backend.utils.strings.config_strs import CONFIG_ENVS
from backend.utils.strings.email_validation_strs import EMAILS

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


def test_user_is_admin_helper(app):
    """
    GIVEN a Users instance
    WHEN role is explicitly set to User_Role.ADMIN versus left at the default
    THEN is_admin() returns True only for the admin role
    """
    with app.app_context():
        admin_user = Users(
            username=new_user["username"],
            email=new_user["email"],
            plaintext_password=new_user["password"],
        )
        admin_user.role = User_Role.ADMIN
        assert admin_user.is_admin()

        regular_user = Users(
            username=new_user["username"],
            email=new_user["email"],
            plaintext_password=new_user["password"],
        )
        regular_user.role = User_Role.USER
        assert not regular_user.is_admin()


def test_stage_email_change_lowercases_pending_email(app):
    """
    GIVEN an existing user
    WHEN stage_email_change is called with a mixed-case new email
    THEN pending_email is stored lowercased and the live email is untouched
    """
    with app.app_context():
        user = Users(
            username=new_user["username"],
            email=new_user["email"],
            plaintext_password=new_user["password"],
        )

        user.stage_email_change("New.Address@Example.COM")

        assert user.pending_email == "new.address@example.com"
        assert user.email == new_user["email"].lower()


def test_finalize_email_change_swaps_pending_into_live_and_clears(app):
    """
    GIVEN a user with a staged pending_email
    WHEN finalize_email_change is called
    THEN the pending email becomes the live email and pending_email is cleared
    """
    with app.app_context():
        user = Users(
            username=new_user["username"],
            email=new_user["email"],
            plaintext_password=new_user["password"],
        )
        user.stage_email_change("new.address@example.com")

        user.finalize_email_change()

        assert user.email == "new.address@example.com"
        assert user.pending_email is None


def test_get_email_change_token_round_trips_through_verify_token(app):
    """
    GIVEN a persisted user with a staged pending_email
    WHEN a change-email token is minted and verified with the CHANGE_EMAIL key
    THEN verify_token resolves the same user and reports the token unexpired
    """
    with app.app_context():
        user = Users(
            username=new_user["username"],
            email=new_user["email"],
            plaintext_password=new_user["password"],
        )
        user.stage_email_change("new.address@example.com")
        db.session.add(user)
        db.session.commit()

        token = user.get_email_change_token()

        assert verify_token(token, EMAILS.CHANGE_EMAIL) == VerifyTokenResponse(
            user=user, is_expired=False, failed_due_to_exception=False
        )


def test_change_email_token_is_purpose_isolated_from_validate_email(app):
    """
    GIVEN a change-email token (carrying only the CHANGE_EMAIL claim)
    WHEN it is fed to verify_token with the VALIDATE_EMAIL key
    THEN it cannot resolve a user — the validate-email claim is absent, so the
        registration consume path can never cross-consume a change-email token
    """
    with app.app_context():
        user = Users(
            username=new_user["username"],
            email=new_user["email"],
            plaintext_password=new_user["password"],
        )
        user.stage_email_change("new.address@example.com")
        db.session.add(user)
        db.session.commit()

        token = user.get_email_change_token()

        with pytest.raises(KeyError):
            verify_token(token, EMAILS.VALIDATE_EMAIL)


def test_get_email_change_token_embeds_target_email_claim(app):
    """
    GIVEN a user who staged a new pending email
    WHEN the change-email token is independently decoded
    THEN the CHANGE_EMAIL_TARGET claim holds the staged (lowercased) address
    """
    with app.app_context():
        user = Users(
            username=new_user["username"],
            email=new_user["email"],
            plaintext_password=new_user["password"],
        )
        user.stage_email_change("New.Address@Example.com")

        token = user.get_email_change_token()
        payload = jwt.decode(
            token,
            key=current_app.config[CONFIG_ENVS.SECRET_KEY],
            algorithms=[EMAILS.ALGORITHM],
        )

        assert payload[EMAILS.CHANGE_EMAIL] == new_user["username"]
        assert payload[EMAILS.CHANGE_EMAIL_TARGET] == "new.address@example.com"


def test_change_email_token_is_detectably_stale_after_repeated_staging(app):
    """
    GIVEN a change-email token minted for one pending email
    WHEN the user stages a different pending email before the link is clicked
    THEN the decoded CHANGE_EMAIL_TARGET claim no longer matches the user's
        current pending_email, marking the first token as stale/superseded
    """
    with app.app_context():
        user = Users(
            username=new_user["username"],
            email=new_user["email"],
            plaintext_password=new_user["password"],
        )
        user.stage_email_change("first@example.com")
        first_token = user.get_email_change_token()

        user.stage_email_change("second@example.com")

        stale_payload = jwt.decode(
            first_token,
            key=current_app.config[CONFIG_ENVS.SECRET_KEY],
            algorithms=[EMAILS.ALGORITHM],
        )
        assert stale_payload[EMAILS.CHANGE_EMAIL_TARGET] == "first@example.com"
        assert stale_payload[EMAILS.CHANGE_EMAIL_TARGET] != user.pending_email


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
            normalized_url=url_validator.normalize_url(new_url["url_string"]),
            current_user_id=new_url["creator"],
        )

        assert new_url_object.url_string == url_validator.normalize_url(
            new_url["url_string"]
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
