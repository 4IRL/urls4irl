import pytest
from flask import Flask
from flask_limiter.util import get_remote_address
from flask_login import login_user

from backend.invite_links.rate_limit import invite_link_manage_rate_key
from backend.models.users import Users

pytestmark = pytest.mark.unit

SHARED_ADDRESS: str = "203.0.113.7"


def _user(user_id: int) -> Users:
    user = Users(
        username=f"InviteKeyUser{user_id}",
        email=f"invitekey{user_id}@example.com",
        plaintext_password="InviteKeyPassword1234",
    )
    user.id = user_id
    return user


def test_authenticated_managers_on_same_address_get_distinct_user_keys(
    app: Flask,
) -> None:
    """
    GIVEN two authenticated managers behind the same remote address
    WHEN the invite link rate key is computed in each request context
    THEN the keys are their user ids, never the shared IP
    """
    keys: list[str] = []
    for user_id in (21, 22):
        with app.test_request_context(environ_base={"REMOTE_ADDR": SHARED_ADDRESS}):
            login_user(_user(user_id))
            assert get_remote_address() == SHARED_ADDRESS
            keys.append(invite_link_manage_rate_key())

    assert keys == ["21", "22"]
    assert SHARED_ADDRESS not in keys


def test_anonymous_caller_is_keyed_by_remote_address(app: Flask) -> None:
    """
    GIVEN an anonymous caller (the key function runs before the auth decorators)
    WHEN the invite link rate key is computed
    THEN it is the remote address and does not raise
    """
    with app.test_request_context(environ_base={"REMOTE_ADDR": SHARED_ADDRESS}):
        assert invite_link_manage_rate_key() == SHARED_ADDRESS
