import pytest
from flask import Flask
from flask_limiter.util import get_remote_address
from flask_login import login_user

from backend.models.users import Users
from backend.short_links.rate_limit import short_link_mint_rate_key

pytestmark = pytest.mark.unit

SHARED_ADDRESS: str = "203.0.113.7"


def _user(user_id: int) -> Users:
    user = Users(
        username=f"RateKeyUser{user_id}",
        email=f"ratekey{user_id}@example.com",
        plaintext_password="RateKeyPassword1234",
    )
    user.id = user_id
    return user


def test_authenticated_users_on_same_address_get_distinct_user_keys(
    app: Flask,
) -> None:
    """
    GIVEN two authenticated users behind the same remote address
    WHEN the mint rate key is computed in each request context
    THEN the keys differ, neither equals the IP, and each is the user id
    """
    keys: list[str] = []
    for user_id in (11, 12):
        with app.test_request_context(environ_base={"REMOTE_ADDR": SHARED_ADDRESS}):
            login_user(_user(user_id))
            assert get_remote_address() == SHARED_ADDRESS
            keys.append(short_link_mint_rate_key())

    assert keys[0] != keys[1]
    assert SHARED_ADDRESS not in keys
    assert keys == ["11", "12"]


def test_anonymous_caller_is_keyed_by_remote_address(app: Flask) -> None:
    """
    GIVEN an anonymous caller (the key function runs before the auth decorators)
    WHEN the mint rate key is computed
    THEN it is the remote address and does not raise
    """
    with app.test_request_context(environ_base={"REMOTE_ADDR": SHARED_ADDRESS}):
        assert short_link_mint_rate_key() == get_remote_address() == SHARED_ADDRESS
