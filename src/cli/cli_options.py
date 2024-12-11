import requests

from flask import Flask, current_app
from flask.cli import AppGroup, with_appcontext
import redis
from redis.client import Redis

from src.utils.strings.config_strs import CONFIG_ENVS as ENV
from src.utils.strings.url_validation_strs import SHORT_URLS

HELP_SUMMARY_MOCKS = """Add list of short URL domains to redis."""
SHORT_URL_DOMAINS_LIST = (
    "https://raw.githubusercontent.com/PeterDaveHello/url-shorteners/master/list"
)

short_urls_cli = AppGroup(
    "shorturls",
    context_settings={"ignore_unknown_options": True},
    help=HELP_SUMMARY_MOCKS,
)


@short_urls_cli.command("add", help="Add short URL domain to redis.")
@with_appcontext
def add_short_url_domains_to_redis():
    with current_app.test_request_context("/"):
        redis_uri: str | None = current_app.config.get(ENV.REDIS_URI, None)
        if not redis_uri or redis_uri == "memory://":
            print("No valid Redis URI provided, exiting here.")
            return

    try:
        response = requests.get(SHORT_URL_DOMAINS_LIST, timeout=10)

        short_urls_raw = response.content
        if not short_urls_raw:
            print("Unable to parse content of response.")
            return

        short_urls = short_urls_raw.splitlines()
        if not short_urls or len(short_urls) < 11:
            print("No content found with splitlines when parsing short URL domains.")
            return

        # Remove title block from list
        short_urls = short_urls[11:]

        short_urls_strs = [str(val.decode()) for val in short_urls]

        redis_client: Redis = redis.Redis.from_url(url=redis_uri)
        added = redis_client.sadd(SHORT_URLS, *short_urls_strs)
        if added == 0:
            print("No new domains added.")
            return

        print(f"Added {added} new short URL domains to Redis.")
        return

    except requests.RequestException:
        print("Unable to perform request to get short URL domains.")

    except Exception as e:
        print(f"Unknown exception when generating short URL domain list. {str(e)}")


def register_short_urls_cli(app: Flask):
    app.cli.add_command(short_urls_cli)
