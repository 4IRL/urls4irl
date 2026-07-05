from datetime import timedelta

from flask import Flask
import jwt
import pytest

from backend import db
from backend.api_v1.services.tokens import (
    RefreshRotationStatus,
    create_access_token,
    decode_access_token,
    issue_refresh_token,
    revoke_all_refresh_tokens_for_user,
    revoke_refresh_token_family,
    rotate_refresh_token,
)
from backend.models.api_refresh_tokens import ApiRefreshTokens
from backend.models.users import Users
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.api_auth_strs import API_AUTH
from backend.utils.strings.config_strs import CONFIG_ENVS

pytestmark = pytest.mark.mobile_api

_UNKNOWN_TOKEN = "not-a-token-that-was-ever-issued"


def _first_user() -> Users:
    return Users.query.get(1)


def _second_user() -> Users:
    return Users.query.get(2)


def _craft_access_token(app: Flask, payload: dict) -> str:
    return jwt.encode(
        payload=payload,
        key=app.config[CONFIG_ENVS.SECRET_KEY],
        algorithm=API_AUTH.ALGORITHM,
    )


def test_access_token_roundtrip(app: Flask, register_first_user):
    """
    GIVEN a registered user
    WHEN an access token is minted and decoded
    THEN the original user is returned
    """
    with app.app_context():
        minted_token = create_access_token(user=_first_user())
        decoded_user = decode_access_token(token=minted_token)
        assert decoded_user is not None
        assert decoded_user.id == 1


def test_access_token_expired_returns_none(app: Flask, register_first_user):
    """
    GIVEN an access token minted with a negative lifetime (already expired)
    WHEN it is decoded
    THEN None is returned
    """
    original_lifetime = app.config[CONFIG_ENVS.API_ACCESS_TOKEN_LIFETIME_SECONDS]
    app.config[CONFIG_ENVS.API_ACCESS_TOKEN_LIFETIME_SECONDS] = -10
    try:
        with app.app_context():
            expired_token = create_access_token(user=_first_user())
            assert decode_access_token(token=expired_token) is None
    finally:
        app.config[CONFIG_ENVS.API_ACCESS_TOKEN_LIFETIME_SECONDS] = original_lifetime


def test_access_token_tampered_returns_none(app: Flask, register_first_user):
    with app.app_context():
        minted_token = create_access_token(user=_first_user())
        assert decode_access_token(token=minted_token + "tampered") is None


def test_access_token_wrong_type_claim_returns_none(app: Flask, register_first_user):
    """A signed JWT whose ``type`` claim is not ``access`` must be rejected."""
    with app.app_context():
        wrong_type_token = _craft_access_token(
            app,
            {
                API_AUTH.SUBJECT_CLAIM: "1",
                API_AUTH.TOKEN_TYPE_CLAIM: "refresh",
                API_AUTH.EXPIRATION_CLAIM: 2**31,
            },
        )
        assert decode_access_token(token=wrong_type_token) is None


def test_access_token_missing_subject_returns_none(app: Flask, register_first_user):
    with app.app_context():
        missing_subject_token = _craft_access_token(
            app,
            {
                API_AUTH.TOKEN_TYPE_CLAIM: API_AUTH.ACCESS_TOKEN_TYPE,
                API_AUTH.EXPIRATION_CLAIM: 2**31,
            },
        )
        assert decode_access_token(token=missing_subject_token) is None


def test_access_token_unknown_user_returns_none(app: Flask, register_first_user):
    with app.app_context():
        unknown_user_token = _craft_access_token(
            app,
            {
                API_AUTH.SUBJECT_CLAIM: "999999",
                API_AUTH.TOKEN_TYPE_CLAIM: API_AUTH.ACCESS_TOKEN_TYPE,
                API_AUTH.EXPIRATION_CLAIM: 2**31,
            },
        )
        assert decode_access_token(token=unknown_user_token) is None


def test_issue_refresh_token_creates_active_row(app: Flask, register_first_user):
    """
    GIVEN a registered user with no refresh tokens
    WHEN a refresh token is issued
    THEN exactly one active row exists with the returned token value
    """
    with app.app_context():
        assert ApiRefreshTokens.query.count() == 0

        issued_token_value = issue_refresh_token(user=_first_user())

        all_rows = ApiRefreshTokens.query.all()
        assert len(all_rows) == 1
        issued_row = all_rows[0]
        assert issued_row.token == issued_token_value
        assert issued_row.user_id == 1
        assert issued_row.is_active()
        assert not issued_row.is_expired()
        assert issued_row.family_id


