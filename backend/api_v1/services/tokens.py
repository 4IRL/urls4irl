from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
import secrets
import uuid

from flask import current_app
import jwt
from jwt import exceptions as JWTExceptions

from backend import db
from backend.models.api_refresh_tokens import ApiRefreshTokens
from backend.models.users import Users
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.api_auth_strs import API_AUTH
from backend.utils.strings.config_strs import CONFIG_ENVS

# secrets.token_urlsafe(48) yields a 64-character opaque refresh token
REFRESH_TOKEN_URLSAFE_BYTES = 48


class RefreshRotationStatus(Enum):
    """Outcome of presenting a refresh token for rotation.

    ROTATED: the token was active; a replacement was issued in the same family.
    REUSE_DETECTED: the token was already rotated — treated as theft; the
        entire family has been revoked.
    INVALID: the token is unknown, expired, or belongs to a revoked family.
    """

    ROTATED = "rotated"
    REUSE_DETECTED = "reuse_detected"
    INVALID = "invalid"


@dataclass(frozen=True)
class RefreshRotationResult:
    status: RefreshRotationStatus
    user: Users | None = None
    new_refresh_token: str | None = None


def create_access_token(*, user: Users) -> str:
    """Mint a short-lived stateless HS256 access JWT for the given user.

    Payload example for user id 42 with a 900-second lifetime:
    ``{"sub": "42", "type": "access", "iat": 1751700000, "exp": 1751700900}``.
    """
    lifetime_seconds: int = current_app.config[
        CONFIG_ENVS.API_ACCESS_TOKEN_LIFETIME_SECONDS
    ]
    issued_at_timestamp = int(utc_now().timestamp())
    return jwt.encode(
        payload={
            API_AUTH.SUBJECT_CLAIM: str(user.id),
            API_AUTH.TOKEN_TYPE_CLAIM: API_AUTH.ACCESS_TOKEN_TYPE,
            API_AUTH.ISSUED_AT_CLAIM: issued_at_timestamp,
            API_AUTH.EXPIRATION_CLAIM: issued_at_timestamp + lifetime_seconds,
        },
        key=current_app.config[CONFIG_ENVS.SECRET_KEY],
        algorithm=API_AUTH.ALGORITHM,
    )


def decode_access_token(*, token: str) -> Users | None:
    """Return the Users row for a valid, unexpired access JWT, else None.

    Never raises: any signature/expiry/claim failure returns None so the
    request_loader can fall through to an unauthenticated request.
    """
    try:
        payload = jwt.decode(
            jwt=token,
            key=current_app.config[CONFIG_ENVS.SECRET_KEY],
            algorithms=[API_AUTH.ALGORITHM],
        )
    except JWTExceptions.PyJWTError:
        return None

    if payload.get(API_AUTH.TOKEN_TYPE_CLAIM) != API_AUTH.ACCESS_TOKEN_TYPE:
        return None

    subject = payload.get(API_AUTH.SUBJECT_CLAIM)
    try:
        user_id = int(subject)
    except (TypeError, ValueError):
        return None

    return Users.query.get(user_id)


def issue_refresh_token(*, user: Users) -> str:
    """Create a new refresh token in a brand-new family (a new device login)."""
    token_value = _generate_refresh_token_value()
    refresh_token_row = ApiRefreshTokens(
        user_id=user.id,
        token=token_value,
        family_id=str(uuid.uuid4()),
        expires_at=utc_now() + timedelta(seconds=_refresh_token_lifetime_seconds()),
    )
    db.session.add(refresh_token_row)
    db.session.commit()
    return token_value


def rotate_refresh_token(*, presented_token: str) -> RefreshRotationResult:
    """Rotate an active refresh token, detecting replay of superseded tokens.

    Rotation: the presented row is stamped ``rotatedAt``/``replacedBy`` and a
    new row is issued in the same family with a fresh 30-day expiry.

    Reuse detection: presenting an already-rotated token means two parties
    held the same token (the legitimate client and a thief) — the whole family
    is revoked and REUSE_DETECTED is returned.
    """
    presented_row: ApiRefreshTokens | None = ApiRefreshTokens.query.filter(
        ApiRefreshTokens.token == presented_token
    ).first()

    if presented_row is None or presented_row.is_revoked():
        return RefreshRotationResult(status=RefreshRotationStatus.INVALID)

    if presented_row.is_rotated():
        _revoke_family(family_id=presented_row.family_id)
        db.session.commit()
        return RefreshRotationResult(status=RefreshRotationStatus.REUSE_DETECTED)

    if presented_row.is_expired():
        return RefreshRotationResult(status=RefreshRotationStatus.INVALID)

    replacement_token_value = _generate_refresh_token_value()
    replacement_row = ApiRefreshTokens(
        user_id=presented_row.user_id,
        token=replacement_token_value,
        family_id=presented_row.family_id,
        expires_at=utc_now() + timedelta(seconds=_refresh_token_lifetime_seconds()),
    )
    db.session.add(replacement_row)
    db.session.flush()

    presented_row.rotated_at = utc_now()
    presented_row.replaced_by_id = replacement_row.id
    db.session.commit()

    return RefreshRotationResult(
        status=RefreshRotationStatus.ROTATED,
        user=presented_row.user,
        new_refresh_token=replacement_token_value,
    )


def revoke_refresh_token_family(*, presented_token: str) -> bool:
    """Per-device logout: revoke the presented token's entire rotation family.

    Returns True when the token was found and its family revoked, else False.
    """
    presented_row: ApiRefreshTokens | None = ApiRefreshTokens.query.filter(
        ApiRefreshTokens.token == presented_token
    ).first()
    if presented_row is None:
        return False

    _revoke_family(family_id=presented_row.family_id)
    db.session.commit()
    return True


def revoke_all_refresh_tokens_for_user(*, user_id: int) -> int:
    """Log out everywhere: revoke every unrevoked refresh token for the user.

    Returns the number of rows revoked.
    """
    revoked_count = ApiRefreshTokens.query.filter(
        ApiRefreshTokens.user_id == user_id,
        ApiRefreshTokens.revoked_at.is_(None),
    ).update({ApiRefreshTokens.revoked_at: utc_now()}, synchronize_session=False)
    db.session.commit()
    return revoked_count


def _generate_refresh_token_value() -> str:
    return secrets.token_urlsafe(REFRESH_TOKEN_URLSAFE_BYTES)


def _refresh_token_lifetime_seconds() -> int:
    return current_app.config[CONFIG_ENVS.API_REFRESH_TOKEN_LIFETIME_SECONDS]


def _revoke_family(*, family_id: str) -> None:
    ApiRefreshTokens.query.filter(
        ApiRefreshTokens.family_id == family_id,
        ApiRefreshTokens.revoked_at.is_(None),
    ).update({ApiRefreshTokens.revoked_at: utc_now()}, synchronize_session=False)
