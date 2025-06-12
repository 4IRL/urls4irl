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
from src.utils.strings.url_validation_strs import LOCATION, URL_VALIDATION, USER_AGENT

pytestmark = pytest.mark.unit

valid_urls = {
    "https://www.yahoo.com/": [
        "yahoo.com",
        "www.yahoo.com",
        "https://www.yahoo.com",
        "https://yahoo.com",
    ],
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
    "https://www.youtube.com/": [
        "www.youtube.com",
        "youtube.com",
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
    "https://immich.app/docs/overview/welcome/": [
        "https://immich.app/docs/overview/welcome",
    ],
    "https://developers.google.com/workspace/calendar/api/guides/overview": [
        "https://developers.google.com/workspace/calendar/api/guides/overview",
    ],
    "https://developers.google.com/workspace/keep/api/reference/rest": [
        "https://developers.google.com/workspace/keep/api/reference/rest"
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


def test_invalid_headers_removed():
    """
    GIVEN a URL to validate using the user's provided Headers
    WHEN the headers contain a set of invalid headers
    THEN ensure that those headers are removed
    """
    url_validator = UrlValidator(is_testing=True)
    invalid_headers = URL_VALIDATION.INVALID_HEADERS

    invalid_headers_dict = {header.upper(): "URLS" for header in invalid_headers}

    valid_headers = url_validator._generate_headers(
        "urls.4irl.app", invalid_headers_dict
    )

    assert all([header.upper() not in valid_headers for header in invalid_headers])


@mock.patch("requests.head")
@mock.patch.object(UrlValidator, "_check_if_is_short_url")
@mock.patch("socket.gethostbyname")
def test_android_valid_intent_url(socket_mock, short_url_mock, head_request_mock):
    """
    GIVEN a user on Android device attempting to validate a URL
    WHEN the URL is automatically converted into an `intent` type
    THEN ensure that it is parsed for the actual URL
    """
    original_url = "https://maps.app.goo.gl/ZPB15B5zC3dL3y4A7"
    valid_intent_url = "intent://maps.app.goo.gl/ZPB15B5zC3dL3y4A7#Intent;package=com.google.android.gms;scheme=https;S.browser_fallback_url=https://www.google.com/maps/place/Ithaca%2BFarmers%2BMarket,%2BSteamboat%2BLanding,%2B545%2B3rd%2BSt,%2BIthaca,%2BNY%2B14850/data%3D!4m2!3m1!1s0x89d0817c483332a1:0x697348f602028b6c%3Futm_source%3Dmstt_1&entry%3Dgps&coh%3D192189&g_ep%3DCAESBzI1LjIzLjQYACCenQoqhwEsOTQyMjMyOTksOTQyMTY0MTMsOTQyNzU3ODUsOTQyMTI0OTYsOTQyNzQ4ODMsOTQyMDczOTQsOTQyMDc1MDYsOTQyMDg1MDYsOTQyMTc1MjMsOTQyMTg2NTMsOTQyMjk4MzksOTQyNzUxNjQsNDcwODQzOTMsOTQyMTMyMDAsOTQyNTgzMjVCAlVT&skid%3D91ec9421-c7f2-438b-9b7d-114626892533;end;"

    android_user_agent = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36"

    socket_mock.return_value = "maps.app.goo.gl"
    short_url_mock.return_value = False

    response_return = mock.Mock(spec=requests.Response)
    response_return.status_code = 301
    response_return.is_redirect = True
    response_return.headers = {LOCATION: valid_intent_url}
    response_return.next = None
    response_return.url = original_url
    head_request_mock.return_value = response_return

    url_validator = UrlValidator(is_testing=True)
    validated_url, is_valid = url_validator.validate_url(
        url=original_url, user_headers={USER_AGENT: android_user_agent}
    )
    assert is_valid and validated_url == original_url


@mock.patch("requests.head")
@mock.patch.object(UrlValidator, "_check_if_is_short_url")
@mock.patch("socket.gethostbyname")
def test_url_invalid_schema_in_redirect(socket_mock, short_url_mock, head_request_mock):
    """
    GIVEN a user on Android device attempting to validate a URL
    WHEN the URL is automatically converted into an `intent` type
    THEN ensure that it is parsed for the actual URL
    """
    original_url = "https://maps.app.goo.gl/ZPB15B5zC3dL3y4A7"
    socket_mock.return_value = "maps.app.goo.gl"
    short_url_mock.return_value = False
    head_request_mock.side_effect = requests.exceptions.InvalidSchema

    url_validator = UrlValidator(is_testing=True)
    with pytest.raises(InvalidURLError):
        url_validator.validate_url(url=original_url)
