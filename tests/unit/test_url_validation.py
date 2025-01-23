from time import sleep
from unittest import mock

import pytest
import requests

from src.extensions.url_validation.url_validator import (
    InvalidURLError,
    UrlValidator,
    WaybackRateLimited,
)
from src.extensions.url_validation import constants as url_constants
from src.utils.strings.url_validation_strs import USER_AGENT

pytestmark = pytest.mark.unit

valid_urls = {
    "https://www.google.com/": [
        "https://www.google.com/",
        "https://www.google.com",
        "google.com",
        "www.google.com",
        "http://www.google.com",
        "https://www.google.com",
        "https://google.com",
        "ww.google.com",
        "http://google.com",
        "http:/google.com",
        "https:/google.com",
    ],
    "https://www.facebook.com/": [
        "https://www.facebook.com/",
        "https://www.facebook.com",
        "facebook.com",
        "www.facebook.com",
        "http://www.facebook.com",
        "https://facebook.com",
        "ww.facebook.com",
        "http://facebook.com",
        "http:/facebook.com",
        "https:/facebook.com",
    ],
    "https://cherupil.com/": [
        "https://cherupil.com/",
        "https://cherupil.com",
        "cherupil.com",
        "https:/cherupil.com",
        "http://cherupil.com",
        "http:/cherupil.com",
    ],
    "https://www.cherupil.com/": [
        "www.cherupil.com/",
        "www.cherupil.com",
        "https://www.cherupil.com",
        "http://www.cherupil.com/",
        "https:/www.cherupil.com/",
    ],
    "https://flask-limiter.readthedocs.io/en/stable/": [
        "https://flask-limiter.readthedocs.io/",
        "https://flask-limiter.readthedocs.io",
        "http:/flask-limiter.readthedocs.io",
        "https:/flask-limiter.readthedocs.io",
        "https://flask-limiter.readthedocs.io/",
        "http:/flask-limiter.readthedocs.io/",
        "https:/flask-limiter.readthedocs.io/",
        "flask-limiter.readthedocs.io",
        "flask-limiter.readthedocs.io/",
    ],
    "https://stackoverflow.com/": [
        "www.stackoverflow.com",
        "stackoverflow.com",
    ],
    "https://www.lowes.com/pd/ReliaBilt-ReliaBilt-3-1-2-in-Zinc-Plated-Flat-Corner-Brace-4-Pack/5003415919": [
        "https://www.lowes.com/pd/ReliaBilt-ReliaBilt-3-1-2-in-Zinc-Plated-Flat-Corner-Brace-4-Pack/5003415919",
        "www.lowes.com/pd/ReliaBilt-ReliaBilt-3-1-2-in-Zinc-Plated-Flat-Corner-Brace-4-Pack/5003415919",
        "lowes.com/pd/ReliaBilt-ReliaBilt-3-1-2-in-Zinc-Plated-Flat-Corner-Brace-4-Pack/5003415919",
    ],
    "https://www.fnb-online.com/": [
        "https://www.fnb-online.com/",
        "www.fnb-online.com/",
        "fnb-online.com/",
    ],
    "https://www.upgrad.com/blog/top-artificial-intelligence-project-ideas-topics-for-beginners/": [
        "https://www.upgrad.com/blog/top-artificial-intelligence-project-ideas-topics-for-beginners/",
        "www.upgrad.com/blog/top-artificial-intelligence-project-ideas-topics-for-beginners/",
        "upgrad.com/blog/top-artificial-intelligence-project-ideas-topics-for-beginners/",
    ],
    "https://immich.app/docs/overview/introduction/": [
        "https://immich.app/docs/overview/introduction",
    ],
    "https://developers.google.com/calendar/api/guides/overview": [
        "https://developers.google.com/calendar/api/guides/overview",
    ],
    "https://developers.google.com/keep/api/reference/rest": [
        "https://developers.google.com/keep/api/reference/rest"
    ],
}

invalid_urls = (
    "w.google.com",
    "http://mw1.google.com/mw-earth-vectordb/kml-samples/gp/seattle/gigapxl/$[level]/r$[y]_c$[x].jpg",
    "http://www.example.com/main.html",
    "/main.html",
    "http:\\www.example.com\\andhere.html",
)

