from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from backend import db
from backend.models.user_oauth_identities import UserOAuthIdentity
from backend.models.users import Users
from backend.splash.services.oauth.account_service import (
    EmailAlreadyRegisteredError,
    find_or_create_oauth_user,
    generate_unique_username_from_email,
)
from backend.splash.services.oauth.constants import Provider
from backend.utils.constants import USER_CONSTANTS

pytestmark = pytest.mark.unit

_PROVIDER = Provider.GOOGLE
_SUBJECT = "google-subject-123"
_EMAIL = "john.doe@example.com"
_LOCAL_PART = "john.doe"


# ---------------------------------------------------------------------------
# generate_unique_username_from_email
# ---------------------------------------------------------------------------
def test_generate_username_clean_local_part_passthrough(app):
    """
    GIVEN an email whose local-part is already a valid, short username
    WHEN generate_unique_username_from_email is called
    THEN it returns the local-part unchanged (no collision, no suffix)
    """
    with app.app_context():
        assert generate_unique_username_from_email(_EMAIL) == _LOCAL_PART


def test_generate_username_plain_username_input_passthrough(app):
    """
    GIVEN an input with no '@' (e.g. a GitHub preferred_username)
    WHEN generate_unique_username_from_email is called
    THEN the full input is used as the base candidate
    """
    with app.app_context():
        assert generate_unique_username_from_email("johndoe") == "johndoe"


def test_generate_username_truncates_over_length_local_part(app):
    """
    GIVEN a local-part longer than the physical username column limit
    WHEN generate_unique_username_from_email is called with no collision
    THEN the result is truncated to at most MAX_USERNAME_LENGTH_ACTUAL (25)
    """
    with app.app_context():
        long_local_part = "a" * 40
        result = generate_unique_username_from_email(f"{long_local_part}@example.com")
        assert result == "a" * USER_CONSTANTS.MAX_USERNAME_LENGTH_ACTUAL
        assert len(result) == USER_CONSTANTS.MAX_USERNAME_LENGTH_ACTUAL


def test_generate_username_collision_appends_numeric_suffix(app):
    """
    GIVEN an existing user whose username equals the base candidate
    WHEN generate_unique_username_from_email is called
    THEN the next candidate appends '1' and the combined length stays within
        MAX_USERNAME_LENGTH (20), well within the 25-char column limit
    """
    with app.app_context():
        existing = Users(username=_LOCAL_PART, email="existing@example.com")
        db.session.add(existing)
        db.session.commit()

        result = generate_unique_username_from_email(_EMAIL)
        assert result == f"{_LOCAL_PART}1"
        assert len(result) <= USER_CONSTANTS.MAX_USERNAME_LENGTH


def test_generate_username_collision_shrinks_over_length_base(app):
    """
    GIVEN an over-length base whose truncated form already exists
    WHEN a collision forces a numeric suffix
    THEN the base shrinks so base + suffix never exceeds the column limit
    """
    with app.app_context():
        long_base = "b" * 40
        first = generate_unique_username_from_email(f"{long_base}@example.com")
        existing = Users(username=first, email="existing2@example.com")
        db.session.add(existing)
        db.session.commit()

        result = generate_unique_username_from_email(f"{long_base}@example.com")
        assert result != first
        assert len(result) <= USER_CONSTANTS.MAX_USERNAME_LENGTH_ACTUAL
        assert result.endswith("1")


def test_generate_unique_username_raises_on_empty_local_part(app):
    """
    GIVEN an email with an empty local-part (e.g. '@example.com')
    WHEN generate_unique_username_from_email is called
    THEN it raises ValueError rather than producing an empty username
    """
    with app.app_context():
        with pytest.raises(ValueError):
            generate_unique_username_from_email("@example.com")


