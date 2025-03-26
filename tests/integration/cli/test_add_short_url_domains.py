from typing import Any
import pytest
import redis
from redis import Redis

from src import url_validator
from src.utils.strings.config_strs import CONFIG_ENVS as ENV
from src.utils.strings.url_validation_strs import SHORT_URLS

pytestmark = pytest.mark.cli


def test_add_short_url_domains(runner):
    """
    GIVEN a developer wanting to add mock users to the database
    WHEN the developer provides the following CLI command:
        `flask addmock users`
    THEN verify that mock users are added to the database

    Args:
        runner (pytest.fixture): Provides a Flask application, and a FlaskCLIRunner
    """
    VALID_SHORT_DOMAINS = (
        "a.co",
        "bit.ly",
        "tinyurl.com",
        "bl.ink",
        "youtu.be",
    )

    app, cli_runner = runner
    redis_uri = app.config.get(ENV.REDIS_URI, None)

    # Do not test unless valid Redis URI is added
    if not redis_uri or redis_uri == "memory://":
        return

    cli_runner.invoke(args=["shorturls", "add"])

    redis_client: Any = redis.Redis.from_url(url=redis_uri)
    assert isinstance(redis_client, Redis)

    for short_domain in VALID_SHORT_DOMAINS:
        assert redis_client.sismember(name=SHORT_URLS, value=short_domain) == 1


def test_validate_short_url(runner):
    """
    GIVEN a developer wanting to add mock users to the database
    WHEN the developer provides the following CLI command:
        `flask addmock users`
    THEN verify that mock users are added to the database

    Args:
        runner (pytest.fixture): Provides a Flask application, and a FlaskCLIRunner
    """
    app, cli_runner = runner
    redis_uri = app.config.get(ENV.REDIS_URI, None)

    # Do not test unless valid Redis URI is added
    if not redis_uri or redis_uri == "memory://":
        return

    cli_runner.invoke(args=["shorturls", "add"])

    """
    VALID_SHORT_URL = "https://a.co/d/5bgDNcz"
    final_url, is_validated = url_validator.validate_url(VALID_SHORT_URL)

    assert "amazon.com" in final_url
    assert is_validated
    """

    VALID_BITLY_URL = "https://bit.ly/test-u4i-link"
    LONG_URL = "https://www.youtube.com/watch?v=b0fv54xGOwY&pp=0gcJCb0Ag7Wk3p_U"

    final_url, is_validated = url_validator.validate_url(VALID_BITLY_URL)

    assert LONG_URL == final_url
    assert is_validated
