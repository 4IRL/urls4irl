from typing import Any
import pytest
import redis
from redis import Redis

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
