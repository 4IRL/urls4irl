from __future__ import annotations

from sqlalchemy.exc import IntegrityError

from backend import db
from backend.models.user_oauth_identities import UserOAuthIdentity
from backend.models.users import Users
from backend.splash.services.oauth.constants import Provider
from backend.utils.constants import USER_CONSTANTS


class EmailAlreadyRegisteredError(Exception):
    """Raised when an OAuth flow resolves to an email already owned by a
    local (password) account that has no linked identity for this provider.

    Carries the conflicting email and provider so the Phase 2 callback route
    can render an actionable message to the user.
    """

    def __init__(self, *, email: str, provider: Provider) -> None:
        self.email = email
        self.provider = provider
        super().__init__(
            f"Email '{email}' is already registered and is not linked to "
            f"provider '{provider}'."
        )


def generate_unique_username_from_email(email: str) -> str:
    """Derive a unique, column-safe username from an email or plain username.

    The local-part (text before ``@``) is used as the base candidate; an input
    with no ``@`` (e.g. a GitHub ``preferred_username``) is used whole. Two
    truncation ceilings apply:

    - **No collision:** the base is truncated to ``MAX_USERNAME_LENGTH_ACTUAL``
      (25) — the physical column limit — and returned as-is.
    - **On collision:** an integer suffix (``1``..``99999``) is appended, and
      the base is re-truncated to ``MAX_USERNAME_LENGTH - len(str(suffix))``
      (base ``MAX_USERNAME_LENGTH`` is 20) so ``base + suffix`` always fits the
      column. The base therefore shrinks from up to 25 chars to at most 19 on
      the first collision.

    Args:
        email: An email address, or a plain username with no ``@``.

    Returns:
        A username unique against the ``Users.username`` column and within the
        physical length limit.

    Raises:
        ValueError: If the email has an empty local-part (e.g. ``@example.com``)
            and no username can be derived.
        RuntimeError: If every suffix from 1 to 99999 is already taken.

    Examples:
        >>> generate_unique_username_from_email("john.doe@example.com")
        'john.doe'                       # local-part passthrough, no collision
        >>> generate_unique_username_from_email("johndoe")
        'johndoe'                        # no '@' -> full input is the base
        >>> generate_unique_username_from_email("a" * 40 + "@example.com")
        'aaaaaaaaaaaaaaaaaaaaaaaaa'       # truncated to 25 chars (no collision)
        # If "john.doe" already exists:
        >>> generate_unique_username_from_email("john.doe@example.com")
        'john.doe1'                      # collision -> base + numeric suffix
    """
    base_candidate = email.split("@", 1)[0]
    if not base_candidate:
        raise ValueError(
            "Cannot derive a username from an email with an empty local-part "
            f"(before '@'): '{email}'."
        )

    no_collision_candidate = base_candidate[: USER_CONSTANTS.MAX_USERNAME_LENGTH_ACTUAL]
    if Users.query.filter(Users.username == no_collision_candidate).first() is None:
        return no_collision_candidate

    for suffix in range(1, 100000):
        suffix_text = str(suffix)
        truncated_base = base_candidate[
            : USER_CONSTANTS.MAX_USERNAME_LENGTH - len(suffix_text)
        ]
        candidate = f"{truncated_base}{suffix_text}"
        if Users.query.filter(Users.username == candidate).first() is None:
            return candidate

    raise RuntimeError(
        f"Unable to generate a unique username from '{email}': all suffixes "
        f"from 1 to 99999 are exhausted."
    )


def find_or_create_oauth_user(
    *,
    provider: Provider,
    subject: str,
    email: str,
    preferred_username: str | None = None,
) -> Users:
    """Resolve an OAuth login to a local Users account, creating one if needed.

    Resolution order:
    1. If an identity for ``(provider, subject)`` exists, return its user.
    2. Else if a user already owns ``email``, raise
       ``EmailAlreadyRegisteredError`` (the caller decides how to reconcile).
    3. Else create a new password-less user with a freshly linked identity.

    Args:
        provider: The OAuth provider whose branch is being handled. Must
            reference a seeded row in the ``Providers`` table; an unknown value
            fails the ``provider`` foreign key at commit (surfaced as
            ``IntegrityError``). Validity is enforced by the DB, not this enum.
        subject: The provider's stable subject identifier for the account.
        email: The email reported by the provider.
        preferred_username: An optional provider-supplied username to seed the
            local username from; falls back to the email local-part.

    Returns:
        The resolved (existing or newly created) Users instance.

    Raises:
        EmailAlreadyRegisteredError: If the email belongs to an unlinked
            local account.
        IntegrityError: If the commit conflicts on a constraint other than the
            ``(provider, provider_subject)`` identity (e.g. an email/username
            collision, or an unknown provider that fails the foreign key, with
            no matching identity to fall back to).
    """
    existing_identity: UserOAuthIdentity | None = UserOAuthIdentity.query.filter_by(
        provider=provider, provider_subject=subject
    ).first()
    if existing_identity is not None:
        return existing_identity.user

    email_owner: Users | None = Users.query.filter(Users.email == email.lower()).first()
    if email_owner is not None:
        raise EmailAlreadyRegisteredError(email=email, provider=provider)

    new_user = Users(
        username=generate_unique_username_from_email(preferred_username or email),
        email=email,
    )
    new_user.oauth_identities.append(
        UserOAuthIdentity(provider=provider, provider_subject=subject, email=email)
    )
    new_user.validate_email()
    db.session.add(new_user)
    try:
        db.session.commit()
    except IntegrityError as integrity_error:
        # A concurrent login for the same (provider, subject) can pass the
        # check-then-act guards above and commit first, so this insert loses
        # the race on the UNIQUE(provider, provider_subject) constraint.
        db.session.rollback()
        concurrent_winner_identity: UserOAuthIdentity | None = (
            UserOAuthIdentity.query.filter_by(
                provider=provider, provider_subject=subject
            ).first()
        )
        if concurrent_winner_identity is not None:
            return concurrent_winner_identity.user
        # No matching identity means the conflict was an email/username
        # collision, not the race we handle — surface it to the caller.
        raise integrity_error
    return new_user