# ---------------------------------------------------------------------------
# find_or_create_oauth_user
# ---------------------------------------------------------------------------
def test_find_or_create_returns_existing_identity_user(app):
    """
    GIVEN an existing (provider, subject) identity linked to a user
    WHEN find_or_create_oauth_user is called with that pair
    THEN it returns the same user and creates no new rows
    """
    with app.app_context():
        user = Users(username="existinguser", email="existing@example.com")
        user.oauth_identities.append(
            UserOAuthIdentity(
                provider=_PROVIDER, provider_subject=_SUBJECT, email=_EMAIL
            )
        )
        db.session.add(user)
        db.session.commit()
        user_id = user.id

        users_before = Users.query.count()
        identities_before = UserOAuthIdentity.query.count()

        result = find_or_create_oauth_user(
            provider=_PROVIDER, subject=_SUBJECT, email=_EMAIL
        )

        assert result.id == user_id
        assert Users.query.count() == users_before
        assert UserOAuthIdentity.query.count() == identities_before


def test_find_or_create_raises_when_email_already_registered(app):
    """
    GIVEN a password user already owns the email
    WHEN find_or_create_oauth_user is called with an unlinked identity + that email
    THEN it raises EmailAlreadyRegisteredError and creates no identity row
    """
    with app.app_context():
        existing = Users(
            username="passworduser",
            email=_EMAIL,
            plaintext_password="a-strong-password",
        )
        db.session.add(existing)
        db.session.commit()

        identities_before = UserOAuthIdentity.query.count()

        with pytest.raises(EmailAlreadyRegisteredError) as exc_info:
            find_or_create_oauth_user(
                provider=_PROVIDER, subject=_SUBJECT, email=_EMAIL
            )

        assert exc_info.value.email == _EMAIL
        assert exc_info.value.provider == _PROVIDER
        assert UserOAuthIdentity.query.count() == identities_before


def test_find_or_create_rejects_unknown_provider(app):
    """
    GIVEN a provider value outside the supported Provider set
    WHEN find_or_create_oauth_user is called with it
    THEN it raises ValueError before any query and creates no user or identity
    """
    with app.app_context():
        users_before = Users.query.count()
        identities_before = UserOAuthIdentity.query.count()

        with pytest.raises(ValueError):
            find_or_create_oauth_user(
                provider="not-a-real-provider", subject=_SUBJECT, email=_EMAIL
            )

        assert Users.query.count() == users_before
        assert UserOAuthIdentity.query.count() == identities_before


def test_find_or_create_creates_new_user_and_identity(app):
    """
    GIVEN no existing identity and no user owning the email
    WHEN find_or_create_oauth_user is called
    THEN exactly one Users and one linked UserOAuthIdentity are created with a
        null password
    """
    with app.app_context():
        users_before = Users.query.count()
        identities_before = UserOAuthIdentity.query.count()

        result = find_or_create_oauth_user(
            provider=_PROVIDER, subject=_SUBJECT, email=_EMAIL
        )

        assert Users.query.count() == users_before + 1
        assert UserOAuthIdentity.query.count() == identities_before + 1
        assert result.password is None
        assert result.email_validated
        assert result.email == _EMAIL.lower()
        assert result.username == _LOCAL_PART
        assert len(result.oauth_identities) == 1
        identity = result.oauth_identities[0]
        assert identity.provider == _PROVIDER
        assert identity.provider_subject == _SUBJECT
        assert identity.user.id == result.id


def test_find_or_create_uses_preferred_username_when_provided(app):
    """
    GIVEN a preferred_username with no '@'
    WHEN find_or_create_oauth_user creates a new user
    THEN the username derives from preferred_username, not the email local-part
    """
    with app.app_context():
        result = find_or_create_oauth_user(
            provider=_PROVIDER,
            subject="github-subject-456",
            email="octocat@example.com",
            preferred_username="octocat",
        )
        assert result.username == "octocat"


def test_second_identity_same_user_provider_raises_integrity_error(app):
    """
    GIVEN a user with one linked identity for a provider
    WHEN a second identity for the same (user, provider) is committed
    THEN the UNIQUE(userID, provider) constraint raises IntegrityError
    """
    with app.app_context():
        user = Users(username="dupuser", email="dup@example.com")
        user.oauth_identities.append(
            UserOAuthIdentity(
                provider=_PROVIDER, provider_subject=_SUBJECT, email=_EMAIL
            )
        )
        db.session.add(user)
        db.session.commit()

        second_identity = UserOAuthIdentity(
            provider=_PROVIDER,
            provider_subject="different-subject-789",
            email=_EMAIL,
        )
        second_identity.user_id = user.id
        db.session.add(second_identity)

        with pytest.raises(IntegrityError):
            db.session.commit()

        db.session.rollback()


