import redis

from flask import Flask, current_app
from flask.cli import AppGroup, with_appcontext

from backend.utils.short_urls import (
    ShortUrlSyncError,
    sync_short_url_domains_to_redis,
)
from backend.utils.strings.config_strs import CONFIG_ENVS as ENV

HELP_SUMMARY_SHORT_URL = """Add list of short URL domains to redis."""

short_urls_cli = AppGroup(
    "shorturls",
    context_settings={"ignore_unknown_options": True},
    help=HELP_SUMMARY_SHORT_URL,
)


@short_urls_cli.command("add", help="Add short URL domain to redis.")
@with_appcontext
def add_short_url_domains_to_redis():
    with current_app.test_request_context("/"):
        redis_uri: str | None = current_app.config.get(ENV.REDIS_URI, None)
        if not redis_uri or redis_uri == "memory://":
            print("No valid Redis URI provided, exiting here.")
            return

    redis_client = redis.Redis.from_url(url=redis_uri)  # type: ignore[arg-type]
    try:
        added_count = sync_short_url_domains_to_redis(redis_client=redis_client)
    except ShortUrlSyncError as sync_error:
        print(str(sync_error))
        return

    if added_count == 0:
        print("No new domains added.")
        return

    print(f"Added {added_count} new short URL domains to Redis.")


def register_short_urls_cli(app: Flask):
    app.cli.add_command(short_urls_cli)