def test_rotate_refresh_token_issues_replacement_in_same_family(
    app: Flask, register_first_user
):
    """
    GIVEN an active refresh token
    WHEN it is rotated
    THEN the old row is stamped rotatedAt/replacedBy, and a new active row is
        issued in the same family for the same user
    """
    with app.app_context():
        original_token_value = issue_refresh_token(user=_first_user())

        rotation_result = rotate_refresh_token(presented_token=original_token_value)

        assert rotation_result.status == RefreshRotationStatus.ROTATED
        assert rotation_result.user is not None
        assert rotation_result.user.id == 1
        assert rotation_result.new_refresh_token is not None
        assert rotation_result.new_refresh_token != original_token_value

        original_row = ApiRefreshTokens.query.filter(
            ApiRefreshTokens.token == original_token_value
        ).first()
        replacement_row = ApiRefreshTokens.query.filter(
            ApiRefreshTokens.token == rotation_result.new_refresh_token
        ).first()

        assert original_row.is_rotated()
        assert not original_row.is_revoked()
        assert original_row.replaced_by_id == replacement_row.id
        assert replacement_row.is_active()
        assert replacement_row.family_id == original_row.family_id
        assert replacement_row.user_id == original_row.user_id


def test_rotate_replayed_token_revokes_entire_family(app: Flask, register_first_user):
    """
    GIVEN a refresh token that was already rotated (superseded)
    WHEN the spent token is presented again (replay — stolen-token scenario)
    THEN REUSE_DETECTED is returned and every row in the family is revoked,
        including the currently-active replacement
    """
    with app.app_context():
        original_token_value = issue_refresh_token(user=_first_user())
        first_rotation = rotate_refresh_token(presented_token=original_token_value)
        assert first_rotation.status == RefreshRotationStatus.ROTATED

        replay_result = rotate_refresh_token(presented_token=original_token_value)

        assert replay_result.status == RefreshRotationStatus.REUSE_DETECTED
        assert replay_result.user is None
        assert replay_result.new_refresh_token is None

        family_rows = ApiRefreshTokens.query.all()
        assert len(family_rows) == 2
        assert all(row.is_revoked() for row in family_rows)

        # The revoked replacement can no longer be rotated
        post_revocation_result = rotate_refresh_token(
            presented_token=first_rotation.new_refresh_token
        )
        assert post_revocation_result.status == RefreshRotationStatus.INVALID


def test_rotate_unknown_token_is_invalid(app: Flask, register_first_user):
    with app.app_context():
        assert ApiRefreshTokens.query.count() == 0
        rotation_result = rotate_refresh_token(presented_token=_UNKNOWN_TOKEN)
        assert rotation_result.status == RefreshRotationStatus.INVALID


def test_rotate_expired_token_is_invalid(app: Flask, register_first_user):
    """
    GIVEN a refresh token whose expiry has passed
    WHEN it is rotated
    THEN INVALID is returned and no replacement is issued
    """
    with app.app_context():
        issued_token_value = issue_refresh_token(user=_first_user())
        issued_row = ApiRefreshTokens.query.filter(
            ApiRefreshTokens.token == issued_token_value
        ).first()
        issued_row.expires_at = utc_now() - timedelta(seconds=1)
        db.session.commit()

        rotation_result = rotate_refresh_token(presented_token=issued_token_value)

        assert rotation_result.status == RefreshRotationStatus.INVALID
        assert ApiRefreshTokens.query.count() == 1


def test_revoke_refresh_token_family_per_device_logout(app: Flask, register_first_user):
    """
    GIVEN a rotation chain of two rows (one spent, one active)
    WHEN the active token's family is revoked (per-device logout)
    THEN every row in the family is revoked and the token cannot be rotated
    """
    with app.app_context():
        original_token_value = issue_refresh_token(user=_first_user())
        rotation_result = rotate_refresh_token(presented_token=original_token_value)

        was_revoked = revoke_refresh_token_family(
            presented_token=rotation_result.new_refresh_token
        )

        assert was_revoked
        family_rows = ApiRefreshTokens.query.all()
        assert len(family_rows) == 2
        assert all(row.is_revoked() for row in family_rows)

        post_logout_result = rotate_refresh_token(
            presented_token=rotation_result.new_refresh_token
        )
        assert post_logout_result.status == RefreshRotationStatus.INVALID


def test_revoke_refresh_token_family_unknown_token_returns_false(
    app: Flask, register_first_user
):
    with app.app_context():
        assert not revoke_refresh_token_family(presented_token=_UNKNOWN_TOKEN)


def test_revoke_all_refresh_tokens_for_user(app: Flask, register_multiple_users):
    """
    GIVEN two active token families for user 1 (two devices) and one for user 2
    WHEN all tokens for user 1 are revoked (log out everywhere)
    THEN both of user 1's families are revoked and user 2's token is untouched
    """
    with app.app_context():
        first_device_token = issue_refresh_token(user=_first_user())
        second_device_token = issue_refresh_token(user=_first_user())
        second_user_token = issue_refresh_token(user=_second_user())

        revoked_count = revoke_all_refresh_tokens_for_user(user_id=1)

        assert revoked_count == 2
        for revoked_token_value in (first_device_token, second_device_token):
            revoked_row = ApiRefreshTokens.query.filter(
                ApiRefreshTokens.token == revoked_token_value
            ).first()
            assert revoked_row.is_revoked()

        second_user_row = ApiRefreshTokens.query.filter(
            ApiRefreshTokens.token == second_user_token
        ).first()
        assert second_user_row.is_active()
