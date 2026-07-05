from __future__ import annotations

from dataclasses import dataclass

from flask import current_app
import jwt
from jwt import PyJWKClient
from jwt import exceptions as JWTExceptions

from backend.utils.strings.config_strs import CONFIG_ENVS

# Google's public signing keys for id_token verification (native mobile
# Sign-In flow). PyJWKClient caches fetched keys in-process.
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ID_TOKEN_ALGORITHM = "RS256"
# Google historically issues both forms; verify manually against this
# closed set rather than passing a single issuer to jwt.decode.
GOOGLE_ISSUERS = ("https://accounts.google.com", "accounts.google.com")

_google_jwk_client = PyJWKClient(GOOGLE_JWKS_URL)


@dataclass(frozen=True)
class GoogleIdTokenClaims:
    """OIDC claims extracted from a verified Google id_token."""

    subject: str
    email: str
    email_verified: bool
    name: str | None


def verify_google_id_token(*, id_token: str) -> GoogleIdTokenClaims | None:
    """Verify a native-app Google id_token's signature, audience, and issuer.

    Returns the extracted claims on success, or None on ANY failure (bad
    signature, expired, wrong audience/issuer, missing claims, unconfigured
    Google client, JWKS fetch failure) — the caller maps None to a 401.
    """
    google_client_id: str | None = current_app.config.get(
        CONFIG_ENVS.GOOGLE_OAUTH_CLIENT_ID
    )
    if not google_client_id:
        return None

    try:
        signing_key = _google_jwk_client.get_signing_key_from_jwt(id_token)
        claims = jwt.decode(
            jwt=id_token,
            key=signing_key.key,
            algorithms=[GOOGLE_ID_TOKEN_ALGORITHM],
            audience=google_client_id,
        )
    except (JWTExceptions.PyJWTError, ValueError, ConnectionError):
        return None

    if claims.get("iss") not in GOOGLE_ISSUERS:
        return None

    subject = claims.get("sub")
    email = claims.get("email")
    if not isinstance(subject, str) or not isinstance(email, str):
        return None

    return GoogleIdTokenClaims(
        subject=subject,
        email=email,
        email_verified=claims.get("email_verified") is True,
        name=claims.get("name") or claims.get("given_name"),
    )
