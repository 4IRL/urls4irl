from flask import current_app
from flask_login import current_user
from redis import Redis

from backend import db
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.app_logger import (
    safe_add_many_logs,
    warning_log,
)
from backend.extensions.metrics.writer import record_event
from backend.members.constants import (
    MEMBER_ADD_DAILY_CAP,
    MemberAddSource,
    UTubMembersErrorCodes,
)
from backend.members.data_models import ValidatedMember
from backend.metrics.events import EventName
from backend.schemas.errors import (
    build_field_error_response,
    build_message_error_response,
)
from backend.models.users import Users
from backend.models.utub_members import Utub_Members
from backend.models.utubs import Utubs
from backend.schemas.users import MemberModifiedResponseSchema, UserSchema
from backend.utils.strings.config_strs import CONFIG_ENVS
from backend.utils.strings.user_strs import MEMBER_FAILURE, MEMBER_SUCCESS, USER_FAILURE
from backend.utubs.guards import reject_if_utub_locked

# Shared enforcement Redis in-memory-stub sentinel — a `memory://` URI (or an
# absent URI) means no real Redis is wired, so the daily-cap counter fails open.
_MEMORY_URI: str = "memory://"

# Fixed 24h window (in seconds) for the per-user add-member daily counter.
_MEMBER_ADD_WINDOW_SECONDS: int = 86400


def _build_member_rate_limit_redis() -> Redis | None:
    """Build a client on the shared enforcement Redis (``REDIS_URI``), or return
    ``None`` when Redis is unavailable.

    Per the ``reauth_throttle.py`` precedent, this private per-module helper is
    duplicated rather than importing the underscore-prefixed
    ``_build_rate_limit_redis`` from ``account_service.py`` cross-module. Returns
    ``None`` when the URI is absent or the in-memory stub, so callers fail open
    (the add-member daily cap is anti-abuse, not a security boundary).
    """
    redis_uri: str | None = current_app.config.get(CONFIG_ENVS.REDIS_URI)
    if not redis_uri or redis_uri == _MEMORY_URI:
        return None
    return Redis.from_url(redis_uri)


def create_utub_member(
    username: str, current_utub: Utubs, source: MemberAddSource
) -> FlaskResponse:
    """
    Adds a user to a UTub. Handles if the user already exists in the UTub.

    Args:
        username (str): Username of the user to add
        current_utub (Utubs): The UTub to add the user to
        source (MemberAddSource): Where the add originated (typeahead pick vs
            exact-username outsider path); threaded into the MEMBER_ADDED metric

    Returns:
        tuple[Response, int]:
        - Response: JSON response on create
        - int: HTTP status code 200 (Success), 400 (User not found, already a
          member, or the per-user daily add cap was reached)
    """
    utub_locked_error: FlaskResponse | None = reject_if_utub_locked(
        current_utub, error_code=UTubMembersErrorCodes.UTUB_IS_LOCKED
    )
    if utub_locked_error is not None:
        return utub_locked_error

    # Per-user fail-open Redis daily counter. Placed BEFORE the username lookup
    # so every attempt reaching the oracle burns a slot regardless of outcome
    # (success, USER_NOT_EXIST, or MEMBER_ALREADY_IN_UTUB), bounding enumeration
    # probing. Fail-open on any Redis error — the cap is anti-abuse, not a
    # security boundary.
    rate_limit_key = f"member-add-lookup:{current_user.id}"
    redis_client = _build_member_rate_limit_redis()

    if redis_client is not None:
        try:
            current_count = int(redis_client.get(rate_limit_key) or 0)
            if current_count >= MEMBER_ADD_DAILY_CAP:
                warning_log(f"User={current_user.id} hit the daily add-member cap")
                return build_message_error_response(
                    message=MEMBER_FAILURE.MEMBER_ADD_RATE_LIMITED,
                )
            new_count = redis_client.incr(rate_limit_key)
            if new_count == 1:
                redis_client.expire(rate_limit_key, _MEMBER_ADD_WINDOW_SECONDS)
        except Exception as redis_error:
            current_app.logger.exception(
                "member-add daily-cap counter failed (failing open): " f"{redis_error}"
            )

    new_user: Users | None = Users.query.filter(Users.username == username).first()
    if new_user is None:
        warning_log(f"User={current_user.id} tried adding nonexistent username")
        return build_field_error_response(
            message=MEMBER_FAILURE.UNABLE_TO_ADD_MEMBER,
            errors={"username": [USER_FAILURE.USER_NOT_EXIST]},
        )

    member_in_utub = _check_if_member_already_in_utub(new_user, current_utub)
    if member_in_utub.in_utub:
        return build_message_error_response(
            message=MEMBER_FAILURE.MEMBER_ALREADY_IN_UTUB,
        )

    return _add_user_to_utub(user=new_user, current_utub=current_utub, source=source)


def _check_if_member_already_in_utub(
    user: Users, current_utub: Utubs
) -> ValidatedMember:
    """
    Checks if the user is already a member in the UTub.

    Args:
        user (Users): The user to check
        current_utub (Utubs): The UTub to check membership in

    Returns:
        ValidatedMember: Containing the User object and whether they are already in the UTub
    """
    already_in_utub = Utub_Members.query.get((current_utub.id, user.id)) is not None

    if already_in_utub:
        warning_log(
            f"User={current_user.id} tried adding a User={user.id} already in this UTub"
        )

    return ValidatedMember(user=user, in_utub=already_in_utub)


def _add_user_to_utub(
    user: Users, current_utub: Utubs, source: MemberAddSource
) -> FlaskResponse:
    """
    Handles adding the user to the UTub as a new UTub member.

    Args:
        user (Users): User being added to this UTub
        current_utub (Utubs): The UTub where this new member is being added too
        source (MemberAddSource): Where the add originated; recorded as the
            MEMBER_ADDED `source` dimension

    Returns:
        tuple[Response, int]:
        - Response: JSON response on success
        - int: HTTP status code 200
    """
    new_user_to_utub = Utub_Members()
    new_user_to_utub.utub_id = current_utub.id
    new_user_to_utub.user_id = user.id
    db.session.add(new_user_to_utub)
    current_utub.set_last_updated()
    db.session.commit()

    # Successfully added user to UTub
    safe_add_many_logs(
        ["Added member to UTub", f"UTub.id={current_utub.id}", f"Added User={user.id}"]
    )
    record_event(EventName.MEMBER_ADDED, dimensions={"source": source.value})

    return APIResponse(
        message=MEMBER_SUCCESS.MEMBER_ADDED,
        data=MemberModifiedResponseSchema(
            utub_id=current_utub.id,
            member=UserSchema(id=user.id, username=user.username),
        ),
    ).to_response()