urls_needing_valid_user_agent = {
    "https://www.homedepot.com/c/ah/how-to-build-a-bookshelf/9ba683603be9fa5395fab904e329862",
    "https://www.lenovo.com/us/en/p/laptops/thinkpad/thinkpadt/thinkpad-t16-gen-2-(16-inch-amd)/len101t0076#ports_slots",
}


original_perform_wayback_check = UrlValidator._perform_wayback_check


@mock.patch.object(UrlValidator, "_perform_wayback_check", autospec=True)
def test_valid_urls(mock_wayback_call):
    """
    GIVEN valid URLs and their known final URL locations
    WHEN the url validation functions checks these URLs
    THEN ensure each variant of the URL outputs the identical and correct URL to use
    """
    mock_wayback_call.side_effect = (
        lambda self, *args, **kwargs: original_perform_wayback_check(
            self, *args, **kwargs
        )
    )  # Forward args properly
    url_validator = UrlValidator(is_testing=True)
    for valid_url in valid_urls:
        urls_to_check = valid_urls[valid_url]
        for url in urls_to_check:
            while True:
                try:
                    commonized_url = url_validator.validate_url(url)[0]
                    # Sleep for longer if testing with Wayback Machine to prevent rate limiting
                    sleep(10) if mock_wayback_call.call_count > 3 else sleep(0.4)
                except WaybackRateLimited:
                    sleep(20)
                else:
                    break
            if "www." in commonized_url:
                assert valid_url == commonized_url
            else:
                valid_url_no_www = valid_url.replace("www.", "")
                assert valid_url_no_www == commonized_url


@mock.patch("time.perf_counter")
@mock.patch("requests.get")
def test_time_out_in_all_agent_sampling(mock_get, mock_time):
    url_validator = UrlValidator(is_testing=True)
    url_validator.timer = 0
    mock_time.return_value = 30
    mock_get.side_effect = requests.exceptions.ReadTimeout

    url = "www.google.com"
    headers = url_validator._generate_headers(url=url)
    with pytest.raises(InvalidURLError):
        url_validator._all_user_agent_sampling(url, headers)


@mock.patch("redis.Redis.from_url")
@mock.patch("redis.Redis.get")
@mock.patch.object(UrlValidator, "_get_current_minute_window")
def test_wayback_limiting(mock_datetime_now, mock_redis_get, mock_redis_client):
    url_validator = UrlValidator(is_testing=True)
    url = "www.google.com"
    mock_redis_get.return_value = 9
    mock_datetime_now.return_value = 60

    mock_redis_client.return_value = {f"wayback_ratelimit:{60 // 60}": 10}

    headers = url_validator._generate_headers(url=url)
    with pytest.raises(WaybackRateLimited):
        url_validator._perform_wayback_check(url, headers)


def test_invalid_urls():
    """
    GIVEN invalid URLs
    WHEN the url validation functions checks these invalid URLs
    THEN ensure the InvalidURLError exception is raised
    """
    url_validator = UrlValidator()
    for invalid_url in invalid_urls:
        with pytest.raises(InvalidURLError):
            url_validator.validate_url(invalid_url)


def test_urls_requiring_valid_user_agent():
    """
    GIVEN URLs that seemed to fail unknowingly, but were due to the request
        failing due to a User-agent indicating a script, OR the returns
        with a different URL even with a 200 status (lenovo)
    WHEN the url validation function checks these URLs
    THEN ensure that these urls are now validated properly
    """
    url_validator = UrlValidator(is_testing=True)
    for unknown_url in urls_needing_valid_user_agent:
        validated_url = False
        for _ in range(3):
            try:
                url_validator.validate_url(unknown_url)
            except InvalidURLError:
                continue
            else:
                validated_url = True
        assert validated_url


def test_random_user_agents():
    """
    GIVEN URLs that seemed to fail unknowingly, but were due to the request
        failing due to a User-agent indicating a script
    WHEN the User-Agent is iterated through random values
    THEN ensure that these urls are now validated properly
    """
    url_validator = UrlValidator(is_testing=True)
    valid_agent_used = 0
    for unknown_url in urls_needing_valid_user_agent:
        for user_agent in set(url_constants.USER_AGENTS):
            try:
                headers = {USER_AGENT: user_agent}
                url_validator.validate_url(unknown_url, headers)
            except InvalidURLError:
                # Avoid any kind of rate limiting or semblance of being a bot
                sleep(0.1)
            else:
                valid_agent_used += 1
                break

    assert valid_agent_used == len(urls_needing_valid_user_agent)
