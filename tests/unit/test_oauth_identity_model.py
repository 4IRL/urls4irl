import pytest

from backend import db
from backend.models.user_oauth_identities import UserOAuthIdentity
from backend.models.users import Users
from backend.splash.services.oauth.constants import Provider

pytestmark = pytest.mark.unit

_USERNAME = "oauthonly"
_EMAIL = "oauthonly@example.com"
_PROVIDER = Provider.GOOGLE
_PROVIDER_SUBJECT = "google-subject-123"


def test_user_without_password_has_null_password():
    """
    GIVEN a Users model constructed with no plaintext_password
    WHEN the instance is created
    THEN its password attribute is None
    """
    user = Users(username=_USERNAME, email=_EMAIL)
    assert user.password is None


def test_is_password_correct_returns_false_when_password_is_none():
    """
    GIVEN a password-less (OAuth-only) Users model
    WHEN is_password_correct is called with any string
    THEN it returns False without invoking the werkzeug hash comparison
    """
    user = Users(username=_USERNAME, email=_EMAIL)
    assert user.password is None
    assert user.is_password_correct("anything") is False


def test_oauth_identity_relationship_loads(app):
    """
    GIVEN a password-less Users model with one appended UserOAuthIdentity
    WHEN the user is committed and re-queried
    THEN the oauth_identities relationship loads the linked identity and it
        back-references the owning user
    """
    with app.app_context():
        user = Users(username=_USERNAME, email=_EMAIL)
        user.oauth_identities.append(
            UserOAuthIdentity(
                provider=_PROVIDER,
                provider_subject=_PROVIDER_SUBJECT,
                email=_EMAIL,
            )
        )
        db.session.add(user)
        db.session.commit()
        user_id = user.id

        db.session.expire_all()

        reloaded_user = Users.query.get(user_id)
        assert len(reloaded_user.oauth_identities) == 1
        identity = reloaded_user.oauth_identities[0]
        assert identity.provider == _PROVIDER
        assert identity.provider_subject == _PROVIDER_SUBJECT
        assert identity.user.id == user_id