def test_find_or_create_returns_existing_winner_on_concurrent_insert(app):
    """
    GIVEN a concurrent login committed an identity for (provider, subject)
        after this call's initial lookup found none
    WHEN find_or_create_oauth_user commits and the
        UNIQUE(provider, provider_subject) constraint raises IntegrityError
    THEN it rolls back, re-queries the identity, and returns the concurrent
        winner's user rather than propagating the error

    The race is simulated by patching the identity lookup so the *initial*
    check sees None (as if the winner had not committed yet) while the except
    branch's re-query returns the already-committed winner.
    """
    with app.app_context():
        winner = Users(username="racewinner", email="winner@example.com")
        winner.oauth_identities.append(
            UserOAuthIdentity(
                provider=_PROVIDER,
                provider_subject=_SUBJECT,
                email="winner@example.com",
            )
        )
        db.session.add(winner)
        db.session.commit()
        winner_id = winner.id
        winner_identity = winner.oauth_identities[0]

        users_before = Users.query.count()

        patched_query = MagicMock()
        patched_query.filter_by.return_value.first.side_effect = [
            None,
            winner_identity,
        ]

        with patch.object(UserOAuthIdentity, "query", patched_query):
            result = find_or_create_oauth_user(
                provider=_PROVIDER, subject=_SUBJECT, email=_EMAIL
            )

        assert result.id == winner_id
        # The losing insert was rolled back; no extra user survived.
        assert Users.query.count() == users_before


def test_find_or_create_reraises_non_identity_integrity_error(app):
    """
    GIVEN a commit conflict that is NOT the (provider, subject) identity race
        (here, a username collision) and no matching identity to fall back to
    WHEN find_or_create_oauth_user hits IntegrityError on commit
    THEN it re-raises rather than swallowing the error, because the except
        branch's re-query finds no winning identity
    """
    with app.app_context():
        taken_username = "takenname"
        assert Users.query.filter(Users.username == taken_username).first() is None
        existing = Users(username=taken_username, email="taken@example.com")
        db.session.add(existing)
        db.session.commit()

        assert (
            UserOAuthIdentity.query.filter_by(
                provider=_PROVIDER, provider_subject=_SUBJECT
            ).first()
            is None
        )

        with patch(
            "backend.splash.services.oauth.account_service."
            "generate_unique_username_from_email",
            return_value=taken_username,
        ):
            with pytest.raises(IntegrityError):
                find_or_create_oauth_user(
                    provider=_PROVIDER, subject=_SUBJECT, email=_EMAIL
                )

        db.session.rollback()


def test_unique_provider_subject_constraint(app):
    """
    GIVEN two distinct users, one already linked to a (provider, subject)
    WHEN a second user is linked to the SAME (provider, subject)
    THEN the UNIQUE(provider, providerSubject) constraint raises IntegrityError

    Uses two different users so the (userID, provider) pair differs; only the
    globally-unique (provider, providerSubject) constraint can fire here.
    """
    with app.app_context():
        first_user = Users(username="provsubuser1", email="provsub1@example.com")
        first_user.oauth_identities.append(
            UserOAuthIdentity(
                provider=_PROVIDER, provider_subject=_SUBJECT, email=_EMAIL
            )
        )
        db.session.add(first_user)
        db.session.commit()

        second_user = Users(username="provsubuser2", email="provsub2@example.com")
        db.session.add(second_user)
        db.session.commit()

        conflicting_identity = UserOAuthIdentity(
            provider=_PROVIDER, provider_subject=_SUBJECT, email=_EMAIL
        )
        conflicting_identity.user_id = second_user.id
        db.session.add(conflicting_identity)

        with pytest.raises(IntegrityError):
            db.session.commit()

        db.session.rollback()
